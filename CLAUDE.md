# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Nova is an AI research and personal assistant written in Python that provides:

- Command-line interface built with Typer
- YAML-based configuration management
- Chat history saved to markdown files
- **Multi-provider AI integration** (OpenAI, Anthropic, Ollama)
- Modular architecture for extensibility

**Current Status:** Phase 2 complete (AI integration), supports OpenAI, Anthropic, and Ollama.

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
- Show configuration: `uv run nova config show`
- Initialize config: `uv run nova config init`

## Testing Commands

- Run all tests: `uv run pytest`
- Run with coverage: `uv run pytest --cov=nova`
- Run specific test file: `uv run pytest tests/unit/test_config.py`
- Run integration tests only: `uv run pytest tests/integration/`

## Development Commands

- Run Python tools like Pytest: `uv run pytest` or `uv run ruff`
- Launch a Python repl: `uv run python`

## Project Architecture

**Modular Structure:**
- `nova/cli/` - CLI command handlers (Typer-based)
- `nova/core/` - Business logic (config, chat, history)
- `nova/models/` - Pydantic data models
- `nova/utils/` - Shared utilities

**Key Components:**
- Configuration management with YAML and environment variable support
- Chat history persistence in markdown format
- Interactive chat sessions with commands (/help, /save, etc.)
- Comprehensive test suite with unit and integration tests

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
