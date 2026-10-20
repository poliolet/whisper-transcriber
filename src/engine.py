import mlx_whisper

MODEL_NAME = "mlx-community/whisper-large-v3-turbo"


def transcribe(audio_path: str, language: str) -> list[dict]:
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=MODEL_NAME,
        language=language,
        verbose=False,
    )
    return result.get("segments", [])
