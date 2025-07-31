"""Chat command handlers"""

import typer
from rich.console import Console

from nova.core.chat import ChatManager
from nova.utils.formatting import print_error

chat_app = typer.Typer()
console = Console()


@chat_app.command("start")
def start_chat(
    session_name: str | None = typer.Argument(
        None, help="Session ID to continue or name for new session"
    ),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="AI profile to use for this chat session"
    ),
):
    """Start a new chat session or continue an existing one"""
    try:
        # Import here to avoid circular import
        from nova.main import app

        chat_manager = ChatManager(app.state.config_file, profile_override=profile)
        chat_manager.start_interactive_chat(session_name)

    except Exception as e:
        print_error(f"Failed to start chat: {e}")
        raise typer.Exit(1) from e


@chat_app.command("list")
def list_sessions():
    """List saved chat sessions"""
    try:
        # Import here to avoid circular import
        from nova.main import app

        chat_manager = ChatManager(app.state.config_file)
        chat_manager.list_conversations()

    except Exception as e:
        print_error(f"Failed to list sessions: {e}")
        raise typer.Exit(1) from e


@chat_app.command("resume")
def resume_last_session(
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="AI profile to use for this chat session"
    ),
):
    """Resume the most recently saved chat session"""
    try:
        # Import here to avoid circular import
        from nova.main import app

        chat_manager = ChatManager(app.state.config_file, profile_override=profile)
        chat_manager.resume_last_conversation()

    except Exception as e:
        print_error(f"Failed to resume last session: {e}")
        raise typer.Exit(1) from e


@chat_app.callback(invoke_without_command=True)
def chat_callback(ctx: typer.Context):
    """Chat-related commands"""
    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()
