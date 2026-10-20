# Install Whisper Transcriber

When asked to install this project, carry out the steps below. Read `README.md`
first. Use the existing installer; do not replace dependencies or redesign the app.

## Install

1. Check that the host is macOS 26 or newer, running natively on Apple Silicon.
   Do not use Rosetta, Intel Python, Linux or a remote container for installation.
2. Keep the project in a permanent, user-writable folder. The installed app
   depends on this folder and its `.venv`. Do not install from a temporary folder.
3. Check for Apple's Command Line Tools and native Homebrew (`/opt/homebrew`).
   If missing, help the user install them from Apple's tools and `https://brew.sh`.
   OS prompts, administrator passwords and required approvals belong to the user;
   wait for prerequisites to finish before continuing.
4. From the project root, run:

   ```sh
   bash scripts/setup.sh
   ```

   The script needs network access, build-tool caches and permission to write
   to `~/Applications` and `~/Library/Services`. Request the environment's normal
   permissions if restricted. It requires no interactive answers once its
   prerequisites are installed. Keep `requirements.txt` unchanged.

## Verify

Run from the project root:

```sh
.venv/bin/python3 -c 'import platform; assert platform.machine() == "arm64"'
.venv/bin/python3 -m pip check
.venv/bin/python3 -B -m unittest discover -s tests -v
codesign --verify --deep --strict "$HOME/Applications/Whisper Transcriber.app"
test -f "$HOME/Applications/Whisper Transcriber.app/Contents/Resources/project-path.txt"
test -f "$HOME/Library/Services/Transcriure amb Whisper.workflow/Contents/Resources/document.wflow"
```

Check that the installed `project-path.txt` contains this checkout's absolute
path, and the installed Finder workflow points to the installed application.
These checks confirm installation, not a completed model download or transcription.
Use only synthetic audio for an optional transcription test, never personal recordings.

## Hugging Face and handoff

- Plain transcription requires no token. Models download on first use.
- Preserve any existing token configuration. Never print tokens or shell config.
- For optional speaker labels, point the user to README section 2. The user
  accepts both model conditions and enters their token directly into:
  `.venv/bin/python3 scripts/configure-huggingface.py`.
  Do not request a token in chat or put it in commands, logs or source files.
- Complete the base installation even if the user has not enabled speaker labels.
- Tell the user how to right-click a file, choose **Quick Actions → Transcriure
  amb Whisper**, and find the `.txt` in Downloads. If the action is hidden,
  show the Finder extension instructions from the README.
- Report which checks passed and any remaining manual steps. Do not claim a
  transcription succeeded unless a transcript was actually produced.
- Do not commit recordings, transcripts, tokens, logs, local agent state or
  generated apps. Do not publish to GitHub unless explicitly asked.
