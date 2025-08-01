"""Rich formatting utilities for terminal output"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()


def print_message(role: str, content: str, timestamp: str = None):
    """Print a formatted chat message"""

    if role.lower() == "user":
        color = "blue"
        icon = "👤"
        display_role = "You"
    elif role.lower() == "assistant":
        color = "green"
        icon = "🤖"
        display_role = "Nova"
    else:
        color = "yellow"
        icon = "ℹ️"
        display_role = role.title()

    # Create header
    header = f"{icon} {display_role}"
    if timestamp:
        header += f" ({timestamp})"

    # Create panel with message
    panel = Panel(
        Markdown(content),
        title=header,
        title_align="left",
        border_style=color,
        padding=(0, 1),
    )

    console.print(panel)


def print_error(message: str):
    """Print an error message"""
    console.print(f"[red bold]Error:[/red bold] {message}")


def print_success(message: str):
    """Print a success message"""
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str):
    """Print a warning message"""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """Print an info message"""
    console.print(f"[blue]ℹ[/blue] {message}")


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
