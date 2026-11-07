# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = ["pytest>=8", "pyyaml>=6"]
# ///
"""Run the elevated batch's key-merge and sshd_config logic in pwsh.

Run: uv run --script plugins/onboarding/tests/test_elevated_batch.py
Skips when pwsh isn't installed. The block is taken from tools.py itself, so
the test exercises the exact text the batch writes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import tools  # noqa: E402

PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="pwsh not installed")

DEFAULT_SSHD = """# sshd_config
Port 22
#PasswordAuthentication yes
Subsystem sftp sftp-server.exe

Match Group administrators
       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
"""


def run_block(tmp: Path, keys: list[str]) -> None:
    block = tools.OPENSSH_BLOCK.replace("@KEYS@", ", ".join(tools.ps_quote(k) for k in keys) or "''")
    body = block[block.index("$keys = "):block.index("Set-Service sshd")]
    body = body.replace("C:\\ProgramData\\ssh\\administrators_authorized_keys", str(tmp / "keys"))
    body = body.replace("C:\\ProgramData\\ssh\\sshd_config", str(tmp / "sshd_config"))
    body = re.sub(r"^\s*icacls .*$", "", body, flags=re.M)
    subprocess.run([PWSH, "-NoProfile", "-Command", "$ErrorActionPreference='Stop'\n" + body], check=True)


def test_keys_merge_with_one_existing_key(tmp_path: Path) -> None:
    (tmp_path / "keys").write_text("ssh-ed25519 AAAAharness harness\n")
    (tmp_path / "sshd_config").write_text(DEFAULT_SSHD)
    run_block(tmp_path, ["ssh-rsa AAAA1 a", "ssh-ed25519 AAAA2 b", "ssh-ed25519 AAAA2 b"])
    lines = (tmp_path / "keys").read_text().split()
    assert (tmp_path / "keys").read_text().splitlines() == [
        "ssh-ed25519 AAAAharness harness", "ssh-rsa AAAA1 a", "ssh-ed25519 AAAA2 b"], lines


def test_keys_file_missing(tmp_path: Path) -> None:
    (tmp_path / "sshd_config").write_text(DEFAULT_SSHD)
    run_block(tmp_path, ["ssh-ed25519 AAAA9 only"])
    assert (tmp_path / "keys").read_text().splitlines() == ["ssh-ed25519 AAAA9 only"]


def test_password_auth_lands_above_match(tmp_path: Path) -> None:
    (tmp_path / "keys").write_text("")
    (tmp_path / "sshd_config").write_text(DEFAULT_SSHD)
    run_block(tmp_path, ["ssh-ed25519 AAAA9 only"])
    run_block(tmp_path, ["ssh-ed25519 AAAA9 only"])  # idempotent
    lines = (tmp_path / "sshd_config").read_text().splitlines()
    assert lines.count("PasswordAuthentication no") == 1
    assert lines.index("PasswordAuthentication no") < lines.index("Match Group administrators")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
