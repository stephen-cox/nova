"""Main entry point for Nova CLI application"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from nova.cli.chat import chat_app
from nova.cli.config import config_app

app = typer.Typer(
    name="nova",
    help="Nova - AI Research Assistant",
    add_completion=False,
)

console = Console()

# Global state for sharing between commands
class AppState:
    config_file: Optional[Path] = None
    verbose: bool = False

app.state = AppState()

# Add subcommands
app.add_typer(chat_app, name="chat", help="Chat commands")
app.add_typer(config_app, name="config", help="Configuration commands")


@app.command()
def version():
    """Show Nova version"""
    from nova import __version__
    console.print(f"Nova v{__version__}")


@app.callback()
def main(
    config_file: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output",
    ),
):
    """Nova - AI Research Assistant
    
    A configurable CLI chatbot with conversation history and memory.
    """
    # Store global options in app state for subcommands to access
    app.state.config_file = config_file
    app.state.verbose = verbose


if __name__ == "__main__":
    app()