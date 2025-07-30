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
        
        # AI Model settings
        table.add_row("AI Provider", config.ai_model.provider)
        table.add_row("Model Name", config.ai_model.model_name)
        table.add_row("Max Tokens", str(config.ai_model.max_tokens))
        table.add_row("Temperature", str(config.ai_model.temperature))
        table.add_row("API Key", "***" if config.ai_model.api_key else "Not set")
        
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


@config_app.callback()
def config_callback():
    """Configuration management commands"""
    pass