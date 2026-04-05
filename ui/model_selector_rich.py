"""
Premium Model Selector for MultiCode - Improved Version.

Features:
- Uses api.models.ModelInfo directly (no duplication)
- Pre-selected models properly initialized
- Quick-select presets (Coding, Chat, Balanced, Free)
- Cost estimator for selected models
- Popular/recommended models highlighted
- Better search with "free" keyword support
- Clear current selection display

Usage:
    from ui.model_selector_rich import select_models_interactive_async
    selected = await select_models_interactive_async(models, pre_selected=["model1", "model2"])
"""

import asyncio

from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Import the canonical ModelInfo from api.models
from api.models import ModelInfo as ApiModelInfo


# Local ModelInfo wrapper for selector (uses same attributes)
class ModelInfo:
    """Model info wrapper for the selector - uses api.models.ModelInfo internally."""
    def __init__(self, api_model: ApiModelInfo):
        self.id = api_model.id
        self.name = api_model.name
        self.context = api_model.context_length
        self.provider = api_model.provider or "Unknown"
        self.is_free = api_model.is_free
        self.price_prompt = api_model.pricing_prompt
        self.price_completion = api_model.pricing_completion
        self.description = api_model.description
        self._api_model = api_model

    def price_per_million(self) -> str:
        """Get price per 1 million tokens."""
        if self.is_free:
            return "FREE"
        if self.price_prompt is None:
            return "Unknown"
        try:
            price_per_m = float(self.price_prompt) * 1000
            return f"${price_per_m:.4f}/1M"
        except (ValueError, TypeError):
            return "Unknown"

    def estimated_cost_100k(self) -> str:
        """Get estimated cost for 100k tokens."""
        if self.is_free:
            return "$0.00"
        if self.price_prompt is None:
            return "Unknown"
        try:
            cost = float(self.price_prompt) * 100
            return f"${cost:.4f}"
        except (ValueError, TypeError):
            return "Unknown"

    def is_popular(self) -> bool:
        """Check if this is a popular/recommended model."""
        popular_ids = {
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "openai/gpt-4-turbo",
            "openai/gpt-4o",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mistral-large",
            "qwen/qwen-2.5-coder-7b-instruct:free",
            "google/gemma-2-9b-it:free",
            "deepseek/deepseek-coder-v2-lite-instruct:free",
        }
        return self.id in popular_ids

    def is_recommended_for(self, category: str) -> bool:
        """Check if model is recommended for a specific use case."""
        recommendations = {
            "coding": {
                "anthropic/claude-3.5-sonnet",
                "openai/gpt-4o",
                "qwen/qwen-2.5-coder-7b-instruct:free",
                "deepseek/deepseek-coder-v2-lite-instruct:free",
                "google/gemma-2-9b-it:free",
            },
            "chat": {
                "anthropic/claude-3.5-sonnet",
                "openai/gpt-4o",
                "google/gemini-pro-1.5",
                "meta-llama/llama-3-70b-instruct:free",
            },
            "speed": {
                "google/gemma-2-9b-it:free",
                "meta-llama/llama-3-8b-instruct:free",
                "mistralai/mistral-7b-instruct:free",
            },
            "quality": {
                "anthropic/claude-3.5-sonnet",
                "anthropic/claude-3-opus",
                "openai/gpt-4o",
                "openai/gpt-4-turbo",
            },
        }
        return self.id in recommendations.get(category, set())


# Preset configurations for quick selection
PRESETS = {
    "coding": {
        "name": "💻 Best for Coding",
        "description": "Top models for code generation and review",
        "models": [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "qwen/qwen-2.5-coder-7b-instruct:free",
            "deepseek/deepseek-coder-v2-lite-instruct:free",
        ],
    },
    "free": {
        "name": "🆓 Free Models",
        "description": "All free models (unlimited usage)",
        "filter": lambda m: m.is_free,
    },
    "balanced": {
        "name": "⚖️ Balanced",
        "description": "Good quality and cost balance",
        "models": [
            "google/gemma-2-27b-it:free",
            "meta-llama/llama-3-70b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free",
        ],
    },
    "quality": {
        "name": "🏆 Best Quality",
        "description": "Highest quality models (paid)",
        "models": [
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-opus",
            "openai/gpt-4o",
        ],
    },
}


