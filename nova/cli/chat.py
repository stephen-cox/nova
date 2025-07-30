"""Chat command handlers"""

from pathlib import Path
from typing import Optional

import typer

from nova.core.chat import ChatManager
from nova.utils.formatting import print_error

chat_app = typer.Typer()


@chat_app.command("start")
def start_chat(
    session_name: Optional[str] = typer.Argument(
        None,
        help="Session ID to continue or name for new session"
    ),
):
    """Start a new chat session or continue an existing one"""
    try:
        # Import here to avoid circular import
        from nova.main import app
        
        chat_manager = ChatManager(app.state.config_file)
        chat_manager.start_interactive_chat(session_name)
        
    except Exception as e:
        print_error(f"Failed to start chat: {e}")
        raise typer.Exit(1)


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
        raise typer.Exit(1)


@chat_app.callback()
def chat_callback():
    """Chat-related commands"""
    pass