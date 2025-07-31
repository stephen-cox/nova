# Nova - AI Research Assistant

Nova is a configurable command-line AI assistant that provides multi-provider AI integration, conversation history, and extensible chat capabilities. Built with Python and Typer, Nova supports OpenAI, Anthropic, and Ollama providers with a profile-based configuration system and persistent chat history saved in markdown format.

## Features

- **Multi-provider AI Integration**: Support for OpenAI, Anthropic, and Ollama
- **Profile-based Configuration**: Easy switching between different AI models and providers
- **Interactive CLI**: Built with Typer for a rich command-line experience
- **Intelligent Chat History**: Conversations saved as markdown files with smart content-based titles
- **Session Management**: Resume your most recent conversation with a single command
- **Flexible Configuration**: YAML-based configuration with environment variable support
- **Memory Management**: Smart context optimization and conversation summarization
- **Nova Branding**: Personalized AI responses clearly labeled as "Nova" throughout the interface
- **Modular Architecture**: Extensible design for easy feature additions
- **Rich Output**: Beautiful console output with Rich library integration

## Installation

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install Dependencies

Clone the repository and install dependencies using uv:

```bash
git clone <repository-url>
cd nova
uv sync
```

For development with test dependencies:

```bash
uv sync --extra test
```

## Quick Start

### 1. Initialize Configuration

```bash
uv run nova config init
```

### 2. Configure AI Provider

Choose one of the following providers:

#### OpenAI
```bash
export OPENAI_API_KEY="your-openai-api-key"
uv run nova config show  # Verify configuration
```

#### Anthropic
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
uv run nova chat start --profile claude  # Use Claude profile
```

#### Ollama (Local)
```bash
# No API key required - just ensure Ollama is running locally
uv run nova chat start --profile llama  # Use Llama profile
```

### 3. Start Chatting

```bash
# Start a new chat session
uv run nova chat start

# Or resume your most recent conversation
uv run nova chat resume
```

## Usage

### CLI Commands

#### Chat Commands
```bash
# Start interactive chat session (uses default profile)
uv run nova chat start

# Resume the most recent chat session
uv run nova chat resume

# Resume with a specific profile
uv run nova chat resume --profile claude

# Start chat with specific profile
uv run nova chat start --profile gpt4
uv run nova chat start --profile claude
uv run nova chat start --profile llama

# Continue a specific conversation by session ID
uv run nova chat start session_id

# List all saved conversations
uv run nova chat list

# Start chat with custom config file
uv run nova chat start --config my-config.yaml
```

#### Configuration Commands
```bash
# Show current configuration
uv run nova config show

# List available profiles
uv run nova config profiles

# Show specific profile
uv run nova config profile claude

# Initialize default configuration
uv run nova config init

# Validate configuration
uv run nova config validate
```

#### General Commands
```bash
# Show help
uv run nova --help

# Show version
uv run nova version

# Enable verbose output
uv run nova --verbose chat start
```

### Interactive Chat Commands

While in a chat session, you can use these commands:

- `/help` - Show available commands
- `/save` - Save current conversation
- `/history` - View conversation history
- `/clear` - Clear current conversation
- `/title <title>` - Set a custom title for the conversation
- `/exit` or `/quit` - Exit chat session
- `/summarize` - Summarize conversation
- `/tag <tags>` - Add tags to conversation
- `/stats` - Show memory statistics

**Note**: Conversations without manually set titles will automatically generate intelligent titles based on the content of your first message.

## Enhanced Features

### Intelligent Title Generation

Nova automatically generates meaningful titles for your conversations based on the content of your first message. This makes it easy to find and identify specific conversations later.

**Examples:**
- `"How do I implement user authentication in Django?"` → `"How to implement user authentication in django"`
- `"Can you help me fix this memory leak?"` → `"Help me fix this memory leak"`
- `"Explain the difference between REST and GraphQL APIs"` → `"Explain the difference between rest and graphql apis"`

### Session Management

**Resume Recent Conversations**
```bash
# Resume your most recent chat session
uv run nova chat resume

# Resume with a different AI profile
uv run nova chat resume --profile claude
```

**List and Continue Specific Sessions**
```bash
# See all your saved conversations
uv run nova chat list

