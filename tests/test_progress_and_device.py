import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diarize
from progress import Progress


class DeviceTests(unittest.TestCase):
    def test_auto_uses_metal_when_available(self):
        with patch.dict(os.environ, {"WHISPER_DIARIZATION_DEVICE": "auto"}), \
             patch.object(diarize.torch.backends.mps, "is_available", return_value=True):
            self.assertEqual(diarize._select_device(), "mps")

    def test_cpu_override_and_unavailable_gpu(self):
        with patch.dict(os.environ, {"WHISPER_DIARIZATION_DEVICE": "cpu"}), \
             patch.object(diarize.torch.backends.mps, "is_available", return_value=True):
            self.assertEqual(diarize._select_device(), "cpu")
        with patch.dict(os.environ, {"WHISPER_DIARIZATION_DEVICE": "auto"}), \
             patch.object(diarize.torch.backends.mps, "is_available", return_value=False):
            self.assertEqual(diarize._select_device(), "cpu")

    def test_failed_metal_retries_cpu_with_fresh_audio(self):
        annotation = Mock()
        turn = Mock(start=0.1, end=1.0)
        annotation.itertracks.return_value = [(turn, None, "SPEAKER_00")]
        pipeline = Mock()
        attempts = []

        def run(audio, hook):
            attempts.append(dict(audio))
            if len(attempts) == 1:
                audio["cached_partial_result"] = True
                raise RuntimeError("MPS out of memory")
            hook("segmentation", None, completed=2, total=4)
            hook("embeddings", None)
            return Mock(speaker_diarization=annotation)

        pipeline.side_effect = run
        progress = Mock()
        with patch.object(diarize, "_load_audio", return_value={"waveform": "test", "sample_rate": 16000}), \
             patch.object(diarize, "_get_pipeline", return_value=pipeline), \
             patch.object(diarize, "_select_device", return_value="mps"):
            result = diarize.diarize("test.mp4", progress=progress)
        self.assertEqual([call.args[0].type for call in pipeline.to.call_args_list], ["mps", "cpu"])
        self.assertNotIn("cached_partial_result", attempts[1])
        self.assertEqual(result, [{"start": 0.1, "end": 1.0, "speaker": "SPEAKER_00"}])
        progress.assert_any_call("Detecting speech", 2, 4, detail="CPU")
        progress.assert_any_call("Grouping speakers", detail="CPU")

    def test_cpu_failure_propagates_instead_of_looping(self):
        pipeline = Mock(side_effect=RuntimeError("inference failed"))
        with patch.object(diarize, "_load_audio", return_value={}), \
             patch.object(diarize, "_get_pipeline", return_value=pipeline), \
             patch.object(diarize, "_select_device", return_value="cpu"):
            with self.assertRaisesRegex(RuntimeError, "inference failed"):
                diarize.diarize("test.mp4")
        self.assertEqual(pipeline.call_count, 1)


class ProgressTests(unittest.TestCase):
    def make_progress(self):
        progress = Progress('audio "example".mp4', show_window=False)
        self.addCleanup(lambda: progress.path.unlink(missing_ok=True))
        return progress

    def test_real_phase_progress_and_indeterminate_transition(self):
        progress = self.make_progress()
        progress.update("Comparing voices", 3, 12, detail="Apple Silicon GPU · Metal")
        state = json.loads(progress.path.read_text())
        self.assertEqual(state["percent"], 25)
        self.assertEqual(state["filename"], 'audio "example".mp4')
        self.assertEqual(progress.path.stat().st_mode & 0o777, 0o600)
        progress.update("Grouping speakers")
        self.assertIsNone(json.loads(progress.path.read_text())["percent"])

    def test_final_warning_and_error_are_terminal(self):
        progress = self.make_progress()
        progress.finish(Path("/tmp/example.txt"), "Saved without speaker labels.")
        self.assertEqual(progress.state["status"], "done")
        self.assertEqual(progress.state["output_path"], "/tmp/example.txt")
        self.assertIn("warning", progress.state["phase"])
        self.assertIn("finished", progress.state)
        progress = self.make_progress()
        progress.fail("Could not save")
        self.assertEqual(progress.state["status"], "error")
        self.assertIsNone(progress.state["output_path"])

    def test_jobs_do_not_share_state(self):
        first, second = self.make_progress(), self.make_progress()
        self.assertNotEqual(first.path, second.path)
        first.update("Comparing voices", 1, 5)
        self.assertEqual(json.loads(second.path.read_text())["phase"], "Starting…")


if __name__ == "__main__":
    unittest.main()
