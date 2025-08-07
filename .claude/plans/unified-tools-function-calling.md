# Unified Tools and Function Calling Implementation Plan

## Overview
Implement a comprehensive, unified function calling system for Nova AI Assistant that seamlessly integrates built-in tools, MCP servers, and user-defined functions through a single, consistent interface.

## Architecture Design

### 1. Unified Function Registry
- **Location**: `nova/core/tools/`
- **Purpose**: Central registry for all callable functions regardless of source
- **Key Components**:
  - `FunctionRegistry`: Main orchestrator for tool discovery and execution
  - `ToolPermissionManager`: Security and permission management
  - `ToolExecutionEngine`: Async tool execution with error handling
  - `ToolSuggestionEngine`: Context-aware tool recommendations

### 2. Enhanced AI Client Integration
```python
# nova/core/ai_client.py - Enhanced base class
class BaseAIClient(ABC):
    def __init__(self, config: AIModelConfig, function_registry: FunctionRegistry = None):
        self.config = config
        self.function_registry = function_registry

    @abstractmethod
    async def generate_response_with_tools(
        self,
        messages: list[dict[str, str]],
        available_tools: list[dict] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> ToolAwareResponse:
        """Generate response with function calling support"""
        pass

    async def _execute_tool_calls(self, tool_calls: list) -> list[ToolResult]:
        """Execute tool calls and return results"""
        if not self.function_registry:
            raise AIError("Function registry not available")

        results = []
        for tool_call in tool_calls:
            try:
                result = await self.function_registry.execute_tool(
                    tool_call.function.name,
                    json.loads(tool_call.function.arguments)
                )
                results.append(result)
            except Exception as e:
                results.append(ToolResult(
                    success=False,
                    error=str(e),
                    tool_name=tool_call.function.name
                ))
        return results
```

### 3. Core Data Models
```python
# nova/models/tools.py
class ToolDefinition(BaseModel):
    """Universal tool definition"""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    parameters: dict = Field(description="JSON Schema for parameters")
    source_type: ToolSourceType = Field(description="Tool source")
    source_id: Optional[str] = Field(default=None, description="Source identifier (e.g., MCP server name)")
    permission_level: PermissionLevel = Field(default=PermissionLevel.SAFE)
    category: ToolCategory = Field(default=ToolCategory.GENERAL)
    tags: List[str] = Field(default_factory=list)
    examples: List[ToolExample] = Field(default_factory=list)

class ToolSourceType(str, Enum):
    BUILT_IN = "built_in"
    MCP_SERVER = "mcp_server"
    USER_DEFINED = "user_defined"
    PLUGIN = "plugin"

class PermissionLevel(str, Enum):
    SAFE = "safe"        # No user confirmation needed
    ELEVATED = "elevated" # User confirmation required
    SYSTEM = "system"     # Admin/explicit approval needed
    DANGEROUS = "dangerous" # Blocked by default

class ToolResult(BaseModel):
    """Tool execution result"""

    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    tool_name: str
    execution_time_ms: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolAwareResponse(BaseModel):
    """AI response that may include tool usage"""

    content: str
    tool_calls_made: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)
```

