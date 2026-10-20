import subprocess


def _literal(value: str) -> str:
    """Quote data as an AppleScript string, never as executable source."""
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t"))
    return '"' + escaped + '"'


def _run_dialog(script: str) -> subprocess.CompletedProcess:
    # Since macOS 26.5.2, panels from background osascript processes open
    # without focus (behind other windows); 'activate' brings them to front.
    return subprocess.run(
        ["osascript", "-e", "activate", "-e", script],
        capture_output=True, text=True,
    )


def notify(title: str, message: str) -> None:
    subprocess.run([
        "osascript", "-e",
        f'display notification {_literal(message)} with title {_literal(title)}',
    ])


def show_error(message: str) -> None:
    _run_dialog(
        f'display dialog {_literal(message)} with title "Whisper Transcriber" '
        f'buttons {{"OK"}} default button "OK" with icon stop'
    )


def pick_file() -> str | None:
    result = _run_dialog(
        'set theFile to choose file with prompt "Select an audio file to transcribe" '
        'of type {"mp3","wav","m4a","flac","ogg","mp4","webm","aac","wma"}\n'
        'return POSIX path of theFile'
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def pick_language(language_names: list[str], default: str = "English") -> str | None:
    items = ", ".join(_literal(name) for name in language_names)
    result = _run_dialog(
        f'choose from list {{{items}}} '
        f'with prompt "Select transcription language" '
        f'default items {{{_literal(default)}}} '
        f'with title "Whisper Transcriber"'
    )
    if result.returncode != 0:
        return None
    choice = result.stdout.strip()
    if choice == "false":
        return None
    return choice


def ask_yes_no(title: str, message: str) -> bool:
    result = _run_dialog(
        f'button returned of (display dialog {_literal(message)} with title {_literal(title)} '
        f'buttons {{"No", "Yes"}} default button "No")'
    )
    return result.stdout.strip() == "Yes"


def ask_text(title: str, message: str) -> str | None:
    result = _run_dialog(
        f'text returned of (display dialog {_literal(message)} with title {_literal(title)} '
        f'default answer "" '
        f'buttons {{"Cancel", "OK"}} default button "OK")'
    )
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return text if text else None
