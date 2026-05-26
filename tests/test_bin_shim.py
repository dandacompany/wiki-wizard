"""Tests for bin/omw-dispatch shim and install.sh changes (Task 14)."""
import os
import subprocess
import stat
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
BIN_SHIM = REPO_ROOT / "bin" / "omw-dispatch"


class TestOmwDispatchShim:
    """Verify bin/omw-dispatch is a valid bash shim."""

    def test_shim_exists(self):
        assert BIN_SHIM.exists(), "bin/omw-dispatch not found"

    def test_shim_is_executable(self):
        mode = BIN_SHIM.stat().st_mode
        assert mode & stat.S_IXUSR, "bin/omw-dispatch must be user-executable"

    def test_shim_bash_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(BIN_SHIM)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"bash syntax error: {result.stderr}"

    def test_shim_contains_cd_dirname(self):
        content = BIN_SHIM.read_text()
        assert 'cd "$(dirname "$0")/.."' in content, \
            "shim must cd to repo root via dirname"

    def test_shim_calls_scripts_dispatch(self):
        content = BIN_SHIM.read_text()
        assert "python3 -m scripts.dispatch" in content, \
            "shim must delegate to python3 -m scripts.dispatch"

    def test_shim_uses_exec_delegation(self):
        """Shim must use exec (not a fork) so dispatch replaces the shell process."""
        content = BIN_SHIM.read_text()
        assert "exec python3 -m scripts.dispatch" in content, \
            "shim must use exec delegation"


class TestInstallShTmuxCheck:
    """Verify install.sh has been updated with tmux pre-flight."""

    INSTALL_SH = REPO_ROOT / "bin" / "install.sh"

    def test_install_sh_mentions_tmux_check(self):
        content = self.INSTALL_SH.read_text()
        assert "tmux" in content.lower()

    def test_install_sh_mentions_omw_dispatch(self):
        content = self.INSTALL_SH.read_text()
        assert "omw-dispatch" in content

    def test_install_sh_bash_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", str(self.INSTALL_SH)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"bash syntax error: {result.stderr}"
