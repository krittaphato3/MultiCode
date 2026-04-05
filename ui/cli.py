"""
Rich-based CLI interface for MultiCode.
Provides beautiful, interactive command-line UI for setup and model selection.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from api.models import ModelInfo, ModelManager
from api.openrouter import OpenRouterClient
from config import (
    APP_NAME,
    CONFIG_DIR,
    MAX_AGENTS_WARNING_THRESHOLD,
    get_max_agents,
    set_api_key,
    set_max_agents,
    set_selected_models,
)

# Color scheme
PRIMARY_COLOR = "bold blue"
SUCCESS_COLOR = "bold green"
WARNING_COLOR = "bold yellow"
ERROR_COLOR = "bold red"
INFO_COLOR = "cyan"


class MultiCodeCLI:
    """
    Interactive CLI for MultiCode using Rich.
    Handles onboarding, API key setup, and model selection.
    """

    def __init__(
        self,
        dry_run: bool = False,
        force_mode: str = "auto",
        output_format: str = "text",
        session_name: str | None = None,
        headless: bool = False,
        audit_log_path: str | None = None,
    ):
        self.console = Console()
        self.client: OpenRouterClient | None = None
        self.model_manager: ModelManager | None = None
        self.dry_run = dry_run
        self.force_mode = force_mode
        self.output_format = output_format
        self.session_name = session_name
        self.headless = headless
        self.audit_log_path = audit_log_path
        # Pause/resume state
        self._paused = False
        self._pause_event: asyncio.Event | None = None
        # Uninstall flag
        self._uninstall_requested = False
        # Audit logger (initialized in run_main_loop)
        self._audit = None
    
    def print_banner(self) -> None:
        """Display the MultiCode banner."""
        from ui.banners import get_banner_style, render_banner

        banner_style = get_banner_style()
        render_banner(self.console, banner_name=banner_style)
    
    def print_welcome(self) -> None:
        """Print welcome message."""
        self.console.print("\n[bold]Welcome to MultiCode![/bold]\n")
        self.console.print(
            "MultiCode is a terminal-based AI coding assistant that uses\n"
            "a dynamic multi-agent debate architecture to help you write better code.\n"
        )
        self.console.print(
            "[dim]Agents will collaborate, debate, and review each other's work[/dim]\n"
        )
    
    async def setup_api_key(self) -> bool:
        """
        Interactive API key setup with STRICT validation.
        
        Returns:
            True if API key was successfully validated and saved
        """
        self.console.print(Panel(
            "[bold]🔑 API Key Setup[/bold]\n\n"
            "MultiCode requires a VALID OpenRouter API key to function.\n"
            "Get your free API key from: [link]https://openrouter.ai/keys[/link]\n\n"
            "[yellow]Note: Your API key will be visible as you type[/yellow]",
            title="First Time Setup",
            border_style=PRIMARY_COLOR,
        ))

        try:
            while True:
                # Use regular Prompt to show the API key (for validation)
                self.console.print()
                try:
                    api_key = Prompt.ask(
                        "[bold]Enter your OpenRouter API key[/bold]",
                        default="",
                    )
                except (KeyboardInterrupt, EOFError):
                    # Handle Ctrl+C during input
                    raise KeyboardInterrupt()

                if not api_key or api_key.strip() == "":
                    self.console.print("[red]❌ API key cannot be empty[/red]")
                    continue

                api_key = api_key.strip()
                
                # Validate format (should start with sk-or-v1-)
                if not api_key.startswith("sk-or-"):
                    self.console.print("[red]❌ Invalid API key format![/red]")
                    self.console.print("[yellow]OpenRouter keys start with 'sk-or-v1-'[/yellow]")
                    self.console.print("[yellow]Get your key from: https://openrouter.ai/keys[/yellow]")
                    continue
                
                # STRICT VALIDATION: Actually test the API key
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                    transient=True,
                ) as progress:
                    task = progress.add_task("Validating API key with OpenRouter...", total=None)

                    try:
                        import requests
                        
                        self.console.print("[dim]Testing API key with OpenRouter...[/dim]")

                        response = requests.get(
                            url="https://openrouter.ai/api/v1/models",
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "HTTP-Referer": "https://github.com/multicode",
                                "X-OpenRouter-Title": "MultiCode",
                            },
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            models = data.get("data", [])
                            progress.update(task, description="✓ API key validated!", completed=True)

                            if not models:
                                self.console.print("[yellow]⚠️  API key works but no models available[/yellow]")
                            else:
                                self.console.print(f"[green]✓ API key validated! ({len(models)} models available)[/green]")

                            # Save the VALID key
                            set_api_key(api_key)
                            self.console.print(f"[dim]Settings saved to {CONFIG_DIR / 'settings.json'}[/dim]")
                            return True  # Only returns on SUCCESS
                            
                        elif response.status_code == 401:
                            progress.update(task, description="✗ Invalid API key", completed=True)
                            self.console.print(f"[red]✗ INVALID API KEY (401 Unauthorized)[/red]")
                            self.console.print("[yellow]Please check your API key at https://openrouter.ai/keys[/yellow]")
                            self.console.print("[yellow]Make sure you copied the ENTIRE key[/yellow]")
                            # DOES NOT RETURN - forces user to try again
                            
                        elif response.status_code == 403:
                            progress.update(task, description="✗ Access forbidden", completed=True)
                            self.console.print(f"[red]✗ API KEY HAS NO PERMISSION (403 Forbidden)[/red]")
                            self.console.print("[yellow]This key exists but has no API access![/yellow]")
                            self.console.print("[yellow]Get a new key from: https://openrouter.ai/keys[/yellow]")
                            # DOES NOT RETURN - forces user to try again
                            
                        elif response.status_code == 429:
                            progress.update(task, description="✗ Rate limited", completed=True)
                            self.console.print(f"[red]✗ RATE LIMITED (429)[/red]")
                            self.console.print("[yellow]Too many attempts. Wait 60 seconds and try again.[/yellow]")
                            # DOES NOT RETURN - forces user to wait and try again
                            
                        else:
                            progress.update(task, description="✗ Validation failed", completed=True)
                            self.console.print(f"[red]✗ Validation failed: HTTP {response.status_code}[/red]")
                            try:
                                error_data = response.json()
                                error_msg = error_data.get("error", {}).get("message", str(error_data))
                                self.console.print(f"[dim]Server response: {error_msg}[/dim]")
                            except:
                                self.console.print(f"[dim]Server response: {response.text[:200]}[/dim]")
                            # DOES NOT RETURN - forces user to try again

                    except requests.exceptions.Timeout:
                        progress.update(task, description="✗ Timeout", completed=True)
                        self.console.print("[red]✗ Request timed out (30s)[/red]")
                        self.console.print("[yellow]Check your internet connection[/yellow]")
                        # DOES NOT RETURN - forces user to check connection and try again
                        
                    except requests.exceptions.ConnectionError as e:
                        progress.update(task, description="✗ Connection error", completed=True)
                        self.console.print("[red]✗ Cannot connect to OpenRouter![/red]")
                        self.console.print("[yellow]Check your internet connection and firewall settings[/yellow]")
                        self.console.print("\n[dim]Troubleshooting:[/dim]")
                        self.console.print("[dim]  1. Check internet: ping google.com[/dim]")
                        self.console.print("[dim]  2. Check firewall: Is Python blocked?[/dim]")
                        self.console.print("[dim]  3. Check proxy: echo %HTTP_PROXY%[/dim]")
                        # DOES NOT RETURN - forces user to fix connection and try again
                        
                    except Exception as e:
                        progress.update(task, description="✗ Error", completed=True)
                        error_msg = str(e)
                        self.console.print(f"[red]✗ Validation error: {error_msg}[/red]")
                        # DOES NOT RETURN - forces user to try again
                
                # If we reach here, validation FAILED - ask to try again
                self.console.print()
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            self.console.print("\n\n[yellow]Setup cancelled by user.[/yellow]")
            return False
        
        # Should never reach here (infinite loop until valid key)
        return False
    
    async def select_models(self, quick_test: bool = False) -> list[str]:
        """
        Interactive model selection interface with two-stage selector.

        Stage 1: Select model type (Free/Paid/Both) with arrow keys
        Stage 2: Select specific models with search and multi-select

        Args:
            quick_test: If True, auto-select default free model for testing

        Returns:
            List of selected model IDs
        """
        self.console.print("\n")
        
        # Initialize client and fetch models
        self.client = OpenRouterClient()
        self.model_manager = ModelManager(self.client)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("Fetching available models...", total=None)
            try:
                await self.model_manager.fetch_models()
                progress.update(task, description="Models loaded!", completed=True)
            except Exception as e:
                progress.update(task, description="Failed to load models", completed=True)
                self.console.print(f"[red]✗ Failed to fetch models: {e}[/red]")
                self.console.print("[yellow]Please check your internet connection and try again[/yellow]")
                return []

        models = self.model_manager.get_models()

        if not models:
            self.console.print("[red]❌ No models available from OpenRouter[/red]")
            return []

        # Quick test mode - auto-select default free model
        if quick_test:
            default_model = self.model_manager.get_default_free_model()
            if default_model:
                model_info = self.model_manager.get_model_by_id(default_model)
                self.console.print(f"\n[green]✓ Selected:[/green] {model_info.name}")
                self.console.print(f"[dim]  ID: {default_model}[/dim]\n")
                set_selected_models([default_model])
                return [default_model]
            else:
                self.console.print("[yellow]⚠ No free models available, falling back to manual selection[/yellow]\n")

        # Launch improved interactive model selector (Rich-based)
        from ui.model_selector_rich import select_models_interactive_async

        # Run the interactive selector with current selections pre-loaded
        self.console.print("\n[dim]Starting interactive model selector...[/dim]\n")
        selected_ids = await select_models_interactive_async(models, pre_selected=[])

        if not selected_ids:
            self.console.print("[yellow]⚠ No models selected, using default free model[/yellow]")
            default_model = self.model_manager.get_default_free_model()
            if default_model:
                selected_ids = [default_model]
            else:
                return []

        # Validate and save
        valid_ids = []
        for model_id in selected_ids:
            model = self.model_manager.get_model_by_id(model_id)
            if model:
                valid_ids.append(model_id)

        if valid_ids:
            set_selected_models(valid_ids)
            self.console.print(f"\n[green]✓ Selected {len(valid_ids)} model(s):[/green]")
            for model_id in valid_ids:
                model = self.model_manager.get_model_by_id(model_id)
                if model:
                    self.console.print(f"  • {model.name} [dim]({model_id})[/dim]")

        return valid_ids
    
    def _display_all_models(self, models: list[ModelInfo]) -> None:
        """Display all available models in a scrollable format."""
        self.console.print("\n[bold]All Available Models:[/bold]\n")
        
        # Group by provider
        by_provider: dict[str, list[ModelInfo]] = {}
        for model in models:
            provider = model.provider or "Other"
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(model)
        
        for provider, provider_models in sorted(by_provider.items()):
            self.console.print(f"\n[bold cyan]├─ {provider}[/bold cyan]")
            
            table = Table(box=box.SIMPLE, expand=True)
            table.add_column("Model ID", style="bold")
            table.add_column("Context")
            table.add_column("Name", style="dim")
            
            for model in provider_models[:15]:  # Limit per provider
                table.add_row(
                    model.id,
                    f"{model.context_length:,}" if model.context_length else "N/A",
                    model.name[:50] + "..." if len(model.name) > 50 else model.name,
                )
            
            self.console.print(table)
            
            if len(provider_models) > 15:
                self.console.print(f"[dim]... and {len(provider_models) - 15} more[/dim]")
        
        self.console.print()
    
    def _display_search_results(self, query: str, results: list[ModelInfo]) -> None:
        """Display search results."""
        if not results:
            self.console.print(f"[yellow]⚠ No models matching '{query}'[/yellow]")
            return
        
        self.console.print(f"\n[green]✓ Found {len(results)} model(s) matching '{query}':[/green]\n")
        
        table = Table(box=box.ROUNDED, expand=True)
        table.add_column("Model ID", style="bold")
        table.add_column("Context")
        table.add_column("Name", style="dim")
        
        for model in results[:20]:
            table.add_row(
                model.id,
                f"{model.context_length:,}" if model.context_length else "N/A",
                model.name,
            )
        
        self.console.print(table)
        if len(results) > 20:
            self.console.print(f"[dim]... and {len(results) - 20} more[/dim]")
    
    async def configure_max_agents(self) -> int:
        """
        Configure the maximum number of agents.
        
        Returns:
            The configured maximum number of agents
        """
        self.console.print("\n")
        self.console.print(Panel(
            "[bold]👥 Agent Configuration[/bold]\n\n"
            "Set the maximum number of agents that can be spawned for a task.\n"
            "More agents = more thorough review but higher API costs",
            title="Step 3",
            border_style=PRIMARY_COLOR,
        ))
        
        current_max = get_max_agents()
        self.console.print(f"[dim]Current setting: {current_max} agents[/dim]\n")
        
        while True:
            try:
                max_agents = IntPrompt.ask(
                    "[bold]Maximum number of agents[/bold]",
                    default=current_max,
                )
                
                if max_agents < 1:
                    self.console.print("[red]❌ Must be at least 1 agent[/red]")
                    continue
                
                if max_agents > MAX_AGENTS_WARNING_THRESHOLD:
                    self.console.print("\n" + Panel(
                        f"[yellow]⚠️  WARNING: You've set {max_agents} agents[/yellow]\n\n"
                        f"This will significantly increase:\n"
                        f"  • API costs (each agent makes multiple requests)\n"
                        f"  • Context window usage\n"
                        f"  • Response time\n\n"
                        f"Recommended: 3-5 agents for most tasks",
                        border_style="yellow",
                    ))
                    
                    if not Confirm.ask("Continue with this setting?"):
                        continue
                
                set_max_agents(max_agents)
                self.console.print(f"[green]✓ Maximum agents set to {max_agents}[/green]")
                return max_agents
                
            except ValueError:
                self.console.print("[red]❌ Please enter a valid number[/red]")
    
    def print_setup_complete(self, models: list[str], max_agents: int) -> None:
        """Print setup completion summary."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold green]✓ Setup Complete![/bold green]\n\n"
            f"Configuration Summary:\n"
            f"  • Models: {len(models)} selected\n"
            f"  • Max Agents: {max_agents}\n"
            f"  • Config: ~/.multicode/config.json\n\n"
            f"[bold]Ready to start coding![/bold]\n"
            f"Type your coding task to begin.",
            title=APP_NAME,
            border_style=SUCCESS_COLOR,
            box=box.DOUBLE,
        ))
    
    async def run_setup(self) -> bool:
        """
        Run the complete setup flow.

        Returns:
            True if setup completed successfully
        """
        self.print_banner()
        self.print_welcome()

        # Step 1: API Key
        if not await self.setup_api_key():
            self.console.print("\n[yellow]Setup cancelled. Run 'multicode' again when ready.[/yellow]")
            return False

        # Step 2: Model Selection (direct to interactive selector)
        selected_models = await self.select_models(quick_test=False)
        if not selected_models:
            self.console.print("\n[red]Setup failed: No models selected[/red]")
            return False

        # Step 3: Max Agents
        max_agents = await self.configure_max_agents()

        # Summary
        self.print_setup_complete(selected_models, max_agents)

        return True
    
    async def run_main_loop(self) -> None:
        """
        Main application loop after setup.
        Handles user input and orchestrates multi-agent collaboration.
        """
        from config import get_max_agents, get_selected_models
        from tools.filesystem import FileSystemTools
        
        # Ensure client and model_manager are initialized
        if not self.client:
            self.client = OpenRouterClient()
        if not self.model_manager:
            self.model_manager = ModelManager(self.client)
            await self.model_manager.fetch_models()
        
        # Get configuration
        selected_models = get_selected_models()
        max_agents = get_max_agents()
        
        # Initialize filesystem tools
        filesystem = FileSystemTools(dry_run=self.dry_run)

        if self.dry_run:
            self.console.print("\n[bold yellow]🔍 DRY-RUN MODE: Files will be previewed but not written![/bold yellow]\n")

        # Initialize audit logger
        session_id = self.session_name or f"mc-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if self.audit_log_path or self.force_mode == "audit":
            from pathlib import Path as StdPath

            from core.audit import create_audit_logger

            log_path = StdPath(self.audit_log_path) if self.audit_log_path else StdPath.home() / ".multicode" / "audit.jsonl"
            self._audit = create_audit_logger(session_id, log_path=log_path)
            self.console.print(f"[dim]🔒 Audit logging enabled: {log_path}[/dim]\n")
        
        # PRE-FLIGHT CHECK: Verify API key is still valid
        self.console.print("\n[dim]Verifying API key...[/dim]")
        try:
            import requests
            response = requests.get(
                url="https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {self.client.api_key}",
                    "HTTP-Referer": "https://github.com/multicode",
                    "X-OpenRouter-Title": "MultiCode",
                },
                timeout=15
            )
            if response.status_code == 401:
                self.console.print("[red]✗ API key is no longer valid![/red]")
                self.console.print("[yellow]Please run 'python main.py --reset' to enter a new key[/yellow]")
                return
            elif response.status_code == 200:
                self.console.print("[green]✓ API key verified[/green]\n")
            else:
                self.console.print(f"[yellow]⚠ API returned HTTP {response.status_code}[/yellow]\n")
        except Exception as e:
            self.console.print(f"[yellow]⚠ Could not verify API key: {e}[/yellow]")
            self.console.print("[dim]Continuing anyway...[/dim]\n")

        self.console.print("\n[bold green]✓ MultiCode Ready![/bold green]")
        self.console.print(f"[dim]Models: {len(selected_models)} | Max Agents: {max_agents}[/dim]\n")
        
        # Show current working directory (from main module)
        try:
            from main import ORIGINAL_CWD
            cwd = ORIGINAL_CWD
        except ImportError:
            import os
            cwd = os.getcwd()
        
        self.console.print(f"[dim]Working Directory: {cwd}[/dim]")
        self.console.print("[dim]Type your coding task or /help for commands[/dim]\n")
        
        while True:
            try:
                # Get user input
                try:
                    user_input = Prompt.ask(
                        "[bold cyan]multicode[/bold cyan]",
                        default="",
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    # Handle Ctrl+C during input
                    self.console.print("\n\n[yellow]Interrupted. Type /quit to exit.[/yellow]")
                    continue
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower().split()[0]
                    
                    if command in ["/quit", "/exit", "/q"]:
                        self.console.print("\n[yellow]Goodbye![/yellow]")
                        return  # Exit main loop
                    elif command == "/help":
                        self._show_help()
                    elif command == "/models":
                        await self._change_models()
                        selected_models = get_selected_models()
                    elif command == "/agents":
                        await self._change_agents()
                        max_agents = get_max_agents()
                    elif command == "/pause":
                        await self._pause_task()
                        continue
                    elif command == "/continue":
                        await self._continue_task()
                        continue
                    elif command == "/pwd":
                        await self._show_working_directory()
                        continue
                    elif command in ("/uninstall", "/uninstall-wipe"):
                        wipe_mode = command == "/uninstall-wipe"
                        if await self._uninstall(wipe=wipe_mode):
                            # Uninstall successful, exit main loop
                            return
                        continue
                    elif command == "/reset":
                        self.console.print("\n[yellow]To reset ALL settings and API key:[/yellow]")
                        self.console.print("  [cyan]multicode --reset[/cyan]")
                        self.console.print("\n[dim]This will remove:[/dim]")
                        self.console.print("  [dim]• API key[/dim]")
                        self.console.print("  [dim]• Selected models[/dim]")
                        self.console.print("  [dim]• All settings[/dim]")
                        self.console.print("  [dim]• Cached data[/dim]")
                    elif command == "/clear":
                        self.console.clear()
                    elif command == "/banner":
                        await self._change_banner()
                    elif command == "/mode":
                        await self._change_mode()
                    elif command == "/memory":
                        await self._handle_memory_command(user_input)
                    else:
                        self.console.print(f"[yellow]Unknown command: {command}[/yellow]")
                    continue
                
                # Process coding task
                # Route based on task complexity (fast heuristic pre-filter)
                from config import get_settings
                from core.audit import AuditAction
                from core.task_classifier import is_simple_task_quick

                settings = get_settings()

                # CLI --mode flag overrides settings
                force_mode = self.force_mode if self.force_mode != "auto" else settings.routing.force_mode
                smart_routing = settings.routing.enable_smart_routing

                # Determine task complexity
                if force_mode == "simple":
                    is_simple = True
                    classification = "simple"
                elif force_mode == "complex":
                    is_simple = False
                    classification = "complex"
                elif force_mode == "audit":
                    is_simple = False
                    classification = "audit"
                elif not smart_routing:
                    is_simple = False
                    classification = "complex"
                else:
                    is_simple = is_simple_task_quick(user_input)
                    classification = "simple" if is_simple else "complex"

                # Log classification to audit trail
                if self._audit:
                    self._audit.log(
                        AuditAction.TASK_CLASSIFIED,
                        detail={"input": user_input[:100], "classification": classification, "force_mode": force_mode},
                    )

                if is_simple:
                    # Simple query: direct single-model response, no multi-agent
                    await self._process_simple_query(
                        user_input,
                        selected_models,
                    )
                else:
                    # Complex task: full multi-agent workflow
                    await self._process_task(
                        user_input,
                        selected_models,
                        max_agents,
                        filesystem,
                    )

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Task interrupted. Type /quit to exit.[/yellow]")
            except SystemExit:
                # Allow clean exits (e.g., from uninstall)
                raise
            except Exception as e:
                # Use markup=False to prevent exception message from being parsed as markup
                self.console.print(f"\nError: {e}", style="red", markup=False)
                import logging
                logging.exception("Error in main loop")
    
    def _show_help(self) -> None:
        """Show help commands."""
        self.console.print("\n[bold]Commands:[/bold]")
        table = Table(box=box.SIMPLE)
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        table.add_row("/quit, /exit", "Exit MultiCode")
        table.add_row("/help", "Show this help")
        table.add_row("/models", "Change selected models")
        table.add_row("/agents", "Change max agents")
        table.add_row("/pause", "Pause current AI task")
        table.add_row("/continue", "Resume paused task")
        table.add_row("/pwd", "Show working directory")
        table.add_row("/clear", "Clear screen")
        table.add_row("/banner", "Change ASCII banner theme")
        table.add_row("/mode", "Set workflow mode (auto/simple/complex)")
        table.add_row("/memory", "Manage agent memory (list/show/clear)")
        table.add_row("/reset", "Reset ALL settings (removes API key)")
        table.add_row("/uninstall", "Uninstall MultiCode (keep settings)")
        table.add_row("/uninstall-wipe", "Full wipe — removes settings, API keys, audit logs")
        self.console.print(table)
        self.console.print("\n[dim]Launch with --dry-run to preview file writes without executing them[/dim]\n")
    
    async def _show_working_directory(self) -> None:
        """Show the current working directory."""
        try:
            from main import ORIGINAL_CWD
            cwd = ORIGINAL_CWD
        except ImportError:
            import os
            cwd = os.getcwd()
        
        self.console.print("\n[bold]Working Directory:[/bold]")
        self.console.print(f"  [cyan]{cwd}[/cyan]")
        self.console.print(f"  [dim]This is where MultiCode is installed[/dim]")
        self.console.print(f"  [dim]File operations use paths relative to your current location[/dim]\n")
    
    async def _uninstall(self, wipe: bool = False) -> bool:
        """
        Uninstall MultiCode with enterprise-grade safety and audit logging.

        Args:
            wipe: If True, remove all user data including settings and API keys.

        Returns:
            True if uninstall was performed, False if cancelled
        """
        from core.uninstall import (
            UninstallManager,
            get_uninstall_summary,
        )

        self.console.print()

        if wipe:
            # Full wipe mode — explicit string confirmation required
            self.console.print(Panel(
                "[bold red]⚠️  FULL WIPE MODE ⚠️[/bold red]\n\n"
                "This will [bold]PERMANENTLY DELETE EVERYTHING[/bold]:\n"
                "  • MultiCode Python package\n"
                "  • Entry point scripts (multicode, multicode.exe)\n"
                "  • User settings and API keys (~/.multicode/)\n"
                "  • Session state and audit logs\n\n"
                "[red]This action CANNOT be undone.[/red]",
                title="FULL WIPE",
                border_style="red",
            ))
            self.console.print()
            confirm = Prompt.ask(
                "[bold red]Type 'WIPE-CONFIRM' to proceed[/bold red]",
            ).strip()

            if confirm != "WIPE-CONFIRM":
                self.console.print("\n[yellow]Uninstall cancelled.[/yellow]\n")
                return False

            mode = "wipe"
        else:
            # Standard uninstall — keep settings by default
            self.console.print(Panel(
                "[bold yellow]⚠️  Standard Uninstall[/bold yellow]\n\n"
                "This will remove the MultiCode application.\n\n"
                "[green]What will be removed:[/green]\n"
                "  • Python package (multicode)\n"
                "  • Entry point scripts (multicode, multicode.exe)\n"
                "  • Build artifacts (.egg-info, __pycache__)\n\n"
                "[green]What will be kept:[/green]\n"
                "  • User settings and API key (~/.multicode/)\n"
                "  • Source code directory (if running from repo)\n"
                "  • Python dependencies (rich, requests, etc.)",
                title="UNINSTALL",
                border_style="yellow",
            ))
            self.console.print()

            keep = Confirm.ask(
                "[bold]Keep your settings and API key?[/bold]",
                default=True,
            )
            if not keep:
                # User wants to wipe settings — upgrade to wipe mode
                self.console.print("\n[dim]Upgrading to full wipe mode...[/dim]\n")
                mode = "wipe"
            else:
                mode = "standard"

        # Execute uninstall via manager
        audit_mgr = getattr(self, "_audit", None)
        mgr = UninstallManager(mode=mode, audit_logger=audit_mgr)
        plan = mgr.create_plan()
        result = mgr.execute(plan)

        # Display results
        self.console.print(get_uninstall_summary(result))

        if result.errors:
            self.console.print("\n[yellow]Some items could not be removed. See warnings above.[/yellow]")
            self.console.print("[dim]Exit code: 1 (partial failure)[/dim]")
        else:
            # Spawn a detached cleanup process to delete locked exe files after we exit
            self._cleanup_locked_exes(mgr)

            # Show success panel with countdown
            self.console.print()
            self._countdown_and_exit(5)

        return True

    def _cleanup_locked_exes(self, mgr: "UninstallManager") -> None:
        """Spawn a hidden background process to delete locked files after we exit."""
        import subprocess
        import sys
        import tempfile

        if not mgr._locked_paths and not mgr._renamed_paths:
            return
        if sys.platform != "win32":
            return

        paths_to_clean = list(mgr._locked_paths) + list(mgr._renamed_paths)

        # Build a PowerShell script for cleanup (more reliable timing than batch)
        ps_lines = [
            "# MultiCode cleanup - runs after main process exits",
            "Start-Sleep -Seconds 10",  # Wait for process to fully exit
        ]
        for path_str in paths_to_clean:
            escaped = path_str.replace("'", "''")
            ps_lines.append(f"if (Test-Path '{escaped}') {{ Remove-Item -LiteralPath '{escaped}' -Recurse -Force -ErrorAction SilentlyContinue }}")
            # Also check renamed version
            renamed = path_str + ".__mc_uninstall"
            ps_lines.append(f"if (Test-Path '{renamed}') {{ Remove-Item -LiteralPath '{renamed}' -Recurse -Force -ErrorAction SilentlyContinue }}")

        # Clean up egg-info directories
        import sysconfig
        site_packages = sysconfig.get_path("purelib")
        escaped_site = site_packages.replace("'", "''")
        ps_lines.append(f"Get-ChildItem '{escaped_site}' -Directory -Filter '*multicode*' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue")
        ps_lines.append(f"Get-ChildItem '{escaped_site}' -Directory -Filter '~*multicode*' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue")

        ps_content = "\n".join(ps_lines)

        try:
            ps_path = Path(tempfile.gettempdir()) / "multicode_cleanup.ps1"
            ps_path.write_text(ps_content, encoding="utf-8")

            # Spawn hidden PowerShell process
            creation_flags = 0x08000000  # CREATE_NO_WINDOW
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(ps_path)],
                creationflags=creation_flags,
            )
        except Exception as e:
            logger.debug("Failed to spawn cleanup process: %s", e)

    def _countdown_and_exit(self, seconds: int) -> None:
        """Display a countdown and exit the application."""
        import os
        import time

        # Show success panel
        self.console.print(
            Panel(
                "[bold green]MultiCode has been successfully uninstalled![/bold green]\n\n"
                "The application and all packages have been removed.",
                title="Uninstall Complete",
                border_style="green",
            )
        )

        # Countdown in main thread
        for i in range(seconds, 0, -1):
            self.console.print(f"[dim]Closing in {i} second{'s' if i > 1 else ''}...[/dim]")
            time.sleep(1)

        os._exit(0)
    
    async def _arrow_key_select(self, options: list[str], default_index: int = 0) -> str:
        """
        Show arrow key selection UI using Rich Live display.
        
        Args:
            options: List of options to select from
            default_index: Default selected index
            
        Returns:
            Selected option
        """
        try:
            from readchar import key, readkey
        except ImportError:
            # Fallback to simple prompt if readchar not available
            options_str = "/".join(options)
            return Prompt.ask(f"Select ({options_str})", default=options[default_index])
        
        selected_index = default_index
        
        def make_selection_text() -> Text:
            """Create Text object for selection display."""
            from rich.text import Text
            result = Text()
            for i, option in enumerate(options):
                if i > 0:
                    result.append("  ")
                if i == selected_index:
                    result.append(f" {option} ", style="reverse bold")
                else:
                    result.append(f" {option} ", style="dim")
            return result
        
        # Use Live display for clean updates
        
        with Live(
            make_selection_text(),
            console=self.console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            while True:
                # Read key
                k = readkey()
                
                if k == key.LEFT:
                    selected_index = (selected_index - 1) % len(options)
                    live.update(make_selection_text())
                elif k == key.RIGHT:
                    selected_index = (selected_index + 1) % len(options)
                    live.update(make_selection_text())
                elif k in (key.ENTER, '\r', '\n'):
                    return options[selected_index]
                elif k == key.BACKSPACE:
                    return options[selected_index]
    
    async def _pause_task(self) -> None:
        """Pause the current AI task."""
        if self._paused:
            self.console.print("[yellow]⚠️  Task is already paused[/yellow]")
            return
        
        self._paused = True
        self._pause_event = asyncio.Event()
        self.console.print("\n[bold yellow]⏸️  Task PAUSED[/bold yellow]")
        self.console.print("[dim]Type /continue to resume[/dim]\n")
    
    async def _continue_task(self) -> None:
        """Resume a paused AI task."""
        if not self._paused:
            self.console.print("[yellow]⚠️  No paused task[/yellow]")
            return
        
        self._paused = False
        if self._pause_event:
            self._pause_event.set()
            self._pause_event = None
        self.console.print("\n[bold green]▶️  Task RESUMED[/bold green]\n")
    
    async def _check_pause(self) -> None:
        """Check if task is paused and wait if necessary."""
        if self._paused and self._pause_event:
            self.console.print("\n[dim]Task is paused. Type /continue to resume.[/dim]\n")
            await self._pause_event.wait()
            self.console.print("\n[dim]Task resumed.[/dim]\n")
    
    async def _change_models(self) -> None:
        """Re-run model selection with current selections pre-loaded."""
        from config import get_selected_models, set_selected_models
        from ui.model_selector_rich import select_models_interactive_async

        self.console.print("\n[bold]Model Reselection[/bold]\n")

        # Ensure client is initialized
        if not self.client:
            self.client = OpenRouterClient()
        if not self.model_manager:
            self.model_manager = ModelManager(self.client)
            await self.model_manager.fetch_models()

        # Get current selections
        current_models = get_selected_models()
        self.console.print(f"[dim]Current models: {len(current_models)}[/dim]")
        for model_id in current_models:
            model = self.model_manager.get_model_by_id(model_id)
            if model:
                self.console.print(f"  • {model.name} [dim]({model_id})[/dim]")

        self.console.print()

        # Fetch fresh models
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("Fetching models...", total=None)
            try:
                await self.model_manager.fetch_models(force_refresh=True)
                progress.update(task, description="Models refreshed!", completed=True)
            except Exception as e:
                progress.update(task, description="Failed", completed=True)
                self.console.print(f"[red]✗ Failed to fetch models: {e}[/red]")
                return

        # Run interactive selector with pre-selected models
        models = self.model_manager.get_models()
        selected_ids = await select_models_interactive_async(models, pre_selected=current_models)

        if selected_ids:
            set_selected_models(selected_ids)
            self.console.print(f"\n[green]✓ Updated model selection ({len(selected_ids)} models)[/green]")
            for model_id in selected_ids:
                model = self.model_manager.get_model_by_id(model_id)
                if model:
                    self.console.print(f"  • {model.name} [dim]({model_id})[/dim]")
        else:
            self.console.print("[yellow]⚠ No models selected, keeping previous selection[/yellow]")

        self.console.print()
    
    async def _change_agents(self) -> None:
        """
        Interactive agent limit configuration.

        Prompts the user for a new agent count. Values above the
        recommended maximum (5) trigger a warning but are accepted.
        Updates both the active session and persisted config, and
        emits an audit event if audit logging is enabled.
        """
        from config import get_max_agents, get_settings, set_max_agents

        current = get_max_agents()
        settings = get_settings()
        min_val = settings.agent.min_agents
        recommended = getattr(settings.agent, "recommended_max", 5)

        self.console.print()
        self.console.print(f"[dim]ℹ️  Current agent limit: {current} (recommended max: {recommended})[/dim]\n")

        for _attempt in range(3):
            try:
                raw = Prompt.ask(
                    f"How many agents would you like to use? (min {min_val}, recommended max {recommended})",
                    default=str(current),
                ).strip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]✓ Operation cancelled. Agent limit unchanged.[/yellow]\n")
                return

            if not raw:
                new_val = current
                break

            try:
                new_val = int(raw)
            except ValueError:
                self.console.print(f"[red]✗ Invalid input: please enter a whole number[/red]\n")
                continue

            if new_val < min_val:
                self.console.print(f"[red]✗ Value too low: minimum is {min_val}[/red]\n")
                continue

            # Warn if above recommended but accept anyway
            if new_val > recommended:
                self.console.print(
                    f"\n[yellow]⚠️  Warning: {new_val} agents exceeds the recommended maximum ({recommended}).[/yellow]"
                )
                self.console.print("[yellow]   This may significantly increase API costs and response times.[/yellow]\n")
                if not Confirm.ask("Continue with this value?", default=False):
                    continue

            break
        else:
            self.console.print(f"[yellow]⚠ Too many invalid attempts. Agent limit remains {current}.[/yellow]\n")
            return

        # Save to config
        try:
            success = set_max_agents(new_val)
        except PermissionError:
            self.console.print(f"\n[red]⚠️  Could not save configuration: permission denied[/red]")
            self.console.print("[dim]💡 Tip: Check file permissions on ~/.multicode/settings.json[/dim]\n")
            settings.agent.max_agents = new_val
            self.console.print(f"[yellow]⚠️  Change applied to current session only[/yellow]\n")
            return
        except OSError as e:
            self.console.print(f"\n[red]⚠️  Could not save configuration: {e}[/red]\n")
            settings.agent.max_agents = new_val
            self.console.print(f"[yellow]⚠️  Change applied to current session only[/yellow]\n")
            return

        if not success:
            self.console.print("[red]✗ Failed to save configuration.[/red]\n")
            return

        # Audit event
        if getattr(self, "_audit", None):
            try:
                from core.audit import AuditAction
                self._audit.log(
                    AuditAction.CONFIG_CHANGED,
                    detail={
                        "field": "agent.max_agents",
                        "old_value": current,
                        "new_value": new_val,
                        "source": "cli_command:/agents",
                    },
                )
            except Exception:
                pass

        self.console.print(f"\n[green]✓ Agent limit updated to {new_val}[/green]")
        self.console.print("[green]✓ Configuration saved[/green]")
        self.console.print("[dim]✓ New limit applies immediately to future tasks[/dim]\n")

    async def _change_banner(self) -> None:
        """Change the ASCII banner style."""
        from ui.banners import (
            get_banner_names,
            get_banner_style,
            render_banner,
            set_banner_style,
        )

        available = get_banner_names()
        current = get_banner_style()

        self.console.print("\n[bold]Available Banner Themes:[/bold]")
        for i, name in enumerate(available, 1):
            marker = " ← current" if name == current else ""
            self.console.print(f"  {i}. [cyan]{name}[/cyan]{marker}")

        self.console.print()
        choice = Prompt.ask(
            "Select banner (number or name)",
            default=current,
        ).strip().lower()

        # Try number selection first
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                choice = available[idx]
        except ValueError:
            pass

        if choice not in available:
            self.console.print(f"[red]Invalid banner: {choice}[/red]\n")
            return

        set_banner_style(choice)
        self.console.print(f"\n[green]✓ Banner changed to '{choice}'[/green]\n")

        # Preview the new banner
        render_banner(self.console, banner_name=choice)

    async def _change_mode(self) -> None:
        """Change the workflow routing mode."""
        from config import get_settings, save_settings

        current = get_settings().routing.force_mode

        self.console.print("\n[bold]Workflow Routing Mode:[/bold]")
        self.console.print("  [cyan]auto[/cyan]     - Auto-detect simple vs complex (default)")
        self.console.print("  [cyan]simple[/cyan]   - Always use single-agent direct response")
        self.console.print("  [cyan]complex[/cyan]  - Always use full multi-agent debate")
        self.console.print(f"\n  Current: [bold green]{current}[/bold green]\n")

        choice = Prompt.ask(
            "Set mode",
            choices=["auto", "simple", "complex"],
            default=current,
        ).strip().lower()

        if choice not in ("auto", "simple", "complex"):
            self.console.print(f"[red]Invalid mode: {choice}[/red]\n")
            return

        settings = get_settings()
        settings.routing.force_mode = choice
        save_settings(settings)

        self.console.print(f"\n[green]✓ Workflow mode set to '{choice}'[/green]\n")

    async def _handle_memory_command(self, full_input: str) -> None:
        """Handle /memory subcommands: list, show <agent>, clear <agent>."""
        from core.agent_memory import get_memory_store

        parts = full_input.strip().split()
        subcommand = parts[1].lower() if len(parts) > 1 else ""

        if subcommand == "list":
            store = get_memory_store()
            memories = store.list_all_memories()
            if not memories:
                self.console.print("\n[yellow]No agent memories found.[/yellow]\n")
                return
            self.console.print("\n[bold]Agent Memories:[/bold]")
            for m in memories:
                self.console.print(
                    f"  • [cyan]{m['agent_name']}[/cyan] — "
                    f"{m['total_sessions']} sessions, {m['total_turns']} turns, "
                    f"last: {m['last_updated'][:19]}"
                )
            self.console.print()

        elif subcommand == "show" and len(parts) > 2:
            agent_name = " ".join(parts[2:])
            store = get_memory_store()
            summary = store.get_memory_summary(agent_name)
            if not summary or summary.get("total_sessions", 0) == 0:
                self.console.print(f"\n[yellow]No memory found for '{agent_name}'[/yellow]\n")
                return
            self.console.print(f"\n[bold]Memory: {summary['agent_name']}[/bold]")
            self.console.print(f"  Sessions: {summary['total_sessions']}")
            self.console.print(f"  Total turns: {summary['total_turns']}")
            self.console.print(f"  Conversation entries: {summary['conversation_entries']}")
            self.console.print(f"  Key learnings: {summary['key_learnings']}")
            if summary.get("files_touched"):
                self.console.print(f"  Files touched: {', '.join(summary['files_touched'][:5])}")
            self.console.print()

        elif subcommand == "clear" and len(parts) > 2:
            agent_name = " ".join(parts[2:])
            store = get_memory_store()
            if store.clear_memory(agent_name):
                self.console.print(f"\n[green]✓ Memory cleared for '{agent_name}'[/green]\n")
            else:
                self.console.print(f"\n[yellow]No memory found for '{agent_name}'[/yellow]\n")

        else:
            self.console.print("\n[bold]Memory Commands:[/bold]")
            self.console.print("  /memory list           - List all agent memories")
            self.console.print("  /memory show <agent>   - Show memory summary for agent")
            self.console.print("  /memory clear <agent>  - Clear agent memory\n")

    async def _process_task(
        self,
        user_prompt: str,
        model_ids: list[str],
        max_agents: int,
        filesystem: FileSystemTools,
    ) -> None:
        """
        Process with ULTIMATE Multi-Agent System.
        
        Features:
        - Full AI control (agents, workflow, voting)
        - CREATE, READ, EDIT file operations
        - Complete visibility (see all thoughts/discussions)
        - Voting system for disagreements
        - Comprehensive logging
        """
        from core.ultimate_multi_agent import UltimateMultiAgentSystem
        
        self.console.print()
        
        if not self.client:
            self.client = OpenRouterClient()
        
        model_id = model_ids[0] if model_ids else "nvidia/nemotron-3-super-120b-a12b:free"
        
        # Create ultimate system
        mas = UltimateMultiAgentSystem(self.client, model_id, filesystem, audit_logger=self._audit)
        
        self.console.print("[bold cyan]🚀 Ultimate Multi-Agent System Active[/bold cyan]\n")
        self.console.print("[dim]Full AI control with complete visibility...[/dim]\n")
        
        # Stream the ultimate session
        async for event in mas.stream_ultimate_session(user_prompt):
            event_type = event.get('type')
            
            if event_type == 'info':
                self.console.print(f"\n[bold yellow]ℹ️  {event['content']}[/bold yellow]\n")
            
            elif event_type == 'directory':
                from rich.panel import Panel
                self.console.print(Panel(
                    event['content'],
                    title="📂 Directory",
                    border_style="blue",
                ))
            
            elif event_type == 'team_revealed':
                agents = event.get('agents', [])
                workflow = event.get('workflow', [])
                
                self.console.print("\n[bold magenta]👥 AI-Created Team:[/bold magenta]")
                for agent in agents:
                    self.console.print(f"  • [cyan]{agent['name']}[/cyan]: {agent['role'][:80]}...")
                
                self.console.print("\n[bold magenta]📋 AI-Created Workflow:[/bold magenta]")
                for i, step in enumerate(workflow, 1):
                    agents_str = ", ".join(step.get('agents', []))
                    self.console.print(f"  {i}. {step.get('task', 'Task')} → [dim]{agents_str}[/dim]")
                self.console.print()
            
            elif event_type == 'workflow_step':
                step_num = event.get('step_number', 0)
                total = event.get('total_steps', 0)
                step = event.get('step', {})
                
                self.console.print(f"\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
                self.console.print(f"[bold cyan]Step {step_num}/{total}: {step.get('task', 'Task')}[/bold cyan]")
                self.console.print(f"[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
            
            elif event_type == 'agent_thinking':
                agent_name = event.get('agent', 'Unknown')
                self.console.print(f"\n[bold magenta]🤔 {agent_name} is thinking...[/bold magenta]\n")
            
            elif event_type == 'agent_speaking':
                agent_name = event.get('agent', 'Unknown')
                role = event.get('role', 'Specialist')
                content = event.get('content', '')
                
                self.console.print(f"\n[bold magenta]👨‍💻 {agent_name}[/bold magenta] [dim]({role})[/dim]")
                
                from rich.panel import Panel
                self.console.print(Panel(
                    content[:1000] + ("..." if len(content) > 1000 else ""),
                    border_style="magenta",
                ))
            
            elif event_type == 'creating_file':
                filename = event.get('file', 'unknown')
                self.console.print(f"\n[bold green]📄 Creating: {filename}[/bold green]")
            
            elif event_type == 'file_created':
                filepath = event.get('file', 'unknown')
                self.console.print(f"[green]✓ Created: {filepath}[/green]\n")
            
            elif event_type == 'editing_file':
                filename = event.get('file', 'unknown')
                lines = event.get('lines', '')
                self.console.print(f"\n[bold blue]✏️  Editing: {filename} (lines {lines})[/bold blue]")
            
            elif event_type == 'file_edited':
                filepath = event.get('file', 'unknown')
                lines = event.get('lines', '')
                self.console.print(f"[blue]✓ Edited: {filepath} (lines {lines})[/blue]\n")
            
            elif event_type == 'reading_file':
                filename = event.get('file', 'unknown')
                self.console.print(f"\n[bold yellow]📖 Reading: {filename}[/bold yellow]")
            
            elif event_type == 'file_read':
                filepath = event.get('file', 'unknown')
                content = event.get('content', '')
                from rich.panel import Panel
                self.console.print(Panel(
                    content,
                    title=f"📄 {filepath}",
                    border_style="yellow",
                ))
            
            elif event_type == 'file_error':
                filename = event.get('file', 'unknown')
                error = event.get('error', 'Unknown error')
                self.console.print(f"[red]✗ Error with {filename}: {error}[/red]\n")
            
            elif event_type == 'voting_results':
                votes = event.get('votes', {})
                approve = event.get('approve', 0)
                reject = event.get('reject', 0)
                modify = event.get('modify', 0)
                
                self.console.print("\n[bold]🗳️  Voting Results:[/bold]")
                for agent, vote in votes.items():
                    vote_emoji = '✅' if vote == 'APPROVE' else '❌' if vote == 'REJECT' else '🔧'
                    self.console.print(f"  {vote_emoji} {agent}: {vote}")
                self.console.print(f"\n[dim]Approve: {approve} | Reject: {reject} | Modify: {modify}[/dim]\n")
            
            elif event_type == 'done':
                content = event.get('content', '')
                self.console.print(f"\n[bold green]✅ {content}[/bold green]\n")
        
        # Final summary
        self.console.print("\n[bold]═══════════════════════════════════════[/bold]")
        self.console.print("[bold green]✓ Ultimate Multi-Agent Session Complete![/bold green]")
        self.console.print("[bold]═══════════════════════════════════════[/bold]\n")
        
        if mas.files_created:
            self.console.print(f"[bold]Files created:[/bold] {len(mas.files_created)}")
            for f in mas.files_created:
                self.console.print(f"  • {f}")
        
        if mas.files_modified:
            self.console.print(f"\n[bold]Files modified:[/bold] {len(mas.files_modified)}")
            for f in mas.files_modified:
                self.console.print(f"  • {f}")
        
        if not mas.files_created and not mas.files_modified:
            self.console.print("[yellow]⚠️  No files created or modified[/yellow]")

        # Show dry-run summary if in dry-run mode
        if self.dry_run and filesystem.preview_log:
            self.console.print("\n[bold yellow]🔍 DRY-RUN SUMMARY:[/bold yellow]")
            self.console.print(f"[dim]{len(filesystem.preview_log)} file operation(s) would have been performed:[/dim]\n")
            for i, entry in enumerate(filesystem.preview_log, 1):
                op_color = "green" if entry["operation"] == "CREATE" else "blue"
                self.console.print(
                    f"  {i}. [{op_color}]{entry['operation']}[/] {entry['path']} "
                    f"[dim]({entry['content_length']} chars)[/dim]"
                )
                self.console.print(f"     [dim]Preview: {entry['content_preview']}[/dim]")
            self.console.print()
            filesystem.clear_preview()

        self.console.print()
    
    async def _process_simple_query(self, user_prompt: str, model_ids: list[str]) -> None:
        """
        Process simple queries (greetings, simple questions) with direct response.
        Also handles file creation when code is provided.

        Args:
            user_prompt: The user's query
            model_ids: List of model IDs to use
        """
        import logging
        import re

        from api.openrouter import ChatMessage, OpenRouterClient
        
        logger = logging.getLogger(__name__)
        self.console.print()

        # Use first available model or default
        model_id = model_ids[0] if model_ids else "google/gemma-2-9b-it:free"

        with self.console.status("[dim]Thinking...[/dim]", spinner="dots") as status:
            try:
                # Ensure client is initialized
                if not self.client:
                    self.client = OpenRouterClient()

                # Check API key
                if not self.client.api_key:
                    self.console.print("[red]✗ Error: No API key configured[/red]")
                    self.console.print("[yellow]Please run 'multicode --reset' to set up your API key[/yellow]")
                    return

                status.update("[dim]Contacting OpenRouter API...[/dim]")
                logger.info(f"Sending request to {model_id}: {user_prompt[:50]}...")

                response = await self.client.chat_completion(
                    messages=[ChatMessage(role="user", content=user_prompt)],
                    model=model_id,
                    temperature=0.7,
                    max_tokens=2000,
                )

                logger.info(f"API response: content_length={len(response.content) if response.content else 0}")

                status.update("[green]✓ Response received[/green]")

                # Check if response has content
                if not response.content or not response.content.strip():
                    self.console.print("[yellow]⚠️  AI returned empty response[/yellow]")
                    self.console.print("[dim]This can happen with certain models. Try again or use a different model.[/dim]")
                    self.console.print(f"[dim]Model used: {model_id}[/dim]")
                    return

                # Check if response contains code blocks that should be files
                content = response.content
                files_created = []
                
                # Pattern to match code blocks with file paths: ```language path/to/file.ext
                file_pattern = re.compile(r'```(\w+)\s+([^\s`]+)\n(.*?)```', re.DOTALL | re.IGNORECASE)
                
                # Pattern to match code blocks WITHOUT file paths (just language)
                simple_code_pattern = re.compile(r'```(\w+)\n(.*?)```', re.DOTALL | re.IGNORECASE)
                
                # First try to find code blocks with file paths
                matches = list(file_pattern.finditer(content))
                
                # If no file paths found but there are code blocks, suggest file creation
                if not matches:
                    simple_matches = list(simple_code_pattern.finditer(content))
                    if simple_matches and len(simple_matches) <= 3:
                        # Found code blocks without file paths - offer to create files
                        self.console.print(Panel(
                            content,
                            title=f"💬 Response",
                            border_style="green",
                            subtitle=f"Model: {model_id}",
                        ))
                        
                        # Check if it looks like a complete file
                        for i, match in enumerate(simple_matches):
                            lang = match.group(1)
                            code = match.group(2).strip()
                            
                            # Suggest file extension based on language
                            ext_map = {
                                'html': 'html', 'javascript': 'js', 'js': 'js',
                                'python': 'py', 'py': 'py', 'css': 'css',
                                'json': 'json', 'yaml': 'yaml', 'yml': 'yml',
                            }
                            ext = ext_map.get(lang.lower(), 'txt')
                            
                            # Auto-create file in current directory
                            filename = f"output_{i+1}.{ext}"
                            
                            from tools.filesystem import FileSystemTools
                            fs = FileSystemTools()
                            
                            try:
                                written_path = await fs.write_file(filename, code)
                                files_created.append(written_path)
                                
                                # Log with proper format: [HH:MM:SS] INFO CREATE File 'path' [✓]
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                import logging
                                logger = logging.getLogger('multicode.files')
                                logger.info(f"[{timestamp}] INFO CREATE File '{filename}' [✓]")
                                
                                self.console.print(f"[green]✓ Created file: {written_path}[/green]")
                            except Exception as e:
                                self.console.print(f"[yellow]⚠ Could not create file: {e}[/yellow]")
                        
                        if files_created:
                            self.console.print(f"\n[bold green]✓ Created {len(files_created)} file(s)![/bold green]")
                        return

                # Display response
                self.console.print(Panel(
                    content,
                    title=f"💬 Response",
                    border_style="green",
                    subtitle=f"Model: {model_id}",
                ))
                
                # Create files from matches
                if matches:
                    from tools.filesystem import FileSystemTools
                    fs = FileSystemTools()
                    
                    for match in matches:
                        lang = match.group(1)
                        filepath = match.group(2)
                        code = match.group(3).strip()
                        
                        try:
                            written_path = await fs.write_file(filepath, code)
                            files_created.append(written_path)
                            self.console.print(f"[green]✓ Created file: {written_path}[/green]")
                        except Exception as e:
                            self.console.print(f"[yellow]⚠ Could not create file {filepath}: {e}[/yellow]")
                    
                    if files_created:
                        self.console.print(f"\n[bold green]✓ Created {len(files_created)} file(s)![/bold green]")

            except asyncio.TimeoutError:
                self.console.print("[red]✗ Error: Request timed out (120s)[/red]")
                self.console.print("[yellow]This could be due to:[/yellow]")
                self.console.print("[dim]  • Slow internet connection[/dim]")
                self.console.print("[dim]  • OpenRouter API is busy[/dim]")
                self.console.print("[dim]  • Firewall blocking the connection[/dim]")
            except Exception as e:
                error_msg = str(e)
                logger.exception(f"Simple query error: {error_msg}")
                self.console.print(f"[red]✗ Error: {error_msg}[/red]")
                
                # Provide helpful troubleshooting
                if "Connection closed" in error_msg or "Connection refused" in error_msg:
                    self.console.print("\n[yellow]Connection Issue Detected![/yellow]")
                    self.console.print("[dim]Try these steps:[/dim]")
                    self.console.print("[dim]  1. Check your internet connection[/dim]")
                    self.console.print("[dim]  2. Try: ping openrouter.ai[/dim]")
                    self.console.print("[dim]  3. Check if firewall/antivirus is blocking Python[/dim]")
                    self.console.print("[dim]  4. Try again in a few seconds[/dim]")
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    self.console.print("\n[yellow]API Key Issue![/yellow]")
                    self.console.print("[dim]Your API key may be invalid. Run 'multicode --reset' to update it.[/dim]")
                elif "429" in error_msg or "Rate limit" in error_msg:
                    self.console.print("\n[yellow]Rate Limited![/yellow]")
                    self.console.print("[dim]Too many requests. Wait a minute and try again.[/dim]")
        
        self.console.print()


async def main():
    """Main entry point for the CLI."""
    cli = MultiCodeCLI()
    
    # Check if already setup
    from config import get_selected_models, is_setup_complete
    
    if is_setup_complete() and get_selected_models():
        # Already configured, show banner and go to main loop
        cli.print_banner()
        cli.console.print("\n[green]✓ Configuration found. Ready to code![/green]\n")
        
        # Initialize client with saved config
        cli.client = OpenRouterClient()
        cli.model_manager = ModelManager(cli.client)
        
        await cli.run_main_loop()
    else:
        # First time setup
        success = await cli.run_setup()
        
        if success:
            await cli.run_main_loop()


if __name__ == "__main__":
    asyncio.run(main())
