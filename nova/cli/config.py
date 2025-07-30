"""Configuration command handlers"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from nova.core.config import config_manager, ConfigError
from nova.utils.formatting import print_error, print_success, print_info

config_app = typer.Typer()
console = Console()


@config_app.command("show")
def show_config(
    config_file: Optional[Path] = typer.Option(
        None,
        "--file", "-f",
        help="Configuration file to show"
    )
):
    """Show current configuration"""
    try:
        # Use global config or specified file
        if not config_file:
            # Import here to avoid circular import
            from nova.main import app
            config_file = app.state.config_file
        
        config = config_manager.load_config(config_file)
        
        print_info("Current Configuration:")
        
        table = Table()
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        
        # Active AI configuration (from profile or direct)
        active_config = config.get_active_ai_config()
        table.add_row("Active Profile", config.active_profile or "None (using direct config)")
        table.add_row("AI Provider", active_config.provider)
        table.add_row("Model Name", active_config.model_name)
        table.add_row("Max Tokens", str(active_config.max_tokens))
        table.add_row("Temperature", str(active_config.temperature))
        table.add_row("API Key", "***" if active_config.api_key else "Not set")
        
        # Chat settings
        table.add_row("History Directory", str(config.chat.history_dir))
        table.add_row("Max History Length", str(config.chat.max_history_length))
        table.add_row("Auto Save", str(config.chat.auto_save))
        
        console.print(table)
        
    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)


@config_app.command("init")
def init_config(
    output_path: Optional[Path] = typer.Option(
        Path("nova-config.yaml"),
        "--output", "-o",
        help="Output path for configuration file"
    )
):
    """Initialize a new configuration file"""
    try:
        # Load default config
        config = config_manager._load_default_config()
        
        # Save to specified path
        config_manager.save_config(config, output_path)
        
        print_success(f"Configuration file created: {output_path}")
        print_info("Edit the file to customize your settings")
        print_info("Set NOVA_API_KEY environment variable for your AI provider")
        
    except Exception as e:
        print_error(f"Failed to create configuration: {e}")
        raise typer.Exit(1)


@config_app.command("profiles")
def list_profiles(
    config_file: Optional[Path] = typer.Option(
        None,
        "--file", "-f",
        help="Configuration file to show profiles from"
    )
):
    """List available AI profiles"""
    try:
        if not config_file:
            from nova.main import app
            config_file = app.state.config_file if hasattr(app.state, 'config_file') else None
        
        config = config_manager.load_config(config_file)
        
        if not config.profiles:
            print_info("No profiles configured")
            return
        
        print_info("Available AI Profiles:")
        
        table = Table()
        table.add_column("Profile", style="cyan")
        table.add_column("Provider", style="green")
        table.add_column("Model", style="yellow")
        table.add_column("Active", style="red")
        
        for profile_name, profile in config.profiles.items():
            is_active = "✓" if config.active_profile == profile_name else ""
            table.add_row(profile_name, profile.provider, profile.model_name, is_active)
        
        console.print(table)
        
    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)


@config_app.command("profile")
def set_profile(
    profile_name: str = typer.Argument(help="Profile name to activate"),
    config_file: Optional[Path] = typer.Option(
        None,
        "--file", "-f",
        help="Configuration file to update"
    )
):
    """Activate an AI profile"""
    try:
        if not config_file:
            from nova.main import app
            config_file = app.state.config_file if hasattr(app.state, 'config_file') else None
        
        config = config_manager.load_config(config_file)
        
        if profile_name not in config.profiles:
            print_error(f"Profile '{profile_name}' not found")
            print_info("Available profiles:")
            for name in config.profiles.keys():
                print_info(f"  - {name}")
            raise typer.Exit(1)
        
        config.active_profile = profile_name
        
        # If no specific config file was provided, save to the first default path
        if not config_file:
            config_file = Path("nova-config.yaml")
        
        config_manager.save_config(config, config_file)
        
        profile = config.profiles[profile_name]
        print_success(f"Activated profile '{profile_name}' ({profile.provider}/{profile.model_name})")
        
    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)


@config_app.callback(invoke_without_command=True)
def config_callback(ctx: typer.Context):
    """Configuration management commands"""
    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()