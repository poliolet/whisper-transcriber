"""Detach the worker with a private, unique log for each job."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def launch(arguments: list[str]) -> Path:
    log_dir = Path.home() / "Library" / "Logs" / "Whisper Transcriber"
    log_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    if log_dir.is_symlink():
        raise RuntimeError("The Whisper log directory must not be a symbolic link.")
    log_dir.chmod(0o700)
    fd, name = tempfile.mkstemp(prefix="transcription-", suffix=".log", dir=log_dir)
    env = dict(os.environ, PYANNOTE_METRICS_ENABLED="0", HF_HUB_DISABLE_TELEMETRY="1")
    try:
        with os.fdopen(fd, "wb") as log:
            subprocess.Popen(
                [sys.executable, "-u", str(Path(__file__).with_name("transcribe.py")), *arguments],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env=env,
            )
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Expected a file, language and speaker identification choice.")
    launch(sys.argv[1:])
