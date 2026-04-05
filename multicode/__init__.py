"""MultiCode - AI Coding Assistant with Multi-Agent Debate Architecture."""

__version__ = "1.0.0"
__author__ = "MultiCode Team"

def run_cli():
    """Entry point for the multicode command."""
    import asyncio

    # Import the main module from the parent package
    # This works because multicode is installed as a package
    try:
        from multicode.main import main as cli_main
    except ImportError:
        # Fallback for development mode: try importing from project root
        from main import main as cli_main

    # Run main (it's async, so use asyncio.run)
    try:
        asyncio.run(cli_main())
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        pass

__all__ = ["run_cli"]