def create_welcome_layout(selected_count: int, has_presets: bool = True) -> Layout:
    """Create the welcome screen layout with presets."""
    content = []

    content.append("[bold cyan]Welcome to Model Selection![/bold cyan]\n")
    content.append("[dim]Select the AI models MultiCode will use for your tasks.[/dim]\n")
    content.append("")

    if has_presets:
        content.append("[bold]Quick Select Presets:[/bold]")
        content.append("  [bold cyan]1[/bold cyan] - 💻 Best for Coding (recommended)")
        content.append("  [bold cyan]2[/bold cyan] - 🆓 Free Models (unlimited)")
        content.append("  [bold cyan]3[/bold cyan] - ⚖️ Balanced (quality + cost)")
        content.append("  [bold cyan]4[/bold cyan] - 🏆 Best Quality (premium)")
        content.append("")

    content.append(f"[dim]Currently selected: {selected_count} models[/dim]")
    content.append("")
    content.append("[dim]Or press Enter to browse all models manually[/dim]")

    panel = Panel(
        Text.from_markup("\n".join(content)),
        title="[bold]MODEL SELECTION[/bold]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )

    layout = Layout()
    layout.split(Layout(panel, name="main"))
    return layout


def create_stage2_layout(
    models: list[ModelInfo],
    selected: set[str],
    cursor: int,
    search: str,
    show_recommendations: bool = True,
) -> Layout:
    """Create the Stage 2 layout with live search and recommendations."""
    layout = Layout()

    # Filter models based on search
    filtered = get_filtered_models(models, search)

    # Calculate estimated cost
    total_cost_100k = sum(
        float(m.price_prompt or 0) * 100
        for m in models if m.id in selected and not m.is_free
    )

    # Show selected models at the top
    selected_display = ""
    if selected:
        selected_names = []
        for m in models:
            if m.id in selected:
                selected_names.append(m.name.split(":")[-1].strip()[:25])  # Short name
        if len(selected_names) <= 3:
            selected_display = f"[green]Selected: {', '.join(selected_names)}[/green] | "
        else:
            selected_display = f"[green]Selected: {len(selected)} models[/green] | "

    # Status bar
    status_parts = []
    status_parts.append(selected_display)
    status_parts.append(f"[dim]Showing: {len(filtered)}[/dim]")
    if total_cost_100k > 0:
        status_parts.append(f"[yellow]Est. Cost: ${total_cost_100k:.4f}/100k tokens[/yellow]")
    if search:
        status_parts.append(f"[cyan]Search: '{search}'[/cyan]")

    status_text = " | ".join(status_parts)

    # Build model table
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        expand=True,
        header_style="bold cyan",
    )
    table.add_column("✓", width=4)
    table.add_column("Cursor", width=8)
    table.add_column("Model", width=50)
    table.add_column("Context", justify="right", width=12)
    table.add_column("Provider", width=15)
    table.add_column("Price/100k", justify="right", width=12)

    # Display up to 18 models (fits in terminal), centered on cursor
    display_count = min(18, len(filtered))
    start = max(0, cursor - 9)  # Center cursor
    if start + display_count > len(filtered):
        start = max(0, len(filtered) - display_count)

    for i in range(start, start + display_count):
        if i >= len(filtered):
            break
        model = filtered[i]
        is_selected = model.id in selected
        is_cursor = i == cursor
        is_popular = model.is_popular()
        is_recommended = model.is_recommended_for("coding") if not search else False

        # Selection marker
        if is_selected:
            marker = "[green bold]✓[/green bold]"
        else:
            marker = " "

        # Cursor indicator
        if is_cursor:
            cursor_indicator = "[cyan bold]► HERE[/cyan bold]"
        else:
            cursor_indicator = ""

        # Model name with cursor highlight and badges
        if is_cursor:
            name_style = "[reverse bold]"
        elif is_selected:
            name_style = "[green bold]"
        elif model.is_free:
            name_style = "[green]"
        else:
            name_style = "[yellow]"

        # Add badges
        badges = ""
        if is_popular:
            badges += " ⭐"
        if is_recommended and not search:
            badges += " 💻"
        if model.is_free:
            badges += " 🆓"

        # Price
        if model.is_free:
            price_text = "[green bold]$0.0000[/green bold]"
        elif model.price_prompt:
            try:
                cost = float(model.price_prompt) * 100
                price_text = f"[yellow]${cost:.4f}[/yellow]"
            except (ValueError, TypeError):
                price_text = "[dim]Unknown[/dim]"
        else:
            price_text = "[dim]Unknown[/dim]"

        table.add_row(
            marker,
            cursor_indicator,
            f"{name_style}{model.name}{badges}[/]",
            f"{model.context:,}" if model.context else "[dim]N/A[/dim]",
            model.provider,
            price_text,
        )

    # Help text with preset hints
    help_parts = []
    help_parts.append("[dim]↑↓[/dim] Navigate")
    help_parts.append("[bold green]Space[/bold green] Toggle Select")
    help_parts.append("[dim]Enter[/dim] Confirm")
    help_parts.append("[dim]A[/dim] Select All")
    help_parts.append("[dim]N[/dim] Deselect All")
    help_parts.append("[dim]1-4[/dim] Presets")
    help_parts.append("[green bold]Type 'next' to finish[/green bold]")

    help_text = " | ".join(help_parts)

    # Create main panel content using Group
    panel_content = Group(
        Text.from_markup(status_text),
        Text(""),  # Empty line for spacing
        table,
        Text(""),  # Empty line for spacing
        Text.from_markup(help_text),
    )

    panel = Panel(
        panel_content,
        title=f"[bold]SELECT MODELS[/bold] - [green]{len(selected)}[/green] selected",
        border_style="green" if selected else "yellow",
        box=box.ROUNDED,
    )

    # Full width layout
    layout.split(Layout(panel, name="main"))
    return layout


