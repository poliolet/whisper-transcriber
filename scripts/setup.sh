#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "ERROR: This application requires macOS."
    exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: Run setup natively on Apple Silicon, not under Rosetta."
    exit 1
fi

# The pinned MLX wheels require macOS 26 or newer.
MACOS_MAJOR="$(sw_vers -productVersion | cut -d. -f1)"
if [ "$MACOS_MAJOR" -lt 26 ]; then
    echo "ERROR: These tested dependencies require macOS 26 or newer."
    exit 1
fi

# Fail before downloading dependencies if Apple's build tools are missing.
if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find swiftc >/dev/null 2>&1 || ! command -v osacompile >/dev/null 2>&1; then
    echo "ERROR: Install Apple's Command Line Tools with xcode-select --install."
    echo "Wait for installation to finish, then run this script again."
    exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
    if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v python3.14 >/dev/null 2>&1; then
        echo "ERROR: Install native Apple Silicon Homebrew from https://brew.sh, then run this script again."
        exit 1
    fi
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "=== Whisper Transcriber Setup ==="
echo "Project directory: $PROJECT_DIR"
echo ""

# 0. Check for ffmpeg (needed for audio decoding)
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg not found. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "ERROR: Homebrew not found. Please install ffmpeg manually."
        exit 1
    fi
else
    echo "FFmpeg found: $(ffmpeg -version 2>&1 | head -1)"
fi

# 1. Create or repair the Python 3.14 virtualenv. Existing packages are kept.
if ! command -v python3.14 >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        brew install python@3.14
    else
        echo "ERROR: Install Python 3.14, then run setup again."
        exit 1
    fi
fi

python3.14 -c 'import platform, sys; sys.exit(0 if platform.machine() == "arm64" else "ERROR: Python must run natively on Apple Silicon.")'
if [ -x "$VENV_DIR/bin/python3" ] && "$VENV_DIR/bin/python3" --version >/dev/null 2>&1; then
    echo "Virtualenv already exists at $VENV_DIR"
else
    echo "Creating or repairing virtualenv..."
    python3.14 -m venv "$VENV_DIR"
    echo "Done."
fi

# 2. Activate
source "$VENV_DIR/bin/activate"
python3 -c 'import platform, sys; sys.exit(0 if platform.machine() == "arm64" else "ERROR: The virtualenv must use native Apple Silicon Python.")'

# 3. Install the versions validated together; never rewrite the lock file.
echo "Installing transcription and speaker identification dependencies…"
python3 -m pip install -r "$PROJECT_DIR/requirements.txt"
python3 -m pip check

# 4. Build locally, then install the app and Finder action.
bash "$PROJECT_DIR/scripts/build.sh"
bash "$PROJECT_DIR/scripts/install-quick-action.sh"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To use the app:"
echo "  1. Double-click: ~/Applications/Whisper Transcriber.app"
echo "  2. Drag one audio/video file onto the app icon in Finder or the Dock"
echo "  3. Or right-click one file and choose Quick Actions > Transcriure amb Whisper"
echo ""
echo "The first transcription downloads the model. Later runs reuse the cached model."
echo "For speaker identification, follow the Hugging Face steps in README.md."
echo "Keep this project folder in place; the app uses its Python environment."
