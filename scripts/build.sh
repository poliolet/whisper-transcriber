#!/bin/bash
# Rebuild without changing Python dependencies or the installed application.
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$(uname -m)" != "arm64" ]; then
    echo "ERROR: Run natively on Apple Silicon."
    exit 1
fi
APP_BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$APP_BUILD_DIR"' EXIT
xcrun swiftc -O -target arm64-apple-macosx13.0 \
    "$PROJECT_DIR/app/Progress.swift" -o "$APP_BUILD_DIR/whisper-progress"
osacompile -l AppleScript -o "$APP_BUILD_DIR/Whisper Transcriber.app" "$PROJECT_DIR/app/main.applescript"
# Give Launch Services a stable identity instead of an anonymous applet.
/usr/bin/plutil -insert CFBundleIdentifier -string "dev.poliolet.whisper-transcriber" \
    "$APP_BUILD_DIR/Whisper Transcriber.app/Contents/Info.plist"
printf '%s\n' "$PROJECT_DIR" > "$APP_BUILD_DIR/Whisper Transcriber.app/Contents/Resources/project-path.txt"
/usr/bin/xattr -cr "$APP_BUILD_DIR/Whisper Transcriber.app"
/usr/bin/codesign --force --sign - "$APP_BUILD_DIR/Whisper Transcriber.app"
/usr/bin/codesign --verify --deep --strict "$APP_BUILD_DIR/Whisper Transcriber.app"
# Replace generated outputs only after both compilers and signing succeed.
/bin/rm -rf "$PROJECT_DIR/app/Whisper Transcriber.app"
/usr/bin/ditto "$APP_BUILD_DIR/Whisper Transcriber.app" "$PROJECT_DIR/app/Whisper Transcriber.app"
/bin/cp "$APP_BUILD_DIR/whisper-progress" "$PROJECT_DIR/app/whisper-progress"
# Finder may attach metadata when the generated app is copied into place.
/usr/bin/xattr -cr "$PROJECT_DIR/app/Whisper Transcriber.app"
if /usr/bin/xattr -p com.apple.FinderInfo "$PROJECT_DIR/app/Whisper Transcriber.app" >/dev/null 2>&1; then
    /usr/bin/xattr -d com.apple.FinderInfo "$PROJECT_DIR/app/Whisper Transcriber.app"
fi
/usr/bin/codesign --verify --deep --strict "$PROJECT_DIR/app/Whisper Transcriber.app"
echo "App built. Run bash scripts/install-quick-action.sh to install it."