async def show_presets_menu(console: Console, models: list[ModelInfo]) -> set[str] | None:
    """Show presets menu and return selected models if preset chosen."""
    options = [
        ("1 - 💻 Best for Coding", "coding"),
        ("2 - 🆓 Free Models", "free"),
        ("3 - ⚖️ Balanced", "balanced"),
        ("4 - 🏆 Best Quality", "quality"),
        ("5 - Browse All Manually", "browse"),
    ]

    cursor = 0

    try:
        from readchar import key, readkey

        with Live(create_preset_layout(cursor, options), console=console, refresh_per_second=4) as live:
            while True:
                k = readkey()

                if k == key.UP:
                    cursor = (cursor - 1) % len(options)
                elif k == key.DOWN:
                    cursor = (cursor + 1) % len(options)
                elif k in '12345':
                    cursor = int(k) - 1
                elif k in (key.ENTER, '\r', '\n'):
                    break

                live.update(create_preset_layout(cursor, options))

        # Return models for selected preset
        selected_preset = options[cursor][1]

        if selected_preset == "browse":
            return None  # User wants to browse manually

        return apply_preset(selected_preset, models)

    except (ImportError, KeyboardInterrupt):
        # Fallback to manual browsing
        return None


def create_preset_layout(cursor: int, options: list) -> Layout:
    """Create preset selection layout."""
    content = [
        "[bold cyan]Quick Select a Preset[/bold cyan]\n",
        "[dim]Choose a pre-configured model set or browse manually[/dim]\n",
        ""
    ]

    for i, (label, _) in enumerate(options):
        if i == cursor:
            content.append(f"[reverse bold cyan] ► {label} ◄ [/reverse bold cyan]")
        else:
            content.append(f"   {label}")

    content.append("\n[dim]Use ↑↓ or number keys, Enter to select[/dim]")

    panel = Panel(
        Text.from_markup("\n".join(content)),
        title="[bold]MODEL SELECTION PRESETS[/bold]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )

    layout = Layout()
    layout.split(Layout(panel, name="main"))
    return layout


def apply_preset(preset_name: str, models: list[ModelInfo]) -> set[str]:
    """Apply a preset and return selected model IDs."""
    preset = PRESETS.get(preset_name)
    if not preset:
        return set()

    selected = set()

    if "filter" in preset:
        # Filter-based preset (e.g., all free models)
        filter_func = preset["filter"]
        for model in models:
            # Use the internal API model for filter
            if filter_func(model._api_model):
                selected.add(model.id)
    elif "models" in preset:
        # List-based preset (specific models)
        preset_ids = set(preset["models"])
        for model in models:
            if model.id in preset_ids:
                selected.add(model.id)

    return selected


async def select_models_interactive_async(
    models,
    pre_selected: list[str] | None = None,
) -> list[str]:
    """
    Main entry point for async model selection.

    Features:
    - Welcome screen with presets
    - Pre-selected models properly initialized
    - Cost estimation display
    - Popular models highlighted
    - Search shortcuts (free, coding, chat, speed, quality)

    Args:
        models: List of ModelInfo objects (from api.models)
        pre_selected: Optional list of pre-selected model IDs

    Returns:
        List of selected model IDs
    """
    console = Console()

    # Convert api.models.ModelInfo to our wrapper
    selector_models: list[ModelInfo] = []
    for m in models:
        if isinstance(m, ApiModelInfo):
            selector_models.append(ModelInfo(m))
        else:
            # Already a wrapper, use as-is
            selector_models.append(m)

    # Initialize pre-selected models
    selected: set[str] = set(pre_selected) if pre_selected else set()

    # Go to main selection screen
    console.clear()
    cursor = 0
    search = ""

    # If no pre-selected models, show presets menu first
    if not selected:
        preset_result = await show_presets_menu(console, selector_models)

        if preset_result is not None:
            # User selected a preset
            selected = preset_result

            # Show confirmation
            console.clear()
            console.print(Panel(
                f"[green bold]✓ Applied Preset![/green bold]\n\n"
                f"Selected {len(selected)} models\n\n"
                f"[dim]Press Enter to confirm or continue to browse[/dim]",
                title="Preset Applied",
                border_style="green",
                box=box.ROUNDED,
            ))

            # Give user a moment to see the confirmation
            await asyncio.sleep(1.5)
            console.clear()

    # Initialize cursor to first selected model if any are pre-selected
    if selected:
        for i, model in enumerate(selector_models):
            if model.id in selected:
                cursor = i
                break

    try:
        from readchar import key, readkey

        with Live(
            create_stage2_layout(selector_models, selected, cursor, search),
            console=console,
            refresh_per_second=4,
        ) as live:
            while True:
                k = readkey()

                # Check for completion commands first (when typing in search)
                if search.lower() in ('next', 'done', 'finish', 'confirm'):
                    if not selected:
                        # Auto-select current if nothing selected
                        filtered = get_filtered_models(selector_models, search)
                        if 0 <= cursor < len(filtered):
                            selected.add(filtered[cursor].id)
                    break

                # SPECIAL KEYS - Handle before search input
                # Space - Toggle selection (most important!)
                if k == ' ':
                    filtered = get_filtered_models(selector_models, search)
                    if 0 <= cursor < len(filtered):
                        model_id = filtered[cursor].id
                        if model_id in selected:
                            selected.remove(model_id)
                        else:
                            selected.add(model_id)
                    live.update(create_stage2_layout(selector_models, selected, cursor, search))
                    continue

                # Backspace - remove last character from search
                if k == key.BACKSPACE or k == '\x08' or k == '\b':
                    if search:
                        search = search[:-1]
                    cursor = 0
                    live.update(create_stage2_layout(selector_models, selected, cursor, search))
                    continue

                # Navigation
                if k == key.UP:
                    filtered = get_filtered_models(selector_models, search)
                    # Move cursor up within filtered list
                    if cursor > 0:
                        cursor -= 1
                    # Make sure cursor points to a filtered model
                    elif len(filtered) > 0:
                        # Find the first selected model in filtered list
                        for i, m in enumerate(filtered):
                            if m.id in selected:
                                cursor = i
                                break

                elif k == key.DOWN:
                    filtered = get_filtered_models(selector_models, search)
                    # Move cursor down within filtered list
                    if cursor < len(filtered) - 1:
                        cursor += 1

                elif hasattr(key, 'PAGEUP') and k == key.PAGEUP:
                    cursor = max(0, cursor - 10)

                elif hasattr(key, 'PAGEDOWN') and k == key.PAGEDOWN:
                    filtered = get_filtered_models(selector_models, search)
                    cursor = min(len(filtered) - 1, cursor + 10)

                elif hasattr(key, 'HOME') and k == key.HOME:
                    cursor = 0

                elif hasattr(key, 'END') and k == key.END:
                    filtered = get_filtered_models(selector_models, search)
                    cursor = len(filtered) - 1

                # Selection with Enter
                elif k in (key.ENTER, '\r', '\n'):
                    # Confirm selection
                    if not selected:
                        filtered = get_filtered_models(selector_models, search)
                        if 0 <= cursor < len(filtered):
                            selected.add(filtered[cursor].id)
                    break

                # Commands
                elif k.lower() == 'a':
                    # Select all filtered
                    filtered = get_filtered_models(selector_models, search)
                    for m in filtered:
                        selected.add(m.id)

                elif k.lower() == 'n':
                    # Deselect all
                    selected.clear()

                # Preset shortcuts
                elif k == '1':
                    selected = apply_preset("coding", selector_models)
                elif k == '2':
                    selected = apply_preset("free", selector_models)
                elif k == '3':
                    selected = apply_preset("balanced", selector_models)
                elif k == '4':
                    selected = apply_preset("quality", selector_models)

                elif k == key.ESC:
                    # Confirm and exit
                    if not selected:
                        filtered = get_filtered_models(selector_models, search)
                        if 0 <= cursor < len(filtered):
                            selected.add(filtered[cursor].id)
                    break

                # Search input - any other printable character
                elif len(k) == 1 and k.isprintable():
                    search += k
                    cursor = 0
                    live.update(create_stage2_layout(selector_models, selected, cursor, search))
                    continue

                live.update(create_stage2_layout(selector_models, selected, cursor, search))

        return list(selected)

    except (ImportError, KeyboardInterrupt):
        # Fallback without readchar - simple prompt-based
        return fallback_model_selection(console, selector_models, selected)


def get_filtered_models(models: list[ModelInfo], search: str) -> list[ModelInfo]:
    """Get filtered models based on search query."""
    if not search:
        return models

    query = search.lower()
    if query == "free":
        return [m for m in models if m.is_free]
    elif query in ["coding", "code"]:
        return [m for m in models if m.is_recommended_for("coding")]
    elif query == "chat":
        return [m for m in models if m.is_recommended_for("chat")]
    elif query == "speed":
        return [m for m in models if m.is_recommended_for("speed")]
    elif query == "quality":
        return [m for m in models if m.is_recommended_for("quality")]
    else:
        return [m for m in models if query in m.id.lower() or query in m.name.lower()]


def fallback_model_selection(
    console: Console,
    models: list[ModelInfo],
    pre_selected: set[str],
) -> list[str]:
    """Fallback model selection without readchar library."""
    console.print()
    console.print(Panel(
        "[bold]MODEL SELECTION[/bold]\n\n"
        "Enter model numbers to select (comma-separated, e.g., 1,3,5)\n"
        "Type 'free' to show only free models\n"
        "Type 'coding' to show coding-recommended models\n"
        "Press Enter with empty input to confirm",
        title="Manual Selection",
        border_style="cyan",
        box=box.DOUBLE,
    ))
    console.print()

    selected = pre_selected.copy()
    search = ""

    while True:
        # Filter and display
        filtered = get_filtered_models(models, search)

        status = f"Showing {len(filtered)} models"
        if search:
            status += f" (search: '{search}')"
        if selected:
            status += f" | [green]Selected: {len(selected)}[/green]"
        console.print(f"[dim]{status}[/dim]\n")

        # Display up to 20
        table = Table(box=box.SIMPLE, show_header=True, expand=True)
        table.add_column("#", width=4)
        table.add_column("✓", width=4)
        table.add_column("Model", width=50)
        table.add_column("Context", justify="right")
        table.add_column("Provider")
        table.add_column("Price/100k")

        for i in range(min(20, len(filtered))):
            model = filtered[i]
            is_selected = model.id in selected
            marker = "[green]✓[/green]" if is_selected else " "
            name_style = "[green]" if model.is_free else "[yellow]"

            badges = ""
            if model.is_popular():
                badges += " ⭐"
            if model.is_free:
                badges += " 🆓"

            price_text = "$0.0000" if model.is_free else f"${float(model.price_prompt or 0)*100:.4f}"

            table.add_row(
                f"[cyan]{i+1}[/cyan]",
                marker,
                f"{name_style}{model.name}{badges}[/]",
                f"{model.context:,}" if model.context else "N/A",
                model.provider,
                price_text,
            )

        console.print(table)

        if len(filtered) > 20:
            console.print(f"[dim]... and {len(filtered) - 20} more (refine search)[/dim]")

        choice = console.input("\n[bold]Enter model number(s) or command:[/bold] ")

        console.clear()
        console.print()
        console.print(Panel(
            "[bold]MODEL SELECTION[/bold]\n\n"
            "Enter model numbers to select (comma-separated, e.g., 1,3,5)\n"
            "Type 'free' to show only free models\n"
            "Type 'coding' to show coding-recommended models\n"
            "Press Enter with empty input to confirm",
            title="Manual Selection",
            border_style="cyan",
            box=box.DOUBLE,
        ))
        console.print()

        if not choice:
            if not selected and filtered:
                selected.add(filtered[0].id)
            break
        elif choice.lower() == 'free':
            search = "free"
            console.print("[green]✓ Showing only free models[/green]\n")
        elif choice.lower() == 'coding':
            search = "coding"
            console.print("[green]✓ Showing coding-recommended models[/green]\n")
        elif choice.lower() == 'a':
            for m in filtered:
                selected.add(m.id)
            console.print(f"[green]✓ Selected all {len(filtered)} models[/green]\n")
        elif choice.lower() == 'n':
            selected.clear()
            console.print("[yellow]Deselected all[/yellow]\n")
        elif choice.lower() == 'q':
            break
        else:
            parts = choice.replace(',', ' ').split()
            added = 0
            for part in parts:
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(filtered):
                        model_id = filtered[idx].id
                        if model_id in selected:
                            selected.remove(model_id)
                        else:
                            selected.add(model_id)
                        added += 1
            if added > 0:
                console.print(f"[green]✓ Updated selection ({added} models)[/green]\n")
            else:
                console.print("[yellow]Invalid model number(s)[/yellow]\n")

    return list(selected)


__all__ = ["select_models_interactive_async", "ModelInfo"]
