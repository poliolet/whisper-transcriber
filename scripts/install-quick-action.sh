#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKFLOW_NAME="Transcriure amb Whisper.workflow"
WORKFLOW_SOURCE="$PROJECT_DIR/finder/$WORKFLOW_NAME"
SERVICES_DIR="$HOME/Library/Services"
WORKFLOW_TARGET="$SERVICES_DIR/$WORKFLOW_NAME"
APPLICATIONS_DIR="$HOME/Applications"
APP_SOURCE="$PROJECT_DIR/app/Whisper Transcriber.app"
APP_PATH="$APPLICATIONS_DIR/Whisper Transcriber.app"

if [ ! -f "$APP_SOURCE/Contents/Resources/project-path.txt" ]; then
    echo "ERROR: Run bash scripts/build.sh before installing."
    exit 1
fi

mkdir -p "$APPLICATIONS_DIR" "$SERVICES_DIR"
APP_STAGE="$(mktemp -d "$APPLICATIONS_DIR/.whisper-install.XXXXXX")"
WORKFLOW_STAGE=""
APP_SWAPPED=0
WORKFLOW_SWAPPED=0
finish() {
    status=$?
    trap - EXIT
    if [ "$status" -ne 0 ]; then
        # Restore both previous integrations if any step of replacement failed.
        if [ -d "$APP_STAGE/previous.app" ]; then
            /bin/rm -rf "$APP_PATH"
            /bin/mv "$APP_STAGE/previous.app" "$APP_PATH" || exit 1
        elif [ "$APP_SWAPPED" -eq 1 ]; then
            /bin/rm -rf "$APP_PATH"
        fi
        if [ -n "$WORKFLOW_STAGE" ] && [ -d "$WORKFLOW_STAGE/previous.workflow" ]; then
            /bin/rm -rf "$WORKFLOW_TARGET"
            /bin/mv "$WORKFLOW_STAGE/previous.workflow" "$WORKFLOW_TARGET" || exit 1
        elif [ "$WORKFLOW_SWAPPED" -eq 1 ]; then
            /bin/rm -rf "$WORKFLOW_TARGET"
        fi
    fi
    /bin/rm -rf "$APP_STAGE"
    if [ -n "$WORKFLOW_STAGE" ]; then /bin/rm -rf "$WORKFLOW_STAGE"; fi
    exit "$status"
}
trap finish EXIT
WORKFLOW_STAGE="$(mktemp -d "$SERVICES_DIR/.whisper-install.XXXXXX")"
NEW_APP="$APP_STAGE/Whisper Transcriber.app"
NEW_WORKFLOW="$WORKFLOW_STAGE/$WORKFLOW_NAME"
/usr/bin/ditto "$APP_SOURCE" "$NEW_APP"
/usr/bin/xattr -cr "$NEW_APP"
/usr/bin/codesign --force --sign - "$NEW_APP"
/usr/bin/codesign --verify --deep --strict "$NEW_APP"
/usr/bin/ditto "$WORKFLOW_SOURCE" "$NEW_WORKFLOW"
QUICK_ACTION_COMMAND="/usr/bin/open -a \"$APP_PATH\" \"\$@\""
/usr/bin/plutil -replace actions.0.action.ActionParameters.COMMAND_STRING \
    -string "$QUICK_ACTION_COMMAND" "$NEW_WORKFLOW/Contents/Resources/document.wflow"
/usr/bin/plutil -lint "$NEW_WORKFLOW/Contents/Info.plist" "$NEW_WORKFLOW/Contents/Resources/document.wflow"

# Only replace the working installation after staging and validation succeed.
if [ -d "$APP_PATH" ]; then /bin/mv "$APP_PATH" "$APP_STAGE/previous.app"; fi
/bin/mv "$NEW_APP" "$APP_PATH"
APP_SWAPPED=1
if [ -d "$WORKFLOW_TARGET" ]; then /bin/mv "$WORKFLOW_TARGET" "$WORKFLOW_STAGE/previous.workflow"; fi
/bin/mv "$NEW_WORKFLOW" "$WORKFLOW_TARGET"
WORKFLOW_SWAPPED=1
/usr/bin/codesign --verify --deep --strict "$APP_PATH"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH"
/usr/bin/touch "$WORKFLOW_TARGET"
if [ -x /System/Library/CoreServices/pbs ]; then
    /System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
    /System/Library/CoreServices/pbs -update >/dev/null 2>&1 || true
fi

echo "Whisper Transcriber installed: $APP_PATH"
echo "Finder Quick Action installed: $WORKFLOW_TARGET"
echo "If hidden, enable it in System Settings > General > Login Items & Extensions > Finder."
