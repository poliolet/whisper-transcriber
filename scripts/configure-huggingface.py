#!/usr/bin/env python3
"""Save a Hugging Face read token outside the project and shell history."""
from getpass import getpass
import os
from pathlib import Path
import tempfile


def main():
    token = getpass("Paste your Hugging Face read token (hidden): ").strip()
    if not token.startswith("hf_") or any(character.isspace() for character in token):
        raise SystemExit("Invalid token format. Create a read token at https://huggingface.co/settings/tokens")
    directory = Path.home() / ".config" / "whisper-transcriber"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise SystemExit("The token directory must not be a symbolic link.")
    directory.chmod(0o700)
    fd, temporary = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(token + "\n")
        Path(temporary).replace(directory / "hf_token")
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Token saved privately. You can now choose Yes for speaker identification.")


if __name__ == "__main__":
    main()
