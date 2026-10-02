"""Explicit fresh-install/migration preparation; no cloud calls or secret output."""
import argparse
from getpass import getpass
import os
from pathlib import Path
import secrets
from dotenv import dotenv_values
from werkzeug.security import generate_password_hash


def signing_key(root, mode, env_file=None, key_file=None):
    """Mirror configured SECRET_KEY precedence; never initialize a key during migration."""
    env_path = root / (env_file or ".env")
    if env_file and not env_path.is_file():
        raise ValueError("The selected private environment file does not exist.")
    values = {key: value for key, value in dotenv_values(root / ".env").items() if value is not None}
    if env_path.is_file():
        values.update({key: value for key, value in dotenv_values(env_path).items() if value is not None})
    effective = os.environ.get("SECRET_KEY") or values.get("SECRET_KEY")
    path = root / (key_file or os.environ.get("RSVP_SECRET_FILE")
                   or values.get("RSVP_SECRET_FILE") or "private/session.key")
    stored = path.read_text(encoding="utf-8").strip() if path.is_file() else None
    if mode == "fresh":
        database = root / (os.environ.get("RSVP_DATABASE") or values.get("RSVP_DATABASE") or "private/attendance.sqlite3")
        if effective or stored or database.is_file():
            raise ValueError("An existing signing key was found. Use --mode migrate; no key was replaced.")
        return secrets.token_hex(32)
    if mode != "migrate":
        raise ValueError("Choose fresh or migrate explicitly.")
    if key_file and effective and stored != effective:
        raise ValueError("The supplied key file disagrees with effective SECRET_KEY. Resolve this privately before migration.")
    key = effective or stored
    if not key or not 32 <= len(key) <= 512 or "\n" in key or "\r" in key or key.startswith("{"):
        raise ValueError("Migration needs the existing effective SECRET_KEY or signing-key file (32+ characters). No new key was generated.")
    return key


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("fresh", "migrate"))
    parser.add_argument("--env-file", help="Private env file used by the old runtime, e.g. .env.google")
    parser.add_argument("--key-file", help="Existing signing-key file; never a Google service-account JSON")
    args = parser.parse_args(argv)
    root = Path(root or Path(__file__).resolve().parent.parent)
    folder = root / "private" / "deployment-secrets"
    names = ("secret-key", "group-password-hash", "admin-password-hash")
    if any((folder / name).exists() for name in names):
        raise SystemExit("Existing deployment secret files were preserved. Do not replace them casually.")
    try:
        key = signing_key(root, args.mode, args.env_file, args.key_file)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    hashes = []
    for label in ("Group", "Admin"):
        password = getpass(label + " password (12+ characters): ")
        if not 12 <= len(password) <= 512 or password != getpass("Confirm " + label.lower() + " password: "):
            raise SystemExit("Passwords must match and contain 12 to 512 characters.")
        hashes.append(generate_password_hash(password))
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in zip(names, (key, *hashes)):
        with (folder / name).open("x", encoding="utf-8") as stream:
            stream.write(value)
    print("Wrote three ignored secret files. Migration preserves the signing key; browser cookies do not move to another hostname.")


if __name__ == "__main__":
    main()