### 4. Function Registry Implementation
```python
# nova/core/tools/function_registry.py
class FunctionRegistry:
    """Unified registry for all callable functions"""

    def __init__(self, config: ToolsConfig):
        self.config = config
        self.tools: Dict[str, ToolDefinition] = {}
        self.handlers: Dict[str, ToolHandler] = {}
        self.permission_manager = ToolPermissionManager(config.permission_mode)
        self.suggestion_engine = ToolSuggestionEngine()

        # Built-in tool modules
        self.built_in_modules = {
            'file_ops': FileOperationsTools(),
            'web_search': WebSearchTools(),
            'tasks': TaskManagementTools(),
            'conversation': ConversationTools(),
            'system': SystemTools(),
            'code': CodeAnalysisTools()
        }

        # MCP integration
        self.mcp_client: Optional[MCPClient] = None

    async def initialize(self):
        """Initialize the function registry"""
        # Register built-in tools
        await self._register_built_in_tools()

        # Initialize MCP client if enabled
        if self.config.mcp_enabled:
            await self._initialize_mcp_integration()

        # Load user-defined tools
        await self._load_user_tools()

    def register_tool(self, tool: ToolDefinition, handler: ToolHandler) -> None:
        """Register a tool with its handler"""
        self.tools[tool.name] = tool
        self.handlers[tool.name] = handler

    async def execute_tool(self, tool_name: str, arguments: dict, context: ExecutionContext = None) -> ToolResult:
        """Execute a tool with permission checking"""
        if tool_name not in self.tools:
            raise ToolNotFoundError(f"Tool '{tool_name}' not found")

        tool = self.tools[tool_name]
        handler = self.handlers[tool_name]

        # Permission check
        if not await self.permission_manager.check_permission(tool, arguments, context):
            raise PermissionDeniedError(f"Permission denied for tool '{tool_name}'")

        # Execute with timeout and error handling
        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                handler.execute(arguments, context),
                timeout=self.config.execution_timeout
            )
            execution_time = int((time.time() - start_time) * 1000)

            return ToolResult(
                success=True,
                result=result,
                tool_name=tool_name,
                execution_time_ms=execution_time
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Tool execution timed out after {self.config.execution_timeout}s",
                tool_name=tool_name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=tool_name
            )

    def get_available_tools(self, context: Optional[ExecutionContext] = None) -> List[ToolDefinition]:
        """Get all available tools for current context"""
        available = []
        for tool in self.tools.values():
            if self.permission_manager.is_tool_available(tool, context):
                available.append(tool)
        return available

    def get_openai_tools_schema(self, context: Optional[ExecutionContext] = None) -> List[dict]:
        """Get OpenAI-compatible tools schema"""
        available_tools = self.get_available_tools(context)
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in available_tools
        ]

    async def suggest_tools(self, conversation: Conversation, user_input: str = None) -> List[str]:
        """Suggest relevant tools based on context"""
        return await self.suggestion_engine.suggest_tools(
            conversation, user_input, list(self.tools.keys())
        )

    async def _register_built_in_tools(self):
        """Register all built-in tools"""
        for module_name, module in self.built_in_modules.items():
            if module_name in self.config.enabled_built_in_modules:
                tools = await module.get_tools()
                for tool_def, handler in tools.items():
                    self.register_tool(tool_def, handler)

    async def _initialize_mcp_integration(self):
        """Initialize MCP client and register MCP tools"""
        if self.mcp_client:
            mcp_tools = await self.mcp_client.list_all_tools()
            for server_name, server_tools in mcp_tools.items():
                for mcp_tool in server_tools:
                    # Convert MCP tool to unified format
                    tool_def = ToolDefinition(
                        name=f"mcp_{server_name}_{mcp_tool.name}",
                        description=f"[{server_name}] {mcp_tool.description}",
                        parameters=mcp_tool.input_schema,
                        source_type=ToolSourceType.MCP_SERVER,
                        source_id=server_name,
                        permission_level=self._determine_mcp_permission_level(mcp_tool),
                        category=self._categorize_mcp_tool(mcp_tool)
                    )

                    # Create MCP tool handler
                    handler = MCPToolHandler(self.mcp_client, server_name, mcp_tool.name)
                    self.register_tool(tool_def, handler)
```

### 5. Built-in Tool Modules

#### File Operations
```python
# nova/core/tools/built_in/file_ops.py
class FileOperationsTools(BuiltInToolModule):
    """File system operations"""

    async def get_tools(self) -> Dict[ToolDefinition, ToolHandler]:
        return {
            ToolDefinition(
                name="read_file",
                description="Read the contents of a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the file to read"},
                        "encoding": {"type": "string", "default": "utf-8"}
                    },
                    "required": ["file_path"]
                },
                permission_level=PermissionLevel.SAFE,
                category=ToolCategory.FILE_SYSTEM
            ): ReadFileHandler(),

            ToolDefinition(
                name="write_file",
                description="Write content to a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path where to write the file"},
                        "content": {"type": "string", "description": "Content to write"},
                        "create_dirs": {"type": "boolean", "default": False}
                    },
                    "required": ["file_path", "content"]
                },
                permission_level=PermissionLevel.ELEVATED,
                category=ToolCategory.FILE_SYSTEM
            ): WriteFileHandler(),

            ToolDefinition(
                name="list_directory",
                description="List contents of a directory",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory_path": {"type": "string", "description": "Directory to list"},
                        "include_hidden": {"type": "boolean", "default": False}
                    },
                    "required": ["directory_path"]
                }
            ): ListDirectoryHandler()
        }
```

#### Web Search Enhancement
```python
# nova/core/tools/built_in/web_search.py
class WebSearchTools(BuiltInToolModule):
    """Enhanced web search capabilities"""

    async def get_tools(self) -> Dict[ToolDefinition, ToolHandler]:
        return {
            ToolDefinition(
                name="web_search",
                description="Search the web for information",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "provider": {"type": "string", "enum": ["duckduckgo", "google", "bing"]},
                        "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                        "include_content": {"type": "boolean", "default": True}
                    },
                    "required": ["query"]
                },
                permission_level=PermissionLevel.SAFE,
                category=ToolCategory.INFORMATION
            ): EnhancedWebSearchHandler(self.config.search)
        }
```

#### Task Management Integration
```python
# nova/core/tools/built_in/tasks.py
class TaskManagementTools(BuiltInToolModule):
    """Task and project management"""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager

    async def get_tools(self) -> Dict[ToolDefinition, ToolHandler]:
        return {
            ToolDefinition(
                name="create_task",
                description="Create a new task",
                parameters=TASK_CREATION_SCHEMA,
                permission_level=PermissionLevel.SAFE,
                category=ToolCategory.PRODUCTIVITY
            ): CreateTaskHandler(self.task_manager),

            ToolDefinition(
                name="list_tasks",
                description="List tasks with optional filtering",
                parameters=TASK_LIST_SCHEMA,
                permission_level=PermissionLevel.SAFE
            ): ListTasksHandler(self.task_manager),

            ToolDefinition(
                name="complete_task",
                description="Mark a task as completed",
                parameters=TASK_COMPLETION_SCHEMA,
                permission_level=PermissionLevel.SAFE
            ): CompleteTaskHandler(self.task_manager)
        }
```

### 6. Permission Management System
```python
# nova/core/tools/permissions.py
class ToolPermissionManager:
    """Manage tool execution permissions and security"""

    def __init__(self, permission_mode: str):
        self.permission_mode = permission_mode  # "auto", "prompt", "deny"
        self.user_permissions: Dict[str, PermissionLevel] = {}
        self.session_grants: Set[str] = set()

    async def check_permission(self, tool: ToolDefinition, arguments: dict,
                              context: ExecutionContext = None) -> bool:
        """Check if tool execution is permitted"""

        # Always allow safe tools
        if tool.permission_level == PermissionLevel.SAFE:
            return True

        # Block dangerous tools unless explicitly allowed
        if tool.permission_level == PermissionLevel.DANGEROUS:
            return tool.name in self.user_permissions.get(PermissionLevel.DANGEROUS, set())

        # Handle elevated permissions based on mode
        if tool.permission_level == PermissionLevel.ELEVATED:
            if self.permission_mode == "auto":
                return True
            elif self.permission_mode == "prompt":
                return await self._request_user_permission(tool, arguments, context)
            else:  # "deny"
                return False

        # System tools require explicit permission
        if tool.permission_level == PermissionLevel.SYSTEM:
            return await self._request_admin_permission(tool, arguments, context)

        return False

    async def _request_user_permission(self, tool: ToolDefinition, arguments: dict,
                                      context: ExecutionContext) -> bool:
        """Request user permission for tool execution"""

        # Check if already granted for this session
        permission_key = f"{tool.name}:{hash(str(arguments))}"
        if permission_key in self.session_grants:
            return True

        # Show permission request to user
        print_warning(f"🔐 Permission requested for tool: {tool.name}")
        print_info(f"Description: {tool.description}")
        print_info(f"Arguments: {arguments}")

        if self._is_potentially_destructive(tool, arguments):
            print_warning("⚠️  This operation may modify files or system state")

        response = input("Allow this tool execution? [y/N/always]: ").strip().lower()

        if response in ['y', 'yes']:
            return True
        elif response == 'always':
            self.session_grants.add(permission_key)
            return True
        else:
            return False

    def _is_potentially_destructive(self, tool: ToolDefinition, arguments: dict) -> bool:
        """Check if tool operation is potentially destructive"""
        destructive_patterns = [
            ('write_file', lambda args: True),
            ('delete_file', lambda args: True),
            ('run_command', lambda args: any(cmd in args.get('command', '')
                                           for cmd in ['rm', 'del', 'format', 'shutdown'])),
            ('modify_database', lambda args: 'DELETE' in args.get('query', '').upper())
        ]

        for pattern_name, checker in destructive_patterns:
            if pattern_name in tool.name.lower() and checker(arguments):
                return True

        return False
```

### 7. Enhanced Chat Integration
```python
# nova/core/chat.py - Enhanced ChatSession
class ChatSession:
    def __init__(self, config: NovaConfig, conversation_id: str = None):
        # ... existing init
        self.function_registry = FunctionRegistry(config.tools)
        await self.function_registry.initialize()

        # Enhance AI client with function registry
        if hasattr(self.ai_client, 'function_registry'):
            self.ai_client.function_registry = self.function_registry

    async def _generate_ai_response_with_tools(self, session: ChatSession) -> str:
        """Generate AI response with tool support"""

        # Get optimized context
        context_messages = session.get_context_messages()

        # Get available tools for current context
        execution_context = ExecutionContext(
            conversation_id=session.conversation.id,
            user_id=None,  # Could be added later
            session_data={}
        )

        available_tools = self.function_registry.get_openai_tools_schema(execution_context)

        # Build messages with system prompt
        messages = []
        if self.config.get_active_ai_config().provider in ["openai", "ollama"]:
            system_prompt = self._build_system_prompt(session)
            if available_tools:
                system_prompt += f"\n\nYou have access to {len(available_tools)} tools. Use them when helpful to assist the user."
            messages.append({"role": "system", "content": system_prompt})

        messages.extend(context_messages)

        # Generate response with tools
        try:
            if available_tools and hasattr(self.ai_client, 'generate_response_with_tools'):
                tool_response = await self.ai_client.generate_response_with_tools(
                    messages=messages,
                    available_tools=available_tools
                )

                # Handle tool results
                if tool_response.tool_calls_made:
                    return self._format_tool_response(tool_response)
                else:
                    return tool_response.content
            else:
                # Fallback to regular response
                return await self.ai_client.generate_response(messages)

        except Exception as e:
            raise AIError(f"Failed to generate response: {e}")

    def _format_tool_response(self, tool_response: ToolAwareResponse) -> str:
        """Format response that includes tool usage"""

        response_parts = [tool_response.content]

        # Add tool execution summaries if helpful
        successful_tools = [r for r in tool_response.tool_results if r.success]
        if successful_tools:
            response_parts.append(f"\n*Used {len(successful_tools)} tool(s) to help with this response*")

        # Show failed tools
        failed_tools = [r for r in tool_response.tool_results if not r.success]
        if failed_tools:
            response_parts.append(f"\n*Note: {len(failed_tools)} tool(s) failed to execute*")

        return "\n".join(response_parts)
```

