"""Main entry point for Nova CLI application"""

from pathlib import Path

import typer
from rich.console import Console

from nova.cli.chat import chat_app
from nova.cli.config import config_app
from nova.cli.tools import tools_app

app = typer.Typer(
    name="nova",
    help="Nova - AI Research Assistant",
    add_completion=False,
)

console = Console()


# Global state for sharing between commands
class AppState:
    config_file: Path | None = None
    verbose: bool = False


app.state = AppState()

# Add subcommands
app.add_typer(chat_app, name="chat", help="Chat commands")
app.add_typer(config_app, name="config", help="Configuration commands")
app.add_typer(tools_app, name="tools", help="Tools management commands")


@app.command()
def version():
    """Show Nova version"""
    from nova import __version__

    console.print(f"Nova v{__version__}")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config_file: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """Nova - AI Research Assistant

    A configurable CLI chatbot with conversation history and memory.
    """
    # Store global options in app state for subcommands to access
    app.state.config_file = config_file
    app.state.verbose = verbose

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()
