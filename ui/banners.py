"""
ASCII Art Banner Customization for MultiCode.

Provides customizable banner themes for branding and fun.
"""


from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Built-in banner themes
BANNERS = {
    "default": {
        "art": [
            "  ███╗   ██╗███████╗██╗  ██╗██╗  ██╗",
            "  ████╗  ██║██╔════╝╚██╗██╔╝╚██╗██╔╝",
            "  ██╔██╗ ██║█████╗   ╚███╔╝  ╚███╔╝ ",
            "  ██║╚██╗██║██╔══╝   ██╔██╗  ██╔██╗ ",
            "  ██║ ╚████║███████╗██╔╝ ██╗██╔╝ ██╗",
            "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ],
        "colors": [
            "bold blue", "bold blue",
            "bold green", "bold green",
            "bold yellow", "bold yellow",
        ],
        "subtitle": "Multi-Agent AI Coding Assistant",
    },
    "minimal": {
        "art": [
            "  ███╗   ███╗ █████╗  ██████╗",
            "  ████╗ ████║██╔══██╗██╔════╝",
            "  ██╔████╔██║███████║██║     ",
            "  ██║╚██╔╝██║██╔══██║██║     ",
            "  ██║ ╚═╝ ██║██║  ██║╚██████╗",
            "  ╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝",
        ],
        "colors": ["bold cyan"] * 6,
        "subtitle": "Multi-Agent AI Coding Assistant",
    },
    "fire": {
        "art": [
            "  ███╗   ██╗███████╗██╗  ██╗██╗  ██╗",
            "  ████╗  ██║██╔════╝╚██╗██╔╝╚██╗██╔╝",
            "  ██╔██╗ ██║█████╗   ╚███╔╝  ╚███╔╝ ",
            "  ██║╚██╗██║██╔══╝   ██╔██╗  ██╔██╗ ",
            "  ██║ ╚████║███████╗██╔╝ ██╗██╔╝ ██╗",
            "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ],
        "colors": [
            "bold red", "bold red",
            "bold yellow", "bold yellow",
            "bold magenta", "bold magenta",
        ],
        "subtitle": "Multi-Agent AI Coding Assistant",
    },
    "matrix": {
        "art": [
            "  ███╗   ██╗███████╗██╗  ██╗██╗  ██╗",
            "  ████╗  ██║██╔════╝╚██╗██╔╝╚██╗██╔╝",
            "  ██╔██╗ ██║█████╗   ╚███╔╝  ╚███╔╝ ",
            "  ██║╚██╗██║██╔══╝   ██╔██╗  ██╔██╗ ",
            "  ██║ ╚████║███████╗██╔╝ ██╗██╔╝ ██╗",
            "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ],
        "colors": ["bold green"] * 6,
        "subtitle": "Enter the Matrix... of Code",
    },
    "neon": {
        "art": [
            "  ███╗   ██╗███████╗██╗  ██╗██╗  ██╗",
            "  ████╗  ██║██╔════╝╚██╗██╔╝╚██╗██╔╝",
            "  ██╔██╗ ██║█████╗   ╚███╔╝  ╚███╔╝ ",
            "  ██║╚██╗██║██╔══╝   ██╔██╗  ██╔██╗ ",
            "  ██║ ╚████║███████╗██╔╝ ██╗██╔╝ ██╗",
            "  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ],
        "colors": [
            "bold magenta", "bold magenta",
            "bold cyan", "bold cyan",
            "bold blue", "bold blue",
        ],
        "subtitle": "Multi-Agent AI Coding Assistant",
    },
}

DEFAULT_BANNER_NAME = "default"


def get_banner_names() -> list[str]:
    """Get list of available banner names."""
    return list(BANNERS.keys())


def render_banner(
    console: Console,
    banner_name: str | None = None,
    version: str = "1.0.0",
) -> None:
    """
    Render a banner to the console.

    Args:
        console: Rich console instance
        banner_name: Name of banner theme to use (uses default if None)
        version: Version string to display
    """
    banner_name = banner_name or DEFAULT_BANNER_NAME
    theme = BANNERS.get(banner_name, BANNERS[DEFAULT_BANNER_NAME])

    banner = Text()
    banner.append("\n", style="default")

    for line, color in zip(theme["art"], theme["colors"], strict=True):
        banner.append(line + "\n", style=color)

    banner.append("\n", style="default")
    banner.append(f"  {theme['subtitle']}\n", style="italic")
    banner.append("  Powered by OpenRouter\n", style="dim")
    banner.append("\n", style="default")

    console.print(Panel(
        banner,
        title=f"[bold]MultiCode v{version}[/bold]",
        border_style="bold blue",
        box=box.DOUBLE,
    ))


def set_banner_style(style_name: str) -> bool:
    """
    Save the banner style preference to settings.

    Args:
        style_name: Name of the banner style

    Returns:
        True if saved successfully
    """
    from config import get_settings, save_settings

    settings = get_settings()
    settings.ui.banner_style = style_name
    return save_settings(settings)


def get_banner_style() -> str:
    """
    Get the current banner style from settings.

    Returns:
        Name of the current banner style
    """
    from config import get_settings

    settings = get_settings()
    return getattr(settings.ui, 'banner_style', DEFAULT_BANNER_NAME)