### 8. Configuration Integration
```python
# nova/models/config.py - Enhanced configuration
class ToolsConfig(BaseModel):
    """Tools and function calling configuration"""

    enabled: bool = Field(default=True, description="Enable function calling")

    # Built-in tools
    enabled_built_in_modules: List[str] = Field(
        default_factory=lambda: ["file_ops", "web_search", "conversation", "tasks"],
        description="Enabled built-in tool modules"
    )

    # Permission settings
    permission_mode: str = Field(
        default="prompt",
        description="Permission mode: auto, prompt, deny",
        enum=["auto", "prompt", "deny"]
    )

    # Execution settings
    execution_timeout: int = Field(default=30, description="Tool execution timeout (seconds)")
    max_concurrent_tools: int = Field(default=3, description="Max concurrent tool executions")

    # MCP integration (unified with existing MCP plan)
    mcp_enabled: bool = Field(default=False, description="Enable MCP server integration")
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

    # Advanced features
    tool_suggestions: bool = Field(default=True, description="Enable AI tool suggestions")
    execution_logging: bool = Field(default=True, description="Log tool executions")

class NovaConfig(BaseModel):
    # ... existing fields
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
```

## Implementation Phases

### Phase 1: Core Function Calling Infrastructure (2-3 weeks)
**Scope**: Basic function calling with essential built-in tools
- Unified `FunctionRegistry` and core tool infrastructure
- Enhanced AI clients with function calling support
- Essential built-in tools (file ops, web search, conversation)
- Basic permission system and security
- Chat integration with tool-aware responses

**Deliverables**:
- Complete function calling infrastructure
- File operations, web search, and conversation tools
- Permission management system
- Enhanced AI client integration
- Basic chat commands for tool management

### Phase 2: MCP Integration and Advanced Tools (4-6 weeks)
**Scope**: Full MCP integration and advanced built-in tools
- Complete MCP client integration (using existing detailed MCP plan)
- Task management tools integration
- Code analysis and system tools
- Advanced permission features and security
- Tool suggestion engine

**Deliverables**:
- Full MCP server support with all transports
- Task management tool suite
- Advanced security and permission features
- Tool analytics and monitoring
- Comprehensive documentation

### Phase 3: Advanced Features and Polish (2-3 weeks)
**Scope**: User-defined tools, workflows, and optimization
- User-defined tool support
- Tool workflow automation
- Performance optimization and caching
- Advanced tool discovery and marketplace features
- Comprehensive testing and documentation

**Deliverables**:
- User-defined tool framework
- Tool workflow automation
- Performance optimizations
- Advanced discovery features
- Complete testing suite

## Usage Examples

### Seamless AI Function Calling
```bash
# User: "Read my project README and summarize it"
# → AI automatically calls read_file tool, then provides summary

# User: "Search for the latest news about AI and create tasks for key developments"
# → AI calls web_search, then create_task for each significant item

# User: "What files are in my Documents folder?"
# → AI calls list_directory tool automatically
```

### Explicit Tool Commands
```bash
# Direct tool execution
/tool read_file --file_path README.md
/tool web_search --query "Python async best practices" --max_results 3

# Tool management
/tools list                    # Show available tools
/tools permissions            # Manage tool permissions
/tools suggest               # Get tool suggestions for current context
```

### MCP Integration
```bash
# MCP server management (seamlessly integrated)
/mcp status                  # Show MCP server status
/tools mcp filesystem list   # List filesystem MCP tools
# All MCP tools appear in main tool list automatically
```

## Success Criteria

### Technical Metrics
- Tool execution latency < 200ms (95th percentile)
- 99.9% tool execution reliability
- Zero security incidents with permission system
- Support for 15+ built-in tools and unlimited MCP tools

### User Experience
- Seamless AI tool integration without user awareness needed
- Intuitive permission system with clear security indicators
- Comprehensive tool discovery and suggestion
- Unified experience for built-in and MCP tools

### Adoption Metrics
- 80%+ of users actively use AI function calling
- High satisfaction with tool suggestions and automation
- Active usage of both built-in and MCP tools
- Positive feedback from developers integrating custom tools

---

**Status**: Planning Phase
**Priority**: Critical
**Estimated Effort**: 8-12 weeks total
**Dependencies**: Core chat system stable, Configuration system ready
**Next Steps**:
1. Review and approve unified architecture approach
2. Begin Phase 1 implementation with core infrastructure
3. Set up comprehensive testing framework
4. Engage with MCP community for integration validation
5. Create detailed API documentation and examples
