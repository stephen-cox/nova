"""Tools command handlers"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nova.core.config import ConfigError, config_manager
from nova.core.tools.handler import ToolHandler
from nova.models.tools import ToolDefinition
from nova.tools.registry import discover_all_tools, discover_built_in_tools
from nova.utils.formatting import print_error, print_info

tools_app = typer.Typer()
console = Console()


def get_module_name_from_tool_source(
    tool_def: ToolDefinition, handler: ToolHandler
) -> str:
    """Extract module name from tool handler for configuration purposes"""
    # For decorated tools, check the func attribute first
    if hasattr(handler, "func") and hasattr(handler.func, "__module__"):
        module_path = handler.func.__module__
        if "built_in" in module_path:
            # Extract module name from path like 'nova.tools.built_in.text_tools'
            parts = module_path.split(".")
            if "built_in" in parts:
                idx = parts.index("built_in")
                if idx + 1 < len(parts):
                    return parts[idx + 1]

    # Fallback to handler module
    if hasattr(handler, "__module__"):
        module_path = handler.__module__
        if "built_in" in module_path:
            parts = module_path.split(".")
            if "built_in" in parts:
                idx = parts.index("built_in")
                if idx + 1 < len(parts):
                    return parts[idx + 1]

    return "unknown"


def get_available_modules() -> list[str]:
    """Get list of available built-in tool modules"""
    built_in_path = Path(__file__).parent.parent / "tools" / "built_in"
    modules = []

    for file in built_in_path.glob("*.py"):
        if file.name != "__init__.py":
            modules.append(file.stem)

    return sorted(modules)


@tools_app.command("list")
def list_tools(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    module: str = typer.Option(None, "--module", "-m", help="Filter by module name"),
    show_examples: bool = typer.Option(False, "--examples", help="Show tool examples"),
    config_file: Path | None = typer.Option(
        None, "--file", "-f", help="Configuration file to use"
    ),
):
    """List available tools with configuration information"""

    try:
        # Load config to show current settings
        if not config_file:
            from nova.main import app

            config_file = (
                getattr(app.state, "config_file", None)
                if hasattr(app, "state")
                else None
            )

        config = config_manager.load_config(config_file)
        tools_config = config.get_effective_tools_config()

        # Discover all tools
        all_tools = discover_all_tools()

        print_info("Available Tools")
        print()

        # Show current tools configuration
        config_panel = Panel(
            f"""[cyan]Current Tools Configuration:[/cyan]
[white]• Enabled:[/white] {tools_config.enabled}
[white]• Permission Mode:[/white] {tools_config.permission_mode}
[white]• Enabled Modules:[/white] {", ".join(tools_config.enabled_built_in_modules) if tools_config.enabled_built_in_modules else "None"}
[white]• Execution Timeout:[/white] {tools_config.execution_timeout}s""",
            title="Configuration",
            border_style="blue",
        )
        console.print(config_panel)
        print()

        # Filter tools
        filtered_tools = all_tools
        if category:
            filtered_tools = {
                name: (tool_def, handler)
                for name, (tool_def, handler) in filtered_tools.items()
                if tool_def.category.value == category
            }

        if module:
            filtered_tools = {
                name: (tool_def, handler)
                for name, (tool_def, handler) in filtered_tools.items()
                if get_module_name_from_tool_source(tool_def, handler) == module
            }

        if not filtered_tools:
            print_error("No tools found matching the specified filters")
            return

        # Group tools by module
        tools_by_module: dict[str, list[tuple[str, ToolDefinition, ToolHandler]]] = {}

        for tool_name, (tool_def, handler) in filtered_tools.items():
            module_name = get_module_name_from_tool_source(tool_def, handler)
            if module_name not in tools_by_module:
                tools_by_module[module_name] = []
            tools_by_module[module_name].append((tool_name, tool_def, handler))

        # Display tools grouped by module
        for module_name, tools in sorted(tools_by_module.items()):
            module_enabled = module_name in tools_config.enabled_built_in_modules
            module_status = (
                "[green]✓ Enabled[/green]"
                if module_enabled
                else "[red]✗ Disabled[/red]"
            )

            console.print(
                f"\n[bold blue]Module: {module_name}[/bold blue] ({module_status})"
            )

            if not module_enabled:
                console.print(
                    f"[yellow]  To enable: Add '{module_name}' to enabled_built_in_modules in config[/yellow]"
                )

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Tool Name", style="cyan", no_wrap=True)
            table.add_column("Description", style="white")
            table.add_column("Category", style="green", no_wrap=True)
            table.add_column("Permission", style="yellow", no_wrap=True)
            table.add_column("Tags", style="blue")

            for tool_name, tool_def, _handler in sorted(tools):
                tags_str = ", ".join(tool_def.tags[:3])  # Limit to first 3 tags
                if len(tool_def.tags) > 3:
                    tags_str += "..."

                table.add_row(
                    tool_name,
                    (
                        tool_def.description[:60] + "..."
                        if len(tool_def.description) > 60
                        else tool_def.description
                    ),
                    tool_def.category.value,
                    tool_def.permission_level.value,
                    tags_str,
                )

            console.print(table)

            # Show examples if requested
            if show_examples:
                for tool_name, tool_def, _handler in sorted(tools):
                    if tool_def.examples:
                        console.print(
                            f"\n[bold cyan]Examples for {tool_name}:[/bold cyan]"
                        )
                        for i, example in enumerate(tool_def.examples, 1):
                            console.print(
                                f"  {i}. [white]{example.description}[/white]"
                            )
                            console.print(
                                f"     Arguments: [dim]{example.arguments}[/dim]"
                            )
                            if example.expected_result:
                                console.print(
                                    f"     Expected: [dim]{example.expected_result}[/dim]"
                                )

        # Show configuration help
        print()
        config_help = Panel(
            """[cyan]Configuration Help:[/cyan]

