#!/usr/bin/env python3
import os
import sys
import traceback
from pathlib import Path

# Disable optional library telemetry before any model imports.
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from languages import LANGUAGES, LANGUAGE_NAMES
from notify import notify, pick_file, pick_language, ask_yes_no
from progress import Progress


def load_hf_token() -> str | None:
    """Read a local token; keep the existing environment/.zshrc flow working."""
    token = os.environ.get("HF_TOKEN", "")
    if token:
        return token

    token_file = Path.home() / ".config" / "whisper-transcriber" / "hf_token"
    if token_file.is_file():
        token = token_file.read_text().strip()
        if token:
            return token

    # Read from .zshrc since .app bundles don't inherit shell env
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        for line in zshrc.read_text().splitlines():
            line = line.strip()
            if line.startswith("export HF_TOKEN="):
                token = line.split("=", 1)[1].strip().strip("'\"")
                if token:
                    return token

    return None


def redact(details: str) -> str:
    token = os.environ.get("HF_TOKEN")
    return details.replace(token, "[REDACTED]") if token else details


def format_plain(segments: list[dict]) -> str:
    """Join segments into readable paragraphs based on pauses and sentence endings."""
    if not segments:
        return ""

    paragraphs = []
    current = []

    for i, seg in enumerate(segments):
        text = seg["text"].strip()
        if not text or _is_hallucination(text):
            continue
        current.append(text)

        # Check gap to next segment
        gap = 0.0
        if i + 1 < len(segments):
            gap = segments[i + 1]["start"] - seg["end"]

        # Break paragraph on: pause > 0.5s AND we have enough text
        should_break = (
            gap > 0.5 and len(" ".join(current)) > 150
        ) or gap > 1.5

        if should_break and current:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs)


def format_diarized(transcription_segments: list[dict], speaker_segments: list[dict]) -> str:
    """Merge transcription with speaker labels, grouping consecutive same-speaker text."""
    if not transcription_segments:
        return ""

    lines = []
    current_speaker = None
    current_texts = []

    for seg in transcription_segments:
        text = seg["text"].strip()
        if not text or _is_hallucination(text):
            continue

        mid = (seg["start"] + seg["end"]) / 2
        speaker = _find_speaker(mid, speaker_segments)

        if speaker != current_speaker:
            if current_texts:
                label = f"[{current_speaker}] " if current_speaker else ""
                lines.append(f"{label}{' '.join(current_texts)}")
            current_speaker = speaker
            current_texts = [text]
        else:
            current_texts.append(text)

    if current_texts:
        label = f"[{current_speaker}] " if current_speaker else ""
        lines.append(f"{label}{' '.join(current_texts)}")

    return "\n\n".join(lines)


def _find_speaker(timestamp: float, speaker_segments: list[dict]) -> str | None:
    for seg in speaker_segments:
        if seg["start"] <= timestamp <= seg["end"]:
            return seg["speaker"]
    return None


def _is_hallucination(text: str) -> bool:
    """Detect Whisper hallucinations: repeated words/phrases in a segment."""
    words = text.lower().split()
    if len(words) < 4:
        return False
    # If 80%+ of words are the same word, it's a hallucination
    from collections import Counter
    most_common_count = Counter(words).most_common(1)[0][1]
    return most_common_count / len(words) > 0.7


def main():
    # Since macOS 26.5.2, dialogs from this (background) process open without
    # focus, so the app bundle asks upfront and passes answers as arguments.
    # Interactive dialogs remain as a fallback for running from a terminal.
    if len(sys.argv) >= 4:
        audio_path = sys.argv[1]
        language_name = sys.argv[2]
        use_diarization = sys.argv[3] == "yes"
        if language_name not in LANGUAGES:
            notify("Whisper Transcriber", f"Unknown language: {language_name}")
            print(f"Unknown language: {language_name}")
            sys.exit(1)
    else:
        audio_path = pick_file()
        if not audio_path:
            sys.exit(0)

        language_name = pick_language(LANGUAGE_NAMES)
        if not language_name:
            sys.exit(0)

        use_diarization = ask_yes_no(
            "Speaker diarization",
            "Enable speaker identification?"
        )

    language_code = LANGUAGES[language_name]
    audio_file = Path(audio_path)
    progress = Progress(audio_file.name)
    warning = ""

    # Handle HF token for diarization
    if use_diarization:
        hf_token = load_hf_token()
        if not hf_token:
            notify(
                "Whisper Transcriber",
                "Hugging Face token missing. Run scripts/configure-huggingface.py. Skipping speaker identification.",
            )
            use_diarization = False
            warning = "Speaker identification was skipped because HF_TOKEN is missing."
        else:
            os.environ["HF_TOKEN"] = hf_token

    # Start transcription
    notify("Whisper Transcriber", f"Transcribing: {audio_file.name} ({language_name})...")

    try:
        progress.update("Transcribing audio", detail="Preparing and transcribing with Whisper…")
        from engine import transcribe
        segments = transcribe(audio_path, language_code)
    except Exception as e:
        # The applet is already gone (runs us detached); notify and log
        notify("Whisper Transcriber", "Transcription failed — details in ~/Library/Logs/Whisper Transcriber")
        print(f"Transcription failed:\n{redact(str(e))}")
        progress.fail("Transcription failed. See ~/Library/Logs/Whisper Transcriber for details.")
        sys.exit(1)

    # Optional diarization
    if use_diarization:
        try:
            progress.update("Loading speaker identification", detail="Preparing the speaker models…")
            from diarize import diarize
            notify("Whisper Transcriber", "Running speaker diarization (this may take a while)...")
            speaker_segments = diarize(audio_path, progress=progress.update)
            output_text = format_diarized(segments, speaker_segments)
        except Exception:
            details = redact(traceback.format_exc())
            print(f"Diarization failed:\n{details}", file=sys.stderr, flush=True)
            notify("Whisper Transcriber", "Diarization failed. Saved plain text; details in ~/Library/Logs/Whisper Transcriber")
            output_text = format_plain(segments)
            warning = "Speaker identification failed. Saved a plain transcript; see ~/Library/Logs/Whisper Transcriber."
    else:
        output_text = format_plain(segments)

    # 7. Save to ~/Downloads
    output_path = Path.home() / "Downloads" / f"{audio_file.stem}.txt"
    progress.update("Saving transcript")
    try:
        # Restrict new and existing transcripts to this user. Refuse symlinks.
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(output_text)
    except OSError:
        print(redact(traceback.format_exc()), file=sys.stderr)
        progress.fail("Could not save the transcript. See ~/Library/Logs/Whisper Transcriber for details.")
        notify("Whisper Transcriber", "Could not save the transcript. Check ~/Library/Logs/Whisper Transcriber")
        sys.exit(1)
    progress.finish(output_path, warning)

    # 8. Notify
    notify("Whisper Transcriber", f"Done! Saved to ~/Downloads/{output_path.name}")


if __name__ == "__main__":
    main()
