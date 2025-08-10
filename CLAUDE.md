# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nova is an AI research and personal assistant written in Python that provides:

- Command-line interface built with Typer
- YAML-based configuration management
- Chat history saved to markdown files
- **Multi-provider AI integration** (OpenAI, Anthropic, Ollama)
- **Custom prompt templating system** with built-in templates and user-defined prompts
- **Enhanced web search with intelligent query optimization** using YAKE keyword extraction and semantic analysis
- Modular architecture for extensibility

**Current Status:** Enhanced Search implemented with intelligent query optimization, supports OpenAI, Anthropic, and Ollama with custom prompt templates and comprehensive tools system with profile-based configuration.

## Package Management Commands

Use uv exclusively for Python package management in this project.

- All Python dependencies **must be installed, synchronized, and locked** using uv
- Never use pip, pip-tools, poetry, or conda directly for dependency management

Use these commands:

- Install dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Sync dependencies: `uv sync`
- Install test dependencies: `uv sync --extra test`

## Running the Application

- Run Nova CLI: `uv run nova --help`
- Start chat session: `uv run nova chat start`
- Resume last chat session: `uv run nova chat resume`
- List saved chat sessions: `uv run nova chat list`
- Show configuration: `uv run nova config show`
- Initialize config: `uv run nova config init`

## Prompt Management Commands

- List available prompt templates: `/prompts`
- Search prompt templates: `/prompts search <query>`
- Apply a prompt template: `/prompt <name>`
- Templates are stored in `~/.nova/prompts/user/custom/` (user-defined) and built-in templates

## Profile-Based Tools Configuration Commands

**Profile Tools Management:**
- Show tools config for profile: `uv run nova config show-tools <profile_name>`
- Configure tools for profile: `uv run nova config set-profile-tools <profile_name> --permission-mode <mode> --modules <modules> --enabled/--disabled`
- Reset profile to global tools: `uv run nova config reset-profile-tools <profile_name>`
- List profiles with tools info: `uv run nova config profiles`

**Profile Tools Features:**
- Each AI profile can have custom tools configuration
- Profiles inherit global tools settings by default
- Override specific settings per profile (permission mode, enabled modules, etc.)
- Use "Global" or "Custom" tools configuration per profile

## Enhanced Web Search Commands

Nova includes intelligent search with context-aware query enhancement through both tools and chat commands.

### /search Command (Enhanced)

**Basic Usage:**
```bash
/search <query>                    # Uses your configured default enhancement
/s <query>                        # Short form
```

**Advanced Usage:**
```bash
/search <query> --enhancement fast              # YAKE keyword extraction (~50ms)
/search <query> --enhancement semantic          # KeyBERT semantic analysis (~200-500ms)
/search <query> --enhancement hybrid            # Combined YAKE + KeyBERT (~300-600ms)
/search <query> --enhancement disabled          # Direct search without enhancement

/search <query> --provider google --max 3       # Existing options still work
/search <query> --technical-level expert        # Adjust query complexity
/search <query> --timeframe recent              # Prefer recent results
```

### Tool Usage (Alternative)

```bash
/tool web_search query="Python async programming" enhancement="fast"
/tool web_search query="machine learning deployment" enhancement="semantic"
```

### Search Enhancement Modes

- **auto**: Automatically choose best enhancement (YAKE + context)
- **disabled**: No enhancement, direct search
- **fast**: YAKE-only enhancement (~50ms) - **Default**
- **semantic**: KeyBERT semantic analysis (~200-500ms, requires additional dependencies)
- **hybrid**: Combined YAKE + KeyBERT (~300-600ms)

### Search Enhancement Configuration

Configure default search behavior in your configuration file:

```yaml
search:
  # Basic search settings
  enabled: true
  default_provider: "duckduckgo"
  max_results: 5
  use_ai_answers: true

  # Enhancement defaults (users can override per search)
  default_enhancement: "fast"           # auto, disabled, fast, semantic, hybrid
  enable_conversation_context: true     # Use chat history for context
  default_technical_level: "intermediate"  # beginner, intermediate, expert
  default_timeframe: "any"             # recent, past_year, any

  # Performance settings
  performance_mode: true               # Prioritize speed over accuracy
  enhancement_cache_enabled: true     # Cache enhanced queries

  # Advanced: Enable semantic analysis (optional)
  enable_keybert: false               # Set to true for KeyBERT
  extraction_backend: "yake_only"      # yake_only, keybert_only, hybrid
```

### Performance Guidance

- Use **fast** or default for most queries (optimal speed/accuracy balance)
- Use **semantic** for complex technical topics or research (requires: `uv add keybert sentence-transformers`)
- Use **disabled** for exact phrase searches or when speed is critical
- The system automatically uses conversation context to improve search relevance

## Testing Commands

- Run all tests: `uv run pytest`
- Run with coverage: `uv run pytest --cov=nova`
- Run specific test file: `uv run pytest tests/unit/test_config.py`
- Run integration tests only: `uv run pytest tests/integration/`

## Development Commands

- Run Python tools like Pytest: `uv run pytest` or `uv run ruff`
- Launch a Python repl: `uv run python`

## Code Quality Commands

