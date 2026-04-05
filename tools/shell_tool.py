"""
Shell Execution Tool with PowerShell/CMD Support.

Provides secure shell command execution with:
- Safety interceptor for dangerous commands
- PowerShell and CMD specific support
- User confirmation for destructive operations
- Timeout protection

RULE: No print() or Rich imports allowed in this module.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Inline minimal types that were previously in base_tool.py


@dataclass
class ToolParameter:
    """Description of a tool parameter."""
    name: str
    param_type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str = ""
    error: str | None = None
    requires_permission: bool = False
    permission_reason: str | None = None


class BaseTool:
    """Minimal base class for tools."""

    name: str = "base"
    description: str = ""
    parameters: list[ToolParameter] = []

    def __init__(self) -> None:
        pass

# Dangerous command patterns that ALWAYS require permission
DANGEROUS_PATTERNS = [
    (r'^rm\s+(-[rf]+\s+)?/\s*$', "Root directory deletion attempt"),
    (r'^rm\s+(-[rf]+\s+)?~.*$', "Home directory deletion attempt"),
    (r'^rm\s+(-[rf]+\s+)?\*.*$', "Wildcard deletion in current directory"),
    (r'^sudo\s+rm\s+.*$', "Privileged deletion command"),
    (r'^dd\s+.*$', "Disk write command (dd)"),
    (r'^mkfs\..*$', "Filesystem format command"),
    (r'^chmod\s+777\s+.*$', "Insecure permission change (777)"),
    (r'^chown\s+.*$', "Ownership change command"),
    (r'^:\(\)\{\s*:\|:\s*&\s*\}\s*;:', "Fork bomb pattern"),
    (r'^>\s*/dev/sd.*$', "Disk overwrite attempt"),
    (r'^curl.*\|\s*(ba)?sh\s*$', "Remote code execution (curl | bash)"),
    (r'^wget.*\|\s*(ba)?sh\s*$', "Remote code execution (wget | bash)"),
    (r'^nc\s+.*-e\s+.*$', "Netcat reverse shell"),
    (r'^netcat\s+.*-e\s+.*$', "Netcat reverse shell"),
    (r'^python.*-c.*socket.*$', "Python socket command"),
    (r'^perl.*-c.*socket.*$', "Perl socket command"),
    (r'^export\s+.*PATH=.*$', "PATH manipulation"),
    (r'^export\s+LD_.*$', "LD_LIBRARY manipulation"),
    (r'^git\s+reset\s+--hard.*$', "Hard git reset (data loss)"),
    (r'^mv\s+.*\s*/dev/null.*$', "Move to /dev/null"),
    # Windows specific
    (r'^del\s+/[fqs].*$', "Force delete command"),
    (r'^format\s+.*$', "Disk format command"),
    (r'^diskpart\s+.*$', "Disk partitioning"),
    (r'^rd\s+/s.*$', "Recursive directory delete"),
    (r'^rmdir\s+/s.*$', "Recursive directory delete"),
]

# Commands that require permission (but are commonly needed)
REQUIRES_PERMISSION = {
    'sudo': "Privilege escalation command",
    'su': "User switch command",
    'rm': "File deletion command",
    'del': "File deletion command",
    'dd': "Low-level disk operation",
    'mkfs': "Filesystem creation",
    'chmod': "Permission change",
    'chown': "Ownership change",
    'wget': "Network download",
    'curl': "Network request",
    'nc': "Network connection",
    'netcat': "Network connection",
    'ssh': "Remote connection",
    'scp': "Remote file transfer",
    'rsync': "File synchronization",
    'git': "Version control operation",
    'pip': "Package installation",
    'npm': "Package installation",
    'yarn': "Package installation",
    'apt': "System package manager",
    'apt-get': "System package manager",
    'brew': "System package manager",
    'docker': "Container operation",
    'kubectl': "Kubernetes operation",
    # Windows specific
    'powershell': "PowerShell execution",
    'cmd': "Command prompt execution",
    'taskkill': "Process termination",
    'shutdown': "System shutdown",
    'reg': "Registry operation",
}

# Commands that are generally safe
SAFE_COMMANDS = {
    'ls', 'dir', 'pwd', 'cd', 'cat', 'head', 'tail', 'less', 'more',
    'grep', 'find', 'which', 'where', 'whoami', 'uname', 'hostname',
    'echo', 'printf', 'date', 'time', 'wc', 'sort', 'uniq', 'cut',
    'awk', 'sed', 'tr', 'tee', 'xargs', 'env', 'set', 'export',
    'python', 'python3', 'node', 'npm', 'npx', 'yarn',
    'git', 'cargo', 'rustc', 'go', 'javac', 'java',
    'make', 'cmake', 'gcc', 'g++', 'clang',
    'pytest', 'unittest', 'jest', 'mocha', 'npm test',
    'mkdir', 'touch', 'cp', 'mv', 'rename',
    'zip', 'unzip', 'tar', 'gzip', 'gunzip',
    # Windows specific
    'type', 'copy', 'move', 'ren', 'rmdir',
    'ipconfig', 'ping', 'tracert', 'netstat',
}


@dataclass
class CommandAnalysis:
    """Result of command safety analysis."""
    command: str
    args: list[str]
    base_command: str
    shell_type: str  # "auto", "powershell", "cmd", "bash"
    is_safe: bool
    risk_level: str  # "safe", "caution", "dangerous"
    requires_permission: bool
    reason: str = ""
    matched_pattern: str | None = None
    suggestions: list[str] = field(default_factory=list)


class DangerousCommandInterceptor:
    """
    Intercepts and analyzes shell commands for safety.
    
    Maintains lists of dangerous patterns and restricted commands,
    and provides detailed analysis of command safety.
    """
    
    def __init__(self) -> None:
        self.dangerous_patterns = DANGEROUS_PATTERNS
        self.requires_permission = REQUIRES_PERMISSION
        self.safe_commands = SAFE_COMMANDS
        self._compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), reason)
            for pattern, reason in DANGEROUS_PATTERNS
        ]
    
    def analyze(self, command: str) -> CommandAnalysis:
        """
        Analyze a command for safety.
        
        Args:
            command: The command string to analyze
            
        Returns:
            CommandAnalysis with safety assessment
        """
        parts = command.strip().split()
        base_cmd = parts[0].lower() if parts else ""
        
        # Detect shell type
        shell_type = "auto"
        if base_cmd in ('powershell', 'pwsh'):
            shell_type = "powershell"
        elif base_cmd in ('cmd', 'cmd.exe'):
            shell_type = "cmd"
        elif base_cmd in ('bash', 'sh', 'zsh'):
            shell_type = "bash"
        
        # Check for empty command
        if not command.strip():
            return CommandAnalysis(
                command=command,
                args=[],
                base_command="",
                shell_type=shell_type,
                is_safe=False,
                risk_level="dangerous",
                requires_permission=True,
                reason="Empty command",
            )
        
        # Check against dangerous patterns first
        for pattern, reason in self._compiled_patterns:
            if pattern.search(command):
                return CommandAnalysis(
                    command=command,
                    args=parts[1:],
                    base_command=base_cmd,
                    shell_type=shell_type,
                    is_safe=False,
                    risk_level="dangerous",
                    requires_permission=True,
                    reason=reason,
                    matched_pattern=pattern.pattern,
                )
        
        # Check if base command requires permission
        if base_cmd in self.requires_permission:
            return CommandAnalysis(
                command=command,
                args=parts[1:],
                base_command=base_cmd,
                shell_type=shell_type,
                is_safe=False,
                risk_level="caution",
                requires_permission=True,
                reason=self.requires_permission[base_cmd],
                suggestions=[
                    f"Consider using safer alternatives",
                    f"Ensure you understand what '{base_cmd}' does",
                ],
            )
        
        # Check if it's a known safe command
        if base_cmd in self.safe_commands:
            # CRITICAL: Detect interpreter -c code execution (arbitrary code injection)
            interpreter_cmds = {'python', 'python3', 'node', 'perl', 'ruby', 'php', 'lua'}
            if base_cmd in interpreter_cmds and '-c' in parts:
                return CommandAnalysis(
                    command=command,
                    args=parts[1:],
                    base_command=base_cmd,
                    shell_type=shell_type,
                    is_safe=False,
                    risk_level="caution",
                    requires_permission=True,
                    reason=f"Interpreter code execution: {base_cmd} -c '...'",
                    suggestions=[
                        "Run scripts from files instead of inline code",
                        "Use -m module flag instead of -c where possible",
                    ],
                )
            # Additional check for pipes and redirects
            if '|' in command or '>' in command or '&&' in command:
                return CommandAnalysis(
                    command=command,
                    args=parts[1:],
                    base_command=base_cmd,
                    shell_type=shell_type,
                    is_safe=False,
                    risk_level="caution",
                    requires_permission=True,
                    reason=f"Command contains pipes/redirects: {base_cmd}",
                )
            
            return CommandAnalysis(
                command=command,
                args=parts[1:],
                base_command=base_cmd,
                shell_type=shell_type,
                is_safe=True,
                risk_level="safe",
                requires_permission=False,
                reason="Known safe command",
            )
        
        # Unknown command - require permission
        return CommandAnalysis(
            command=command,
            args=parts[1:],
            base_command=base_cmd,
            shell_type=shell_type,
            is_safe=False,
            risk_level="caution",
            requires_permission=True,
            reason=f"Unknown command: {base_cmd}",
            suggestions=[
                "Verify this command is safe",
                "Check command documentation",
            ],
        )
    
    def get_risk_summary(self, command: str) -> dict[str, Any]:
        """
        Get a detailed risk summary for a command.
        
        Args:
            command: The command to analyze
            
        Returns:
            Dictionary with risk analysis
        """
        analysis = self.analyze(command)
        return {
            "command": command,
            "base_command": analysis.base_command,
            "shell_type": analysis.shell_type,
            "is_safe": analysis.is_safe,
            "risk_level": analysis.risk_level,
            "requires_permission": analysis.requires_permission,
            "reason": analysis.reason,
            "matched_pattern": analysis.matched_pattern,
            "suggestions": analysis.suggestions,
            "args_count": len(analysis.args),
        }


class ShellExecutionTool(BaseTool):
    """
    Sandboxed shell execution tool with PowerShell/CMD support.
    
    This tool provides secure shell command execution with:
    1. Command analysis before execution
    2. Event-driven permission requests for dangerous commands
    3. PowerShell and CMD specific execution
    4. Timeout protection
    5. Output sanitization
    
    Example:
        tool = ShellExecutionTool()
        
        # Safe command - executes immediately
        result = await tool.execute(command="ls -la")
        
        # PowerShell command
        result = await tool.execute(
            command="Get-Process",
            shell="powershell"
        )
        
        # Dangerous command - requires permission
        result = await tool.execute(command="rm -rf ./build")
    """
    
    name = "shell"
    description = "Execute shell commands with safety checks, PowerShell/CMD support, and user permission for dangerous operations"
    
    def __init__(
        self,
        default_timeout: int = 60,
        max_output_length: int = 10000,
    ) -> None:
        super().__init__()
        self.default_timeout = default_timeout
        self.max_output_length = max_output_length
        self.interceptor = DangerousCommandInterceptor()
        
        self.parameters = [
            ToolParameter(
                name="command",
                param_type="string",
                description="The shell command to execute",
                required=True,
            ),
            ToolParameter(
                name="shell",
                param_type="string",
                description="Shell type: auto, powershell, cmd, bash (default: auto)",
                required=False,
                default="auto",
            ),
            ToolParameter(
                name="timeout",
                param_type="integer",
                description="Execution timeout in seconds",
                required=False,
                default=60,
            ),
            ToolParameter(
                name="working_dir",
                param_type="path",
                description="Working directory for command",
                required=False,
                default=None,
            ),
            ToolParameter(
                name="capture_stderr",
                param_type="boolean",
                description="Capture stderr in output",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        command: str,
        shell: str = "auto",
        timeout: int | None = None,
        working_dir: str | None = None,
        capture_stderr: bool = True,
        skip_safety_check: bool = False,
        permission_callback: callable | None = None,
        **kwargs: Any
    ) -> ToolResult:
        """
        Execute a shell command with safety checks.

        Args:
            command: The shell command to execute
            shell: Shell type (auto, powershell, cmd, bash)
            timeout: Execution timeout in seconds
            working_dir: Working directory for command
            capture_stderr: Include stderr in output
            skip_safety_check: Skip safety analysis (NOT RECOMMENDED)
            permission_callback: Optional async callable(command, reason, risk_level) -> bool
                If provided, called when a dangerous command is detected.
                Should return True to allow execution, False to deny.
            **kwargs: Additional parameters

        Returns:
            ToolResult with output, error, or permission request
        """
        if not command or not command.strip():
            return ToolResult(
                success=False,
                error="Empty command",
                requires_permission=True,
                permission_reason="Command string is empty or whitespace-only",
            )

        exec_timeout = timeout or self.default_timeout

        # Analyze command safety
        analysis = self.interceptor.analyze(command)

        logger.info(
            "Executing command (%s): %s [risk=%s]",
            analysis.shell_type, command, analysis.risk_level,
        )

        # If dangerous and not skipping safety check, request permission
        if analysis.requires_permission and not skip_safety_check:
            if permission_callback:
                granted = await permission_callback(
                    command=command,
                    reason=analysis.reason,
                    risk_level=analysis.risk_level,
                )
                if not granted:
                    logger.warning("Permission denied for command: %s", command)
                    return ToolResult(
                        success=False,
                        error="Permission denied by user",
                        requires_permission=True,
                        permission_reason=analysis.reason,
                    )
            else:
                # No callback provided — deny dangerous commands by default
                logger.warning("Dangerous command blocked (no permission callback): %s", command)
                return ToolResult(
                    success=False,
                    error=f"Command blocked: {analysis.reason}",
                    requires_permission=True,
                    permission_reason=analysis.reason,
                )

        # Execute the command
        try:
            # Determine shell executable
            shell_exec = self._get_shell_executable(shell, analysis.shell_type)

            process = await asyncio.create_subprocess_exec(
                *shell_exec,
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE if capture_stderr else asyncio.subprocess.DEVNULL,
                cwd=working_dir,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=exec_timeout,
            )

            # Decode and truncate output
            output = stdout.decode('utf-8', errors='replace') if stdout else ""
            error = stderr.decode('utf-8', errors='replace') if stderr else ""

            if len(output) > self.max_output_length:
                output = output[:self.max_output_length] + "\n... (truncated)"

            if process.returncode == 0:
                logger.info("Command completed successfully (rc=0, output=%d bytes)", len(output))
                return ToolResult(
                    success=True,
                    output=output,
                )
            else:
                logger.warning("Command failed (rc=%d): %s", process.returncode, error or output)
                return ToolResult(
                    success=False,
                    output=output,
                    error=error or f"Command failed with code {process.returncode}",
                )

        except asyncio.TimeoutError:
            logger.error("Command timed out after %ds: %s", exec_timeout, command)
            return ToolResult(
                success=False,
                error=f"Command timed out after {exec_timeout}s",
            )
        except Exception as e:
            logger.error("Command execution failed: %s", e)
            return ToolResult(
                success=False,
                error=f"Execution failed: {type(e).__name__}: {e}",
            )
    
    def _get_shell_executable(self, requested: str, detected: str) -> list[str]:
        """
        Get the shell executable based on request and detection.
        
        Args:
            requested: User requested shell
            detected: Auto-detected shell from command
            
        Returns:
            List of executable arguments
        """
        # User request takes precedence
        shell = requested if requested != "auto" else detected
        
        if shell == "powershell":
            return ["powershell", "-Command"] if sys.platform == "win32" else ["pwsh", "-Command"]
        elif shell == "cmd":
            return ["cmd", "/C"]
        elif shell == "bash":
            return ["bash", "-c"]
        else:
            # Auto-detect based on platform
            if sys.platform == "win32":
                # Windows: prefer PowerShell
                return ["powershell", "-Command"]
            else:
                # Unix-like: use bash
                return ["bash", "-c"]
    
    def analyze_command(self, command: str) -> dict[str, Any]:
        """
        Analyze a command without executing it.
        
        Args:
            command: The command to analyze
            
        Returns:
            Dictionary with safety analysis
        """
        return self.interceptor.get_risk_summary(command)
    
    def is_command_safe(self, command: str) -> bool:
        """
        Quick check if a command is safe to execute.
        
        Args:
            command: The command to check
            
        Returns:
            True if safe, False if requires permission
        """
        analysis = self.interceptor.analyze(command)
        return analysis.is_safe
    
    def get_blocked_commands_info(self) -> dict[str, Any]:
        """
        Get information about blocked/restricted commands.
        
        Returns:
            Dictionary with blocked command info
        """
        return {
            "dangerous_patterns_count": len(self.interceptor.dangerous_patterns),
            "requires_permission_count": len(self.interceptor.requires_permission),
            "safe_commands_count": len(self.interceptor.safe_commands),
            "dangerous_patterns": [p[0] for p in self.interceptor.dangerous_patterns],
            "requires_permission": list(self.interceptor.requires_permission.keys()),
        }