# Continue a specific conversation by session ID
uv run nova chat start abc123def
```

## Configuration

### Configuration Files

Nova looks for configuration files in this order:

1. Command-line specified file (`--config path/to/config.yaml`)
2. `nova-config.yaml` in current directory
3. `~/.nova/config.yaml` in user home directory
4. Built-in defaults

### Environment Variables

Override configuration with environment variables:

- `NOVA_API_KEY` - API key for the selected provider
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `NOVA_MODEL` - Model name to use
- `NOVA_PROVIDER` - AI provider (openai, anthropic, ollama)
- `NOVA_PROFILE` - Active profile to use
- `OLLAMA_HOST` - Ollama server URL (default: http://localhost:11434)

### Profile-based Configuration

Nova uses a profile-based configuration system for easy switching between AI providers and models:

```yaml
# Active profile (can be overridden with NOVA_PROFILE)
active_profile: "default"

# AI profiles for different models and providers
profiles:
  default:
    name: "default"
    provider: "openai"
    model_name: "gpt-3.5-turbo"
    max_tokens: 2000
    temperature: 0.7

  gpt4:
    name: "gpt4"
    provider: "openai"
    model_name: "gpt-4"
    max_tokens: 4000
    temperature: 0.7

  claude:
    name: "claude"
    provider: "anthropic"
    model_name: "claude-sonnet-4-20250514"
    max_tokens: 4000
    temperature: 0.7

  claude-opus:
    name: "claude-opus"
    provider: "anthropic"
    model_name: "claude-opus-4-20250514"
    max_tokens: 4000
    temperature: 0.7

  llama:
    name: "llama"
    provider: "ollama"
    model_name: "llama3.1"
    base_url: "http://localhost:11434"
    max_tokens: 2000
    temperature: 0.7
```

#### Using Profiles

```bash
# List available profiles
uv run nova config profiles

# Use a specific profile for chat
uv run nova chat start --profile gpt4
uv run nova chat start --profile claude
uv run nova chat start --profile llama

# Set active profile via environment
export NOVA_PROFILE=claude
uv run nova chat start  # Uses Claude profile
```

### Chat Configuration

```yaml
chat:
  history_dir: "~/.nova/history"
  max_history_length: 50
  auto_save: true
```

### Complete Configuration Example

```yaml
# Nova AI Assistant Configuration

# Chat behavior settings
chat:
  history_dir: "~/.nova/history"
  max_history_length: 50
  auto_save: true

# AI profiles for different models and providers
profiles:
  default:
    name: "default"
    provider: "openai"
    model_name: "gpt-3.5-turbo"
    max_tokens: 2000
    temperature: 0.7
    # api_key will be set via environment variables

  gpt4:
    name: "gpt4"
    provider: "openai"
    model_name: "gpt-4"
    max_tokens: 4000
    temperature: 0.7

  claude:
    name: "claude"
    provider: "anthropic"
    model_name: "claude-sonnet-4-20250514"
    max_tokens: 4000
    temperature: 0.7

  llama:
    name: "llama"
    provider: "ollama"
    model_name: "llama3.1"
    base_url: "http://localhost:11434"
    max_tokens: 2000
    temperature: 0.7

# Active profile (defaults to "default" if not specified)
active_profile: "default"
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=nova

# Run specific test file
uv run pytest tests/unit/test_config.py

# Run integration tests only
uv run pytest tests/integration/
```

### Project Structure

```
nova/
|-- nova/
|   |-- cli/              # CLI command handlers
|   |   |-- chat.py       # Chat commands
|   |   `-- config.py     # Configuration commands
|   |-- core/             # Business logic
|   |   |-- ai_client.py  # AI provider integration
|   |   |-- chat.py       # Chat functionality
|   |   |-- config.py     # Configuration management
|   |   |-- history.py    # Chat history persistence
|   |   `-- memory.py     # Memory management
|   |-- models/           # Pydantic data models
|   |   |-- config.py     # Configuration models
|   |   `-- message.py    # Message models
|   `-- utils/            # Shared utilities
|       |-- files.py      # File operations
|       `-- formatting.py # Output formatting
|-- tests/                # Test suite
|   |-- unit/             # Unit tests
|   `-- integration/      # Integration tests
`-- config/
    `-- default.yaml      # Default configuration
```
### Package Management

This project uses `uv` exclusively for dependency management:

```bash
# Add new dependency
uv add <package>

# Remove dependency
uv remove <package>

# Sync dependencies
uv sync

# Add development dependency
uv add --dev <package>
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Submit a pull request

## License

Nova is released under the GPLv3 licence.

## Support

For issues and feature requests, please use the project's issue tracker: <https://github.com/stephen-cox/nova/issues>