- Run all code quality checks: `uv run ruff check . && uv run ruff format --check . && uv run black --check . && uv run isort --check-only .`
- Auto-fix code quality issues: `uv run ruff check . --fix && uv run ruff format . && uv run black . && uv run isort .`
- Run linting only: `uv run ruff check .`
- Run formatting only: `uv run ruff format .` or `uv run black .`
- Sort imports: `uv run isort .`
- Run pre-commit on all files: `uv run pre-commit run --all-files`

## Code Style

- PEP 8 naming (snake_case for functions/variables)
- Class names in PascalCase
- Constants in UPPER_SNAKE_CASE
- Document with docstrings
- Use f-strings for formatting

## Git workflow

- All changes must be made on a feature or bug fix branch, NEVER directly on main
- Git branches are prefixed with feature/ or hotfix/ and followed by a brief description
- feature/ branches are for new features and big changes. hotfix/ branches are for bug fixes and minor chnages
- Once the feature or fix is complete create, commit the changes and create a pull request into the main branch
- A feature or fix IS NOT complete until all tests and code quality checks are passing.
- Create a detailed message of what changed. Focus on the high level description of
  the problem it tries to solve, and how it is solved. Don't go into the specifics of the
  code unless it adds clarity.
- NEVER ever mention a `co-authored-by` or similar aspects. In particular, never
  mention the tool used to create the commit message or PR.

## Development Philosophy

- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Testability**: Ensure code is testable
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint

## Coding Best Practices

- **Early Returns**: Use to avoid nested conditions
- **Descriptive Names**: Use clear variable/function names (prefix handlers with "handle")
- **Constants Over Functions**: Use constants where possible
- **DRY Code**: Don't repeat yourself
- **Functional Style**: Prefer functional, immutable approaches when not verbose
- **Minimal Changes**: Only modify code related to the task at hand
- **Function Ordering**: Define composing functions before their components
- **TODO Comments**: Mark issues in existing code with "TODO:" prefix
- **Simplicity**: Prioritize simplicity and readability over clever solutions
- **Build Iteratively** Start with minimal functionality and verify it works before adding complexity
- **Run Tests**: Test your code frequently with realistic inputs and validate outputs
- **Build Test Environments**: Create testing environments for components that are difficult to validate directly
- **Functional Code**: Use functional and stateless approaches where they improve clarity
- **Clean logic**: Keep core logic clean and push implementation details to the edges
- **File Organsiation**: Balance file organization with simplicity - use an appropriate number of files for the project scale
- **Input Handling**: Use `prompt-toolkit` for enhanced terminal input with arrow key navigation and history support
- **Template Security**: Always validate user-provided templates for dangerous patterns and length limits
- **Path Security**: Ensure file paths are properly sanitized to prevent directory traversal attacks
- **Variable Validation**: Use type checking for template variables and validate required fields
- **YAML Security**: Always use `yaml.safe_load()` instead of `yaml.load()` to prevent code injection
- **Error Handling**: Use specific exception types and provide meaningful error messages; avoid silent failures
- **Metadata Validation**: Validate user-provided metadata to prevent oversized or malicious content
- **Performance**: Consider lazy loading and caching for operations that read multiple files
- **Backward Compatibility**: Maintain fallback mechanisms when introducing new data formats
- **Tool Security**: Use appropriate permission levels and validate tool inputs; prefer `@tool` decorator over manual registration
- **Async Operations**: Prefer async/await for I/O operations; use proper timeout and resource management
- **Performance Awareness**: Consider lazy loading, caching, and concurrent operations for better performance
- **Resource Cleanup**: Always implement proper cleanup in async handlers and use context managers
- **Permission-Based Security**: Tools should use proper permission levels (SAFE, ELEVATED, SYSTEM, DANGEROUS)
- **Tool Discovery**: Use automatic tool discovery via decorators rather than manual registration

## Project Architecture

**Modular Structure:**
- `nova/cli/` - CLI command handlers (Typer-based)
- `nova/core/` - Business logic (config, chat, history)
- `nova/models/` - Pydantic data models
- `nova/utils/` - Shared utilities

**Key Components:**
- Configuration management with YAML and environment variable support
- Chat history persistence in markdown format with YAML frontmatter metadata
- Interactive chat sessions with commands (/help, /save, etc.)
- Enhanced input handling with arrow key navigation and message history
- **Custom prompt templating system** with validation, categories, and variable substitution
- Comprehensive test suite with unit and integration tests

**Chat History Format:**
- New format uses YAML frontmatter for metadata (conversation_id, title, timestamps, tags)
- Maintains backward compatibility with legacy HTML comment format
- Metadata includes: conversation_id, created, updated, title, tags, summaries_count

## Configuration

Configuration follows this precedence (highest to lowest):
1. Command-line `--config` file
2. Environment variables (NOVA_API_KEY, NOVA_MODEL, etc.)
3. Default config files (`nova-config.yaml`, `~/.nova/config.yaml`)
4. Built-in defaults

### AI Provider Configuration

**OpenAI:**
- Set `OPENAI_API_KEY` environment variable
- Provider: `openai`, Model: `gpt-4`, `gpt-3.5-turbo`, etc.

**Anthropic:**
- Set `ANTHROPIC_API_KEY` environment variable
- Provider: `anthropic`, Model: `claude-3-5-sonnet-20241022`, etc.

**Ollama (Local):**
- No API key required
- Provider: `ollama`, Model: any installed model (`llama2`, `mistral`, etc.)
- Set `OLLAMA_HOST` or `base_url` to customize endpoint (default: `http://localhost:11434`)