[white]To enable/disable tools, edit your configuration file:[/white]
[dim]nova-config.yaml[/dim] or [dim]~/.nova/config.yaml[/dim]

[white]Example configuration:[/white]
[dim]tools:
  enabled: true
  permission_mode: "prompt"  # "auto", "prompt", or "deny"
  enabled_built_in_modules:
    - "text_tools"
    - "network_tools"
    - "file_ops"
    - "web_search"
    - "conversation"
  execution_timeout: 30[/dim]

[white]Available modules:[/white] [dim]{modules}[/dim]""".format(
                modules=", ".join(get_available_modules())
            ),
            title="Configuration",
            border_style="green",
        )
        console.print(config_help)

    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error listing tools: {e}")
        raise typer.Exit(1)


@tools_app.command("modules")
def list_modules(
    config_file: Path | None = typer.Option(
        None, "--file", "-f", help="Configuration file to use"
    ),
):
    """List available tool modules and their status"""

    try:
        # Load config to show current settings
        if not config_file:
            from nova.main import app

            config_file = (
                getattr(app.state, "config_file", None)
                if hasattr(app, "state")
                else None
            )

        config = config_manager.load_config(config_file)
        tools_config = config.get_effective_tools_config()

        # Get available modules
        available_modules = get_available_modules()

        print_info("Tool Modules")
        print()

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Module", style="cyan", no_wrap=True)
        table.add_column("Status", style="white", no_wrap=True)
        table.add_column("Tools Count", style="green", no_wrap=True)
        table.add_column("Description", style="blue")

        # Discover tools to get counts per module
        all_tools = discover_built_in_tools()
        tools_by_module = {}

        for tool_name, (tool_def, handler) in all_tools.items():
            module_name = get_module_name_from_tool_source(tool_def, handler)
            if module_name not in tools_by_module:
                tools_by_module[module_name] = []
            tools_by_module[module_name].append((tool_name, tool_def))

        # Module descriptions
        module_descriptions = {
            "text_tools": "Text processing and analysis tools",
            "network_tools": "Network and IP location tools",
            "file_ops": "File system operations",
            "web_search": "Web search and time tools",
            "conversation": "Chat conversation management",
        }

        for module_name in sorted(available_modules):
            enabled = module_name in tools_config.enabled_built_in_modules
            status = "[green]✓ Enabled[/green]" if enabled else "[red]✗ Disabled[/red]"

            tool_count = len(tools_by_module.get(module_name, []))
            description = module_descriptions.get(module_name, "Built-in tools module")

            table.add_row(module_name, status, str(tool_count), description)

        console.print(table)

        # Configuration instructions
        print()
        console.print("[cyan]To enable/disable modules:[/cyan]")
        console.print(
            "Edit the [white]enabled_built_in_modules[/white] list in your config file"
        )
        console.print()
        console.print("[dim]Example:[/dim]")
        console.print("[dim]tools:")
        console.print("  enabled_built_in_modules:")
        for module in available_modules:
            enabled = module in tools_config.enabled_built_in_modules
            prefix = "    - " if enabled else "    # - "
            console.print(f'[dim]{prefix}"{module}"[/dim]')

    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error listing modules: {e}")
        raise typer.Exit(1)


@tools_app.command("info")
def tool_info(
    tool_name: str = typer.Argument(help="Name of the tool to show information for"),
    config_file: Path | None = typer.Option(
        None, "--file", "-f", help="Configuration file to use"
    ),
):
    """Show detailed information about a specific tool"""

    try:
        # Discover tools
        all_tools = discover_all_tools()

        if tool_name not in all_tools:
            print_error(f"Tool '{tool_name}' not found")
            available_tools = list(all_tools.keys())
            if available_tools:
                console.print("\n[yellow]Available tools:[/yellow]")
                for name in sorted(available_tools)[:10]:  # Show first 10
                    console.print(f"  • {name}")
                if len(available_tools) > 10:
                    console.print(f"  ... and {len(available_tools) - 10} more")
            raise typer.Exit(1)

        tool_def, handler = all_tools[tool_name]
        module_name = get_module_name_from_tool_source(tool_def, handler)

        # Check if module is enabled
        if not config_file:
            from nova.main import app

            config_file = (
                getattr(app.state, "config_file", None)
                if hasattr(app, "state")
                else None
            )

        config = config_manager.load_config(config_file)
        tools_config = config.get_effective_tools_config()
        module_enabled = module_name in tools_config.enabled_built_in_modules

        console.print(f"\n[bold blue]Tool: {tool_name}[/bold blue]")
        console.print(f"[white]{tool_def.description}[/white]")

        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column("Key", style="cyan", no_wrap=True)
        info_table.add_column("Value", style="white")

        info_table.add_row("Module:", module_name)
        info_table.add_row("Category:", tool_def.category.value)
        info_table.add_row("Permission Level:", tool_def.permission_level.value)
        info_table.add_row("Tags:", ", ".join(tool_def.tags))
        info_table.add_row(
            "Module Status:",
            "[green]✓ Enabled[/green]" if module_enabled else "[red]✗ Disabled[/red]",
        )

        console.print(info_table)

        # Show parameters if available
        if hasattr(tool_def, "parameters") and tool_def.parameters:
            console.print("\n[bold green]Parameters:[/bold green]")
            if "properties" in tool_def.parameters:
                param_table = Table(show_header=True, header_style="bold magenta")
                param_table.add_column("Parameter", style="cyan")
                param_table.add_column("Type", style="yellow")
                param_table.add_column("Required", style="white")
                param_table.add_column("Description", style="blue")

                required_params = tool_def.parameters.get("required", [])

                for param_name, param_info in tool_def.parameters["properties"].items():
                    param_type = param_info.get("type", "unknown")
                    is_required = "Yes" if param_name in required_params else "No"
                    description = param_info.get("description", "No description")

                    param_table.add_row(
                        param_name, param_type, is_required, description
                    )

                console.print(param_table)

        # Show examples
        if tool_def.examples:
            console.print("\n[bold green]Examples:[/bold green]")
            for i, example in enumerate(tool_def.examples, 1):
                console.print(f"\n  [cyan]{i}. {example.description}[/cyan]")
                console.print(f"     [white]Arguments:[/white] {example.arguments}")
                if example.expected_result:
                    console.print(
                        f"     [white]Expected:[/white] {example.expected_result}"
                    )

        # Show configuration help if module is disabled
        if not module_enabled:
            console.print(
                f"\n[yellow]⚠️  This tool is disabled because module '{module_name}' is not enabled[/yellow]"
            )
            console.print(
                f"[white]To enable:[/white] Add '{module_name}' to enabled_built_in_modules in your config"
            )

    except ConfigError as e:
        print_error(f"Configuration error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Error getting tool info: {e}")
        raise typer.Exit(1)
