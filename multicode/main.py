"""
MultiCode - AI Coding Assistant with Multi-Agent Debate Architecture

Package entry point module.
This module re-exports from the root main.py to avoid code duplication.
"""

# Re-export everything from the root main module
from main import ORIGINAL_CWD, main, setup_logging

__all__ = ["main", "ORIGINAL_CWD", "setup_logging"]
