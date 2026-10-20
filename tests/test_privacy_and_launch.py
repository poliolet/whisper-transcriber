import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import launch
import notify
import transcribe


class PrivacyTests(unittest.TestCase):
    def test_notification_data_cannot_become_applescript(self):
        text = 'audio "example" \\ path\n" & do shell script "false" & " àudio'
        # Execute only a return statement: quotes, slashes and line breaks must
        # survive exactly as data, without executing the apparent command.
        result = subprocess.run(
            ["osascript", "-e", "return " + notify._literal(text)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.removesuffix("\n"), text)
        with patch.object(notify.subprocess, "run") as run:
            notify.notify(text, text)
        self.assertIn(notify._literal(text), run.call_args.args[0][-1])

    def test_token_sources_and_legacy_compatibility(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(Path, "home", return_value=Path(directory)), \
             patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(transcribe.load_hf_token())
            (Path(directory) / ".zshrc").write_text('export HF_TOKEN="hf_fake_legacy"\n')
            self.assertEqual(transcribe.load_hf_token(), "hf_fake_legacy")
            token_file = Path(directory) / ".config/whisper-transcriber/hf_token"
            token_file.parent.mkdir(parents=True)
            token_file.write_text("hf_fake_file\n")
            self.assertEqual(transcribe.load_hf_token(), "hf_fake_file")
            os.environ["HF_TOKEN"] = "hf_fake_environment"
            self.assertEqual(transcribe.load_hf_token(), "hf_fake_environment")

    def test_configuration_saves_token_privately(self):
        path = Path(__file__).resolve().parents[1] / "scripts/configure-huggingface.py"
        spec = importlib.util.spec_from_file_location("configure_hf", path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(Path, "home", return_value=Path(directory)), \
             patch.object(config, "getpass", return_value="hf_fake_test"), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            config.main()
            token_file = Path(directory) / ".config/whisper-transcriber/hf_token"
            self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(token_file.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(token_file.read_text().strip(), "hf_fake_test")
            self.assertNotIn("hf_fake_test", output.getvalue())

    def test_detached_worker_has_private_log_and_telemetry_disabled(self):
        real_popen = subprocess.Popen
        workers = []

        def start(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            workers.append(process)
            return process

        with tempfile.TemporaryDirectory(prefix="whisper user's ") as directory:
            root = Path(directory)
            (root / "transcribe.py").write_text(
                'import json, os, sys\n'
                'print(json.dumps({"args":sys.argv[1:], "metrics":os.environ["PYANNOTE_METRICS_ENABLED"], '
                '"hf":os.environ["HF_HUB_DISABLE_TELEMETRY"], "detached":os.getsid(0)==os.getpid()}))\n'
            )
            with patch.object(Path, "home", return_value=root), \
                 patch.object(launch, "__file__", str(root / "launch.py")), \
                 patch.object(launch.subprocess, "Popen", side_effect=start):
                args = ['audio "example".mp4', "Catalan", "yes"]
                first = launch.launch(args)
                second = launch.launch(args)
                for worker in workers:
                    self.assertEqual(worker.wait(timeout=10), 0)
            self.assertNotEqual(first, second)
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)
            self.assertEqual(first.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(json.loads(first.read_text()),
                             {"args": args, "metrics": "0", "hf": "1", "detached": True})

    def test_speaker_failure_saves_private_plain_transcript_and_redacts_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Downloads").mkdir()
            output = root / "Downloads/example.txt"
            output.write_text("previous transcript")
            output.chmod(0o644)
            segments = [{"start": 0, "end": 1, "text": "This is a synthetic test."}]
            engine = Mock(transcribe=Mock(return_value=segments))
            speakers = Mock(diarize=Mock(side_effect=RuntimeError("hf_fake_test")))
            with patch.object(Path, "home", return_value=root), \
                 patch.object(sys, "argv", ["transcribe.py", "example.wav", "English", "yes"]), \
                 patch.dict(os.environ, {"HF_TOKEN": "hf_fake_test"}), \
                 patch.dict(sys.modules, {"engine": engine, "diarize": speakers}), \
                 patch.object(transcribe, "Progress") as progress, \
                 patch.object(transcribe, "notify"), \
                 contextlib.redirect_stderr(io.StringIO()) as errors:
                transcribe.main()
            self.assertEqual(output.read_text(), "This is a synthetic test.")
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("hf_fake_test", errors.getvalue())
            self.assertIn("[REDACTED]", errors.getvalue())
            self.assertIn("failed", progress.return_value.finish.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
