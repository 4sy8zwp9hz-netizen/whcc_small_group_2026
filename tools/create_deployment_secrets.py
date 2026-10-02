"""Interactive local preparation only; no Google requests and no secret output."""
from getpass import getpass
from pathlib import Path
import secrets
from werkzeug.security import generate_password_hash


def main():
    folder = Path(__file__).resolve().parent.parent / "private" / "deployment-secrets"
    names = ("secret-key", "group-password-hash", "admin-password-hash")
    if any((folder / name).exists() for name in names):
        raise SystemExit("Existing secret files were preserved. Move them privately before generating a new set.")
    hashes = []
    for label in ("Group", "Admin"):
        password = getpass(label + " password (12+ characters): ")
        if not 12 <= len(password) <= 512 or password != getpass("Confirm " + label.lower() + " password: "):
            raise SystemExit("Passwords must match and contain 12 to 512 characters.")
        hashes.append(generate_password_hash(password))
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in zip(names, (secrets.token_hex(32), *hashes)):
        with (folder / name).open("x", encoding="utf-8") as stream:
            stream.write(value)
    print("Wrote three ignored files under private/deployment-secrets. Keep them private; no cloud changes made.")


if __name__ == "__main__":
    main()
