#!/usr/bin/env python3
"""
MultiCode - AI Coding Assistant with Multi-Agent Debate Architecture

Entry point for the MultiCode CLI application.
"""

import asyncio
import logging
import os
import sys

from rich.console import Console
from rich.logging import RichHandler

# Capture the original working directory before any changes
ORIGINAL_CWD = os.getcwd()

from config import APP_NAME, is_setup_complete  # noqa: E402
from ui.cli import MultiCodeCLI  # noqa: E402


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create custom formatter for file operations
    class FileOperationFormatter(logging.Formatter):
        def format(self, record):
            # For file operation logs, use the message as-is (already formatted)
            if 'multicode.files' in record.name:
                return record.getMessage()
            # For other logs, use standard format
            return super().format(record)
    
    formatter = FileOperationFormatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="[%H:%M:%S]"
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add Rich handler for general logs
    rich_handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=verbose,
        console=Console(file=sys.stderr),
        show_time=False,  # We handle timestamps in formatter
    )
    rich_handler.setFormatter(formatter)
    root_logger.addHandler(rich_handler)
    
    # Set up file operation logger
    file_logger = logging.getLogger('multicode.files')
    file_logger.setLevel(logging.INFO)
    file_logger.propagate = False  # Don't propagate to root logger
    
    # Add handler for file operations
    file_handler = RichHandler(
        rich_tracebacks=False,
        console=Console(file=sys.stdout),
        show_time=False,
    )
    file_handler.setFormatter(FileOperationFormatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="[%H:%M:%S]"
    ))
    file_logger.addHandler(file_handler)


def print_quick_start() -> None:
    """Print quick start help for returning users."""
    console = Console()
    console.print(f"\n[bold]{APP_NAME}[/bold] - Multi-Agent AI Coding Assistant\n")
    console.print("[dim]Quick commands:[/dim]")
    console.print("  [bold]/models[/bold]     - Change selected models")
    console.print("  [bold]/agents[/bold]     - Change max agents setting")
    console.print("  [bold]/reset[/bold]      - Reset configuration")
    console.print("  [bold]/help[/bold]       - Show all commands")
    console.print("  [bold]/quit[/bold]       - Exit MultiCode\n")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - Multi-Agent AI Coding Assistant"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset ALL configuration (removes API key, models, settings)"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview file writes without executing them"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "simple", "complex", "audit"],
        default=None,
        help="Force workflow routing mode (auto/simple/complex/audit)"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "summary"],
        default="text",
        help="Output format: text (default), json (structured), summary (concise)"
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Named session for context persistence across commands"
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Task to execute in headless/API mode"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Enable headless/API mode: JSON I/O, no interactive prompts"
    )
    parser.add_argument(
        "--audit-log",
        default=None,
        help="Path to JSONL audit log file"
    )
    
    args = parser.parse_args()

    if args.version:
        from importlib.metadata import version
        try:
            v = version("multicode")
        except Exception:
            v = "1.0.0"
        print(f"{APP_NAME} v{v}")
        sys.exit(0)

    # Setup logging
    setup_logging(args.verbose)

    # Handle --reset flag (complete reset with confirmation)
    if args.reset:
        import shutil
        from pathlib import Path
        
        config_dir = Path.home() / ".multicode"
        
        print("=" * 60)
        print("MultiCode Complete Reset")
        print("=" * 60)
        print()
        
        if config_dir.exists():
            print(f"Found configuration directory: {config_dir}")
            print()
            print("This will PERMANENTLY DELETE:")
            print("  • API key")
            print("  • Selected models")
            print("  • Max agents setting")
            print("  • All cached data")
            print()
            
            confirm = input("Type 'YES' to confirm reset: ").strip()
            
            if confirm == "YES":
                try:
                    shutil.rmtree(config_dir)
                    print()
                    print("✓ Configuration deleted successfully!")
                    print()
                    print("Run 'multicode' to set up fresh configuration.")
                except Exception as e:
                    print()
                    print(f"✗ Error deleting configuration: {e}")
                    print()
                    print(f"Manual deletion: rmdir /S /Q {config_dir}")
                    sys.exit(1)
            else:
                print()
                print("Reset cancelled.")
                sys.exit(0)
        else:
            print("No configuration found. Nothing to reset.")
            print()
            print("Run 'multicode' for initial setup.")
        
        sys.exit(0)

    # Initialize CLI
    cli = MultiCodeCLI(
        dry_run=args.dry_run,
        force_mode=args.mode or "auto",
        output_format=args.output,
        session_name=args.session,
        headless=args.api,
        audit_log_path=args.audit_log,
    )

    # Check if setup is needed
    if not is_setup_complete() or args.reset:
        success = await cli.run_setup()
        if not success:
            sys.exit(1)
    else:
        # Show quick start for returning users
        cli.print_banner()
        print_quick_start()

        # Initialize client with saved config for returning users
        from api.models import ModelManager
        from api.openrouter import OpenRouterClient
        
        cli.client = OpenRouterClient()
        cli.model_manager = ModelManager(cli.client)

    # Run main application loop
    await cli.run_main_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[yellow]MultiCode interrupted by user. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as e:
        logging.exception("Fatal error occurred")
        print(f"\n[red]Fatal error: {e}[/red]")
        print("[dim]Check logs for details. Use --verbose for more info.[/dim]")
        sys.exit(1)
