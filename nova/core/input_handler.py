"""Enhanced input handling with arrow key navigation and message history"""

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings


class ChatInputHandler:
    """Handles enhanced input with cursor navigation and message history"""

    def __init__(self):
        self.message_history = InMemoryHistory()
        self.key_bindings = KeyBindings()
        self._setup_key_bindings()

    def _setup_key_bindings(self):
        """Setup custom key bindings for enhanced navigation"""

        # Left and right arrow keys are handled automatically by prompt-toolkit
        # for cursor navigation within the current line

        # Up and down arrows are handled automatically by prompt-toolkit
        # for navigating through command history

        # The default behavior already provides what we need:
        # - Left/Right: Move cursor in current message
        # - Up/Down: Navigate through message history
        pass

    def get_input(self, prompt_text: str = "You: ") -> str | None:
        """
        Get user input with enhanced navigation support

        Args:
            prompt_text: The prompt to display to the user

        Returns:
            User input string, or None if interrupted
        """
        try:
            user_input = prompt(
                prompt_text,
                history=self.message_history,
                key_bindings=self.key_bindings,
                vi_mode=False,  # Use emacs-style navigation (default)
                multiline=False,
                wrap_lines=True,
                complete_style="column",
            )

            # Add to history if not empty
            if user_input.strip():
                self.message_history.append_string(user_input)

            return user_input.strip()

        except (EOFError, KeyboardInterrupt):
            return None

    def clear_history(self):
        """Clear the input history"""
        self.message_history = InMemoryHistory()

    def add_to_history(self, message: str):
        """Add a message to the input history manually"""
        if message.strip():
            self.message_history.append_string(message)

    def get_history(self) -> list[str]:
        """Get all messages from history"""
        return list(self.message_history.get_strings())
