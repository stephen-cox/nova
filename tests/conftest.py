"""Shared test fixtures and configuration"""

import tempfile
from pathlib import Path
from datetime import datetime
from typing import Generator

import pytest
import yaml

from nova.models.config import NovaConfig, AIModelConfig, ChatConfig
from nova.models.message import Conversation, Message, MessageRole


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config() -> NovaConfig:
    """Create a sample configuration for testing"""
    return NovaConfig(
        ai_model=AIModelConfig(
            provider="openai",
            model_name="gpt-3.5-turbo",
            api_key="test-api-key",
            max_tokens=1000,
            temperature=0.5
        ),
        chat=ChatConfig(
            history_dir=Path("/tmp/test-history"),
            max_history_length=25,
            auto_save=True
        )
    )


@pytest.fixture
def sample_config_dict() -> dict:
    """Create a sample configuration dictionary for YAML testing"""
    return {
        "ai_model": {
            "provider": "openai",
            "model_name": "gpt-3.5-turbo",
            "api_key": "test-api-key",
            "max_tokens": 1000,
            "temperature": 0.5
        },
        "chat": {
            "history_dir": "/tmp/test-history",
            "max_history_length": 25,
            "auto_save": True
        }
    }


@pytest.fixture
def sample_config_yaml(temp_dir: Path, sample_config_dict: dict) -> Path:
    """Create a sample YAML config file"""
    config_path = temp_dir / "test-config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(sample_config_dict, f)
    return config_path


@pytest.fixture
def sample_conversation() -> Conversation:
    """Create a sample conversation for testing"""
    conv = Conversation(
        id="test-conv-123",
        title="Test Conversation",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 30, 0)
    )
    
    conv.add_message(MessageRole.USER, "Hello, how are you?")
    conv.add_message(MessageRole.ASSISTANT, "I'm doing well, thank you! How can I help you today?")
    conv.add_message(MessageRole.USER, "Can you explain Python decorators?")
    conv.add_message(MessageRole.ASSISTANT, "Sure! Python decorators are a way to modify or enhance functions...")
    
    return conv


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown conversation for testing parsing"""
    return """<!-- Nova Chat History -->
<!-- Conversation ID: test-conv-123 -->
<!-- Created: 2024-01-01T12:00:00 -->
<!-- Updated: 2024-01-01T12:30:00 -->
<!-- Title: Test Conversation -->

# Test Conversation

## User (12:00:00)

Hello, how are you?

## Assistant (12:05:00)

I'm doing well, thank you! How can I help you today?

## User (12:10:00)

Can you explain Python decorators?

## Assistant (12:15:00)

Sure! Python decorators are a way to modify or enhance functions...

"""


@pytest.fixture
def invalid_yaml_content() -> str:
    """Invalid YAML content for testing error handling"""
    return """
ai_model:
  provider: "openai"
  model_name: "gpt-3.5-turbo
  # Missing closing quote above
  max_tokens: not_a_number
"""


@pytest.fixture
def history_dir(temp_dir: Path) -> Path:
    """Create a temporary history directory"""
    history_path = temp_dir / "history"
    history_path.mkdir()
    return history_path


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing"""
    def _mock_env(**kwargs):
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)
    return _mock_env