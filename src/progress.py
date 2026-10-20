"""Per-job progress shared with a small native macOS window."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


class Progress:
    def __init__(self, filename: str, show_window: bool = True):
        fd, path = tempfile.mkstemp(prefix="whisper-progress-", suffix=".json")
        os.close(fd)
        self.path = Path(path)
        self.started = time.time()
        self.process = None
        self.last_write = 0.0
        self.last_phase = None
        self.state = {"filename": filename, "started": self.started, "pid": os.getpid()}
        self.update("Starting…")
        helper = Path(__file__).resolve().parent.parent / "app" / "whisper-progress"
        if show_window:
            try:
                self.process = subprocess.Popen([str(helper), str(self.path)])
            except OSError as exc:
                print(f"Progress window unavailable: {exc}", flush=True)

    def update(self, phase, completed=None, total=None, detail="", *, status="running", output_path=None):
        now = time.monotonic()
        # Avoid disk writes for every inference batch; phase changes always appear.
        finished_step = total is not None and completed is not None and completed >= total
        if phase == self.last_phase and status == "running" and not finished_step and now - self.last_write < 0.25:
            return
        percent = None
        if total is not None and total > 0 and completed is not None:
            percent = max(0.0, min(100.0, 100.0 * completed / total))
        self.state.update(phase=phase, percent=percent, detail=detail, status=status,
                          output_path=str(output_path) if output_path else None,
                          updated=time.time())
        if status != "running":
            self.state["finished"] = time.time()
        temporary = self.path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(self.state, stream)
        temporary.replace(self.path)
        if phase != self.last_phase or status != "running":
            print(f"[{time.strftime('%H:%M:%S')}] {phase} — {detail}", flush=True)
        self.last_write = now
        self.last_phase = phase

    def finish(self, output_path, warning=""):
        self.update("Finished" if not warning else "Finished with a warning",
                    1, 1, warning or "Your transcript is ready.",
                    status="done", output_path=output_path)
        self._clean_if_closed()

    def fail(self, message):
        self.update("Could not finish", detail=message, status="error")
        self._clean_if_closed()

    def _clean_if_closed(self):
        if self.process is None or self.process.poll() is not None:
            self.path.unlink(missing_ok=True)
