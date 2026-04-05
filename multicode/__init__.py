"""MultiCode - AI Coding Assistant with Multi-Agent Debate Architecture."""

__version__ = "1.0.0"
__author__ = "MultiCode Team"

def run_cli():
    """Entry point for the multicode command."""
    import asyncio
    import sys
    from pathlib import Path

    # Add the parent directory to sys.path so we can import root modules
    # This is necessary because the package is installed but needs to access
    # config, core, ui, api modules that live at the project root level
    package_dir = Path(__file__).resolve().parent.parent
    if str(package_dir) not in sys.path:
        sys.path.insert(0, str(package_dir))

    try:
        from multicode.main import main as cli_main
    except ImportError:
        print("Error: MultiCode package is not properly installed.")
        print("Please reinstall with: pip install -e .")
        sys.exit(1)

    # Run main (it's async, so use asyncio.run)
    try:
        asyncio.run(cli_main())
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        pass

__all__ = ["run_cli"]
