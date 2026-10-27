"""Give each transcription to the macOS session manager, independently of callers."""
import os
from pathlib import Path
import plistlib
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
    os.close(fd)
    # No shell or inherited Codex environment. Tokens remain in the existing
    # private configuration, read by transcribe.py, never in this job definition.
    job = {
        "Label": "dev.poliolet.whisper-transcriber.job." + Path(name).stem,
        "ProgramArguments": [sys.executable, "-u", str(Path(__file__).resolve().with_name("transcribe.py")), *arguments],
        "WorkingDirectory": str(Path.home()),
        "EnvironmentVariables": {
            "HOME": str(Path.home()),
            "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYANNOTE_METRICS_ENABLED": "0",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        },
        "StandardOutPath": name,
        "StandardErrorPath": name,
        "RunAtLoad": True,
        "LaunchOnlyOnce": True,
        "KeepAlive": False,
        # The completion window must survive the worker finishing.
        "AbandonProcessGroup": True,
        "Umask": 0o077,
    }
    job_fd, job_name = tempfile.mkstemp(prefix="job-", suffix=".plist", dir=log_dir)
    try:
        with os.fdopen(job_fd, "wb") as stream:
            plistlib.dump(job, stream)
        result = subprocess.run(
            ["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", job_name],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise RuntimeError("macOS could not start the transcription: " + result.stderr.strip())
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    finally:
        # launchd has read the definition. Do not register anything at login
        # or leave media paths in persistent agent files.
        Path(job_name).unlink(missing_ok=True)
    return Path(name)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Expected a file, language and speaker identification choice.")
    launch(sys.argv[1:])
