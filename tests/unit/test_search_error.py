"""Test to reproduce the search command error"""

from unittest.mock import Mock, patch

import pytest

from nova.core.chat import ChatManager, ChatSession
from nova.models.config import AIProfile, ChatConfig, NovaConfig, SearchConfig


class TestSearchCommandError:
    """Test search command error reproduction"""

    def test_search_command_messages_attribute_error_was_fixed(self):
        """Test that verifies the 'messages' attribute error is now fixed"""

        # Create a minimal config for testing
        config = NovaConfig(
            profiles={
                "default": AIProfile(
                    name="default", provider="openai", model_name="gpt-4"
                )
            },
            active_profile="default",
            chat=ChatConfig(history_dir="/tmp/test", auto_save=False),
            search=SearchConfig(enabled=True),
        )

        # Mock the AI client BEFORE creating ChatSession since it's called in __init__
        with (
            patch("nova.core.config.config_manager.load_config", return_value=config),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Mock the AI client to avoid API key requirements
            mock_ai_client = Mock()
            mock_create_ai_client.return_value = mock_ai_client

            chat_manager = ChatManager()
            session = ChatSession(config)

            # Mock the search functionality to avoid actual network calls
            with patch("nova.search.manager.SearchManager") as mock_search_manager:
                mock_search_instance = Mock()
                mock_search_manager.return_value = mock_search_instance

                # Mock the search response
                mock_response = Mock()
                mock_response.results = []
                mock_response.query = "test query"
                mock_response.provider = "duckduckgo"
                mock_search_instance.search.return_value = mock_response
                mock_search_instance.close.return_value = None

                # This previously triggered the error: 'ChatSession' object has no attribute 'messages'
                # The error occurred in line 493 where it tried to access session.messages
                # Now it should work correctly after fixing session.messages -> session.conversation.messages
                import io
                from contextlib import redirect_stdout

                # Capture stdout to verify the error no longer occurs
                captured_output = io.StringIO()
                with redirect_stdout(captured_output):
                    chat_manager._handle_search_command(
                        "What events are happening near me next weekend?", session
                    )

                output = captured_output.getvalue()
                # Should NOT contain the messages attribute error anymore
                assert "'ChatSession' object has no attribute 'messages'" not in output
                # Should contain search-related output instead
                assert "Searching" in output or "search" in output.lower()

    def test_search_command_correct_messages_access(self):
        """Test that shows the correct way to access messages"""

        # Create a minimal config for testing
        config = NovaConfig(
            profiles={
                "default": AIProfile(
                    name="default", provider="openai", model_name="gpt-4"
                )
            },
            active_profile="default",
            chat=ChatConfig(history_dir="/tmp/test", auto_save=False),
            search=SearchConfig(enabled=True, use_ai_answers=False),
        )

        # Mock the AI client BEFORE creating ChatSession since it's called in __init__
        with (
            patch("nova.core.config.config_manager.load_config", return_value=config),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Mock the AI client to avoid API key requirements
            mock_ai_client = Mock()
            mock_create_ai_client.return_value = mock_ai_client

            chat_manager = ChatManager()
            session = ChatSession(config)

            # Add some messages to the conversation
            session.add_user_message("Hello")
            session.add_assistant_message("Hi there!")
            session.add_user_message("What's the weather like?")

            # Verify session has conversation.messages, not messages directly
            assert hasattr(session, "conversation")
            assert hasattr(session.conversation, "messages")
            assert len(session.conversation.messages) == 3

            # This should NOT have a messages attribute directly on session
            assert not hasattr(session, "messages")

            # Mock the search functionality to avoid actual network calls
            with patch("nova.search.manager.SearchManager") as mock_search_manager:
                mock_search_instance = Mock()
                mock_search_manager.return_value = mock_search_instance

                # Mock the search response
                mock_response = Mock()
                mock_response.results = []
                mock_response.query = "test query"
                mock_response.provider = "duckduckgo"
                mock_search_instance.search.return_value = mock_response
                mock_search_instance.close.return_value = None

                # With use_ai_answers=False, this should not trigger the messages access
                # and should work correctly (just display raw results)
                try:
                    chat_manager._handle_search_command("test query", session)
                    # If we get here, the basic search worked (without AI enhancement)
                except AttributeError as e:
                    if "'ChatSession' object has no attribute 'messages'" in str(e):
                        pytest.fail("The messages attribute error still occurs")
                    else:
                        # Some other AttributeError, re-raise it
                        raise

    def test_search_command_fixed_messages_access(self):
        """Test that the search command works correctly after fixing the messages access bug"""

        # Create a minimal config for testing
        config = NovaConfig(
            profiles={
                "default": AIProfile(
                    name="default", provider="openai", model_name="gpt-4"
                )
            },
            active_profile="default",
            chat=ChatConfig(history_dir="/tmp/test", auto_save=False),
            search=SearchConfig(enabled=True, use_ai_answers=True),
        )

        # Mock the AI client BEFORE creating ChatSession since it's called in __init__
        with (
            patch("nova.core.config.config_manager.load_config", return_value=config),
            patch("nova.core.ai_client.create_ai_client") as mock_create_ai_client,
        ):
            # Mock the AI client to avoid API key requirements
            mock_ai_client = Mock()
            mock_create_ai_client.return_value = mock_ai_client

            chat_manager = ChatManager()
            session = ChatSession(config)

            # Add some messages to the conversation
            session.add_user_message("Hello")
            session.add_assistant_message("Hi there!")
            session.add_user_message("What's the weather like?")

            # Mock the search functionality to avoid actual network calls
            with patch("nova.search.manager.SearchManager") as mock_search_manager:
                mock_search_instance = Mock()
                mock_search_manager.return_value = mock_search_instance

                # Mock the search response
                mock_response = Mock()
                mock_response.results = []
                mock_response.query = "test query"
                mock_response.provider = "duckduckgo"
                mock_search_instance.search.return_value = mock_response
                mock_search_instance.close.return_value = None

                import io
                from contextlib import redirect_stdout

                # Capture stdout to verify no error occurs
                captured_output = io.StringIO()
                with redirect_stdout(captured_output):
                    chat_manager._handle_search_command("test query", session)

                output = captured_output.getvalue()
                # Should NOT contain the messages attribute error
                assert "'ChatSession' object has no attribute 'messages'" not in output
                # Should contain search-related output
                assert "Searching" in output or "search" in output.lower()
