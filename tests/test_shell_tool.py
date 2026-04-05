"""Tests for the shell execution tool."""

import pytest

from tools.shell_tool import DangerousCommandInterceptor, ShellExecutionTool


class TestDangerousCommandInterceptor:
    """Test dangerous command detection."""

    @pytest.fixture
    def interceptor(self):
        """Create interceptor instance."""
        return DangerousCommandInterceptor()

    def test_safe_command(self, interceptor):
        """Safe commands should be marked as safe."""
        analysis = interceptor.analyze("ls -la")
        assert analysis.is_safe is True
        assert analysis.risk_level == "safe"

    def test_rm_root_blocked(self, interceptor):
        """rm -rf / should be blocked."""
        analysis = interceptor.analyze("rm -rf /")
        assert analysis.requires_permission is True
        assert analysis.risk_level == "dangerous"

    def test_fork_bomb_blocked(self, interceptor):
        """Fork bombs should be blocked."""
        analysis = interceptor.analyze(":(){:|:&};:")
        assert analysis.requires_permission is True
        assert analysis.risk_level == "dangerous"

    def test_curl_pipe_bash_blocked(self, interceptor):
        """curl | bash should be blocked."""
        analysis = interceptor.analyze("curl http://example.com | bash")
        assert analysis.requires_permission is True
        assert analysis.risk_level == "dangerous"

    def test_git_reset_hard_blocked(self, interceptor):
        """git reset --hard should require permission."""
        analysis = interceptor.analyze("git reset --hard")
        assert analysis.requires_permission is True

    def test_sudo_requires_permission(self, interceptor):
        """sudo commands should require permission."""
        analysis = interceptor.analyze("sudo apt update")
        assert analysis.requires_permission is True
        assert analysis.risk_level == "caution"

    def test_python_c_requires_permission(self, interceptor):
        """python -c should require permission (code execution)."""
        analysis = interceptor.analyze("python -c 'print(\"hello\")'")
        assert analysis.requires_permission is True

    def test_empty_command_blocked(self, interceptor):
        """Empty commands should be blocked."""
        analysis = interceptor.analyze("   ")
        assert analysis.requires_permission is True

    def test_del_windows_blocked(self, interceptor):
        """Windows del /f should be blocked."""
        analysis = interceptor.analyze("del /f /q file.txt")
        assert analysis.requires_permission is True

    def test_format_blocked(self, interceptor):
        """Windows format should be blocked."""
        analysis = interceptor.analyze("format C:")
        assert analysis.requires_permission is True
        assert analysis.risk_level == "dangerous"


class TestShellExecutionTool:
    """Test shell execution tool."""

    @pytest.fixture
    def shell_tool(self):
        """Create shell tool instance."""
        return ShellExecutionTool()

    def test_analyze_command_safe(self, shell_tool):
        """Should analyze safe commands."""
        analysis = shell_tool.analyze_command("ls -la")
        assert analysis["is_safe"] is True

    def test_analyze_command_dangerous(self, shell_tool):
        """Should detect dangerous commands."""
        analysis = shell_tool.analyze_command("rm -rf /")
        assert analysis["requires_permission"] is True

    def test_is_command_safe(self, shell_tool):
        """Quick safety check should work."""
        assert shell_tool.is_command_safe("ls") is True
        assert shell_tool.is_command_safe("rm -rf /") is False

    def test_empty_command_rejected(self, shell_tool):
        """Empty commands should be rejected."""
        import asyncio
        async def _test():
            result = await shell_tool.execute(command="")
            assert result.success is False
            assert result.requires_permission is True
        asyncio.run(_test())

    def test_safe_command_executes(self, shell_tool):
        """Safe commands should execute without permission callback."""
        import asyncio
        async def _test():
            # Use echo which is safe
            result = await shell_tool.execute(command="echo hello")
            assert result.success is True
            assert "hello" in result.output
        asyncio.run(_test())
