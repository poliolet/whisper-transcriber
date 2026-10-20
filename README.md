# Whisper Transcriber

Transcribe audio and video on your Apple Silicon Mac. Choose the language and,
optionally, label different speakers. Includes a progress window, drag and drop,
and a Finder right-click action.

## 1. Install

You need **Apple Silicon, macOS 26 or newer**, [Homebrew](https://brew.sh),
internet access and several GB of free space.

1. Install Apple's Command Line Tools if needed:
   ```sh
   xcode-select --install
   ```
   Wait for installation to finish.
2. Choose **Code → Download ZIP** on this page. Unzip it and put the folder
   somewhere permanent, such as `Documents/Whisper Transcriber`.
3. Open Terminal. Type `cd ` (with a space), drag that folder into Terminal,
   and press Return. Run:
   ```sh
   bash scripts/setup.sh
   ```

Setup installs Python, FFmpeg, the tested dependencies, the app in
`~/Applications`, and the Finder action. Allow several minutes.
**Keep the project folder in place.** If you move it, run setup again.

**Using a coding agent?** Open the downloaded folder with the agent and ask:

> Read AGENTS.md and install Whisper Transcriber on this Mac. Run the checks
> and tell me how to start transcribing.

The agent follows [AGENTS.md](AGENTS.md). You may need to approve macOS prompts
or permissions. Hugging Face setup below is optional and requires your account.

## 2. Connect Hugging Face (optional)

Plain transcription uses [Whisper](https://huggingface.co/mlx-community/whisper-large-v3-turbo)
and needs **no account or token**. For speaker labels, complete these steps once:

1. Create a free [Hugging Face account](https://huggingface.co/join).
2. Sign in and accept the conditions on **both** model pages:
   [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   and [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0).
3. In [Access Tokens](https://huggingface.co/settings/tokens), choose
   **Create new token → Read** and copy it.
4. From the project folder in Terminal, run:
   ```sh
   .venv/bin/python3 scripts/configure-huggingface.py
   ```
   Paste the token and press Return. **The pasted text stays hidden.**

The token is stored privately outside the project. Existing `HF_TOKEN` settings
in the environment or `~/.zshrc` still work.

## 3. Transcribe

1. Right-click one file in Finder: **Quick Actions → Transcriure amb Whisper**.
   Alternatively, open **Whisper Transcriber** in your user Applications folder,
   or drag a file onto its icon.
2. Choose the language, then **Yes** for speaker labels or **No** for plain text.
3. Wait for **Finished** and click **Open transcript**.

The `.txt` file appears in **Downloads**, using the input file's name.
**An existing transcript with the same name is replaced.** Speaker labels such
as `SPEAKER_00` distinguish voices; they do not identify people by name.

The first run downloads models and takes longer. Closing the progress window
leaves the job running. Percentages describe the current step. If speaker
identification fails, the app saves plain text and shows a warning.
Always check the transcript for recognition errors.

Supported: MP3, WAV, M4A, FLAC, OGG, MP4, WEBM, AAC and WMA. One file at a time.

## Help

- **Finder action missing:** enable it in **System Settings → General →
  Login Items & Extensions → Finder** (the location varies by macOS version).
- **Speaker labels fail:** accept both model conditions with the account that
  created the token. Run the token setup again to replace it.
- **App will not start:** run `bash scripts/setup.sh` from the project folder.
- **Error details:** in Finder, **Go → Go to Folder** →
  `~/Library/Logs/Whisper Transcriber`. Open the newest log.
  Review logs before sharing: they may contain filenames and local paths.

## Privacy

Recordings and transcripts are processed on your Mac and are not uploaded by the
app. Internet access is used for dependencies and model downloads/checks.
Optional Pyannote and Hugging Face telemetry is disabled.

`.gitignore` excludes tokens, recordings, transcripts, logs, assistant settings
and generated apps. Review files before publishing commits.

## Development

Rebuild and reinstall without changing Python dependencies:

```sh
bash scripts/build.sh
bash scripts/install-quick-action.sh
```

Run tests:

```sh
.venv/bin/python3 -B -m unittest discover -s tests -v
```

Native Apple Silicon; no Rosetta. Speaker identification uses Metal with CPU
fallback. For terminal runs, `WHISPER_DIARIZATION_DEVICE=cpu` forces CPU.

## License

[MIT](LICENSE). MLX Whisper and Pyannote use MIT; PyTorch uses BSD-3-Clause.
Models have their own access conditions and licenses. This repository contains
source code, not model weights or third-party binaries.
