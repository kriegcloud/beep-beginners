# /// script
# requires-python = ">=3.11"
# dependencies = ["cryptography>=43"]
# ///
"""Write a password-protected Bitwarden JSON export full of fake items (D31).

  uv run --script make_bitwarden_fixture.py [--out bitwarden_export_fixture.json]

The password is the fixed test value below; it protects nothing real. The
format follows Bitwarden's "password protected" export: PBKDF2-SHA256 key,
HKDF-expanded into encryption and MAC keys, and type-2 EncStrings
(AES-256-CBC with HMAC-SHA256) for the validation string and the vault data.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PASSWORD = "beep-beginners-fixture"
ITERATIONS = 600_000


def hkdf_expand(prk: bytes, info: bytes, length: int = 32) -> bytes:
    out, block, counter = b"", b"", 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def enc_string(plain: str, enc_key: bytes, mac_key: bytes) -> str:
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    data = padder.update(plain.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    mac = hmac.new(mac_key, iv + ct, hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"2.{b64(iv)}|{b64(ct)}|{b64(mac)}"


def fake_vault() -> dict:
    folder_id = str(uuid.uuid4())
    items = []
    for i, (name, uri, user) in enumerate([
        ("Example Shop", "https://shop.example.com", "fixture.user@example.com"),
        ("Example Bank", "https://bank.example.net", "fixture-user"),
        ("Example Forum", "https://forum.example.org", "fixture_user"),
    ]):
        items.append({
            "id": str(uuid.uuid4()), "organizationId": None, "folderId": folder_id, "type": 1,
            "reprompt": 0, "name": name, "notes": "Fake item for beep-beginners tests.", "favorite": i == 0,
            "login": {"uris": [{"match": None, "uri": uri}], "username": user,
                      "password": f"fixture-password-{i}", "totp": None},
            "collectionIds": None,
        })
    items.append({"id": str(uuid.uuid4()), "organizationId": None, "folderId": None, "type": 2,
                  "reprompt": 0, "name": "Fixture note", "notes": "A fake secure note.", "favorite": False,
                  "secureNote": {"type": 0}, "collectionIds": None})
    return {"encrypted": False, "folders": [{"id": folder_id, "name": "Fixture folder"}], "items": items}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("bitwarden_export_fixture.json"))
    args = parser.parse_args()
    salt = base64.b64encode(os.urandom(16)).decode()
    master = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode(), salt.encode(), ITERATIONS, 32)
    enc_key, mac_key = hkdf_expand(master, b"enc"), hkdf_expand(master, b"mac")
    export = {
        "encrypted": True,
        "passwordProtected": True,
        "salt": salt,
        "kdfType": 0,
        "kdfIterations": ITERATIONS,
        "kdfMemory": None,
        "kdfParallelism": None,
        "encKeyValidation_DO_NOT_EDIT": enc_string(str(uuid.uuid4()), enc_key, mac_key),
        "data": enc_string(json.dumps(fake_vault()), enc_key, mac_key),
    }
    args.out.write_text(json.dumps(export, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "items": 4, "password": PASSWORD}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
