import os
import subprocess
import warnings

# Set before importing pyannote, including when used from a terminal.
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

# Unsupported individual Metal operations may still run on the native CPU.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch

# We decode with the FFmpeg executable and supply a waveform. Pyannote's
# optional TorchCodec decoder is not needed (its current build rejects FFmpeg 9).
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore", message="\ntorchcodec is not installed correctly", category=UserWarning,
    )
    from pyannote.audio import Pipeline


_pipeline = None


def _get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        hf_token = os.environ["HF_TOKEN"]
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )
    return _pipeline


def _load_audio(audio_path: str) -> dict:
    """Decode audio/video to a 16kHz mono waveform without TorchCodec."""
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-i", audio_path,
        "-vn", "-ar", "16000", "-ac", "1",
        "-acodec", "pcm_f32le", "-f", "f32le", "pipe:1",
    ], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg could not decode the audio: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    samples = np.frombuffer(result.stdout, dtype="<f4").copy()
    if samples.size == 0:
        raise ValueError("The selected file contains no decodable audio.")
    return {"waveform": torch.from_numpy(samples).unsqueeze(0), "sample_rate": 16000}


def _select_device() -> str:
    requested = os.environ.get("WHISPER_DIARIZATION_DEVICE", "auto")
    if requested not in {"auto", "cpu", "mps"}:
        raise ValueError("WHISPER_DIARIZATION_DEVICE must be auto, cpu, or mps.")
    return "mps" if requested != "cpu" and torch.backends.mps.is_available() else "cpu"


def _run_pipeline(pipeline, audio, device, progress):
    label = "Apple Silicon GPU · Metal" if device == "mps" else "CPU"
    progress("Detecting speech", detail=label)

    def hook(step, artifact, *, total=None, completed=None, **kwargs):
        if total is not None:
            phase = {"segmentation": "Detecting speech", "embeddings": "Comparing voices"}.get(step, step)
            progress(phase, completed, total, detail=label)
        else:
            phase = {
                "segmentation": "Counting speakers",
                "speaker_counting": "Comparing voices",
                "embeddings": "Grouping speakers",
                "discrete_diarization": "Finishing speaker turns",
            }.get(step, step.replace("_", " ").capitalize())
            progress(phase, detail=label)

    pipeline.to(torch.device(device))
    # Each attempt gets a fresh mapping, without pyannote's per-file caches.
    return pipeline(dict(audio), hook=hook)


def diarize(audio_path: str, progress=None) -> list[dict]:
    progress = progress or (lambda *args, **kwargs: None)
    progress("Preparing audio for speaker identification")
    audio = _load_audio(audio_path)
    progress("Loading speaker models")
    pipeline = _get_pipeline()
    device = _select_device()
    try:
        result = _run_pipeline(pipeline, audio, device, progress)
    except (RuntimeError, NotImplementedError) as exc:
        if device != "mps":
            raise
        print(f"Metal diarization failed; retrying on CPU: {exc}", flush=True)
        progress("Restarting speaker identification", detail="GPU unavailable for this job; continuing on CPU.")
        result = _run_pipeline(pipeline, audio, "cpu", progress)
    # pyannote 4.x returns DiarizeOutput; extract the Annotation object
    diarization = getattr(result, "speaker_diarization", result)

    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })
    progress("Speaker identification complete", 1, 1,
             detail=f"{len({segment['speaker'] for segment in segments})} speakers detected")
    return segments
