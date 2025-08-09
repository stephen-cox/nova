# MCP (Model Context Protocol) Integration Plan

## Overview
Add comprehensive Model Context Protocol (MCP) support to Nova AI Assistant as part of the unified tools and function calling system, enabling seamless integration with external tools, services, and data sources through standardized MCP servers.

**Note**: This plan is integrated with the [Unified Tools and Function Calling Plan](./unified-tools-function-calling.md) to provide a cohesive tool ecosystem.

## MCP Background

### What is MCP?
Model Context Protocol (MCP) is an open standard that enables AI assistants to connect with external tools and data sources through a standardized interface. It provides:
- **Tools**: Function calling capabilities
- **Resources**: Access to external data (files, databases, APIs)
- **Prompts**: Reusable prompt templates
- **Sampling**: AI model interaction capabilities

### Unified Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   Nova AI Assistant                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Unified Function Registry              │   │
│  │  ┌─────────────┐  ┌─────────────┐ ┌────────────┐ │   │
│  │  │ Built-in    │  │ MCP Tools   │ │ User Tools │ │   │
│  │  │ Tools       │  │ (via MCP    │ │ (Custom)   │ │   │
│  │  │             │  │  Servers)   │ │            │ │   │
│  │  └─────────────┘  └─────────────┘ └────────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│           ┌─────────────────────────────┐               │
│           │     AI Clients with         │               │
│           │   Function Calling          │               │
│           │ (OpenAI, Anthropic, Ollama) │               │
│           └─────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼ MCP Protocol
        ┌─────────────────┐    ┌─────────────────┐
        │   MCP Server    │    │   MCP Server    │
        │  (Filesystem)   │    │   (GitHub)      │
        └─────────────────┘    └─────────────────┘
```

## Architecture Design

### 1. MCP Integration within Unified System
- **Location**: `nova/core/tools/mcp/`
- **Purpose**: MCP client implementation that integrates with the unified function registry
- **Key Components**:
  - `MCPClient`: Main MCP protocol client
  - `MCPServerManager`: Manage multiple MCP server connections
  - `MCPTransport`: Handle different transport mechanisms (stdio, HTTP, WebSocket)
  - `MCPToolHandler`: Adapter to convert MCP tools to unified tool interface
  - `MCPRegistry`: Server discovery and configuration

### 2. MCP Protocol Implementation
- **Protocol Version**: MCP 1.0 specification
- **Transport Support**:
  - **stdio**: Process-based servers (most common)
  - **HTTP**: REST API-based servers
  - **WebSocket**: Real-time bidirectional servers
- **Message Types**:
  - Tools (function calling) → Integrated with unified function registry
  - Resources (data access) → Exposed as specialized tools
  - Prompts (template sharing) → Integrated with Nova's prompt system
  - Sampling (AI model calls) → Advanced feature for meta-AI workflows

### 3. Integration with Unified Function Registry
```python
# nova/core/tools/mcp/mcp_integration.py
class MCPToolHandler(ToolHandler):
    """Adapter to execute MCP tools through unified interface"""

    def __init__(self, mcp_client: MCPClient, server_name: str, tool_name: str):
        self.mcp_client = mcp_client
        self.server_name = server_name
        self.tool_name = tool_name

    async def execute(self, arguments: dict, context: ExecutionContext) -> Any:
        """Execute MCP tool and return result"""
        return await self.mcp_client.call_tool(
            self.server_name,
            self.tool_name,
            arguments
        )

class MCPIntegrationManager:
    """Manages MCP integration with unified function registry"""

    def __init__(self, function_registry: FunctionRegistry):
        self.function_registry = function_registry
        self.mcp_client: Optional[MCPClient] = None
        self.active_servers: Dict[str, MCPServerConnection] = {}

    async def initialize(self, mcp_config: MCPConfig):
        """Initialize MCP integration"""
        if not mcp_config.enabled:
            return

        self.mcp_client = MCPClient(mcp_config)
        await self._start_configured_servers(mcp_config.servers)
        await self._register_mcp_tools()

    async def _register_mcp_tools(self):
        """Register all MCP tools with the unified function registry"""
        if not self.mcp_client:
            return

        mcp_tools = await self.mcp_client.list_all_tools()
        for server_name, server_tools in mcp_tools.items():
            for mcp_tool in server_tools:
                # Convert MCP tool to unified tool definition
                tool_def = self._convert_mcp_tool_to_unified(mcp_tool, server_name)

                # Create handler for this MCP tool
                handler = MCPToolHandler(self.mcp_client, server_name, mcp_tool.name)

                # Register with unified function registry
                self.function_registry.register_tool(tool_def, handler)

    def _convert_mcp_tool_to_unified(self, mcp_tool: MCPTool, server_name: str) -> ToolDefinition:
        """Convert MCP tool definition to unified format"""
        return ToolDefinition(
            name=f"mcp_{server_name}_{mcp_tool.name}",
            description=f"[{server_name}] {mcp_tool.description}",
            parameters=mcp_tool.input_schema,
            source_type=ToolSourceType.MCP_SERVER,
            source_id=server_name,
            permission_level=self._determine_permission_level(mcp_tool),
            category=self._categorize_tool(mcp_tool),
            tags=[server_name, "mcp"] + (mcp_tool.tags or [])
        )
```

## Core MCP Features

**Note**: All MCP tools are exposed through the unified function calling interface - users interact with them seamlessly alongside built-in tools.

### 1. MCP Server Management

#### Server Configuration
```yaml
# Example MCP server configurations
mcp:
  enabled: true
  servers:
    filesystem:
      name: "File System Access"
      command: ["npx", "@modelcontextprotocol/server-filesystem", "/Users/user/Documents"]
      transport: "stdio"
      enabled: true
      auto_start: true
      timeout: 30

    sqlite:
      name: "SQLite Database"
      command: ["mcp-server-sqlite", "--db-path", "/path/to/database.db"]
      transport: "stdio"
      enabled: true

    github:
      name: "GitHub Integration"
      command: ["mcp-server-github"]
      transport: "stdio"
      enabled: false
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"

    weather:
      name: "Weather Service"
      url: "http://localhost:3001/mcp"
      transport: "http"
      enabled: true
      headers:
        Authorization: "Bearer ${WEATHER_API_KEY}"

    slack:
      name: "Slack Integration"
      url: "ws://localhost:3002/mcp"
      transport: "websocket"
      enabled: false
```

#### Server Discovery and Auto-Configuration
```python
class MCPServerRegistry:
    """Discover and manage MCP servers"""

    def discover_servers(self) -> List[MCPServerConfig]:
        """Auto-discover available MCP servers"""
        # Check common installation paths
        # Scan npm global packages for MCP servers
        # Check Python packages for MCP servers
        # Look for registered MCP servers in system

    def validate_server(self, config: MCPServerConfig) -> ValidationResult:
        """Validate server configuration and availability"""

    def install_server(self, server_name: str) -> bool:
        """Install MCP server from registry"""
```

### 2. Tool Integration

#### MCP Tool Execution
```python
class MCPToolHandler:
    """Handle MCP tool execution"""

    async def execute_tool(self, server_name: str, tool_name: str,
                          arguments: dict) -> ToolResult:
        """Execute tool on specific MCP server"""

    async def list_available_tools(self) -> Dict[str, List[MCPTool]]:
        """List all available tools from all servers"""

    def get_tool_schema(self, server_name: str, tool_name: str) -> dict:
        """Get OpenAI-compatible tool schema for AI models"""
```

#### Function Calling Integration
```python
# Integration with existing AI clients
def _get_available_tools(self) -> List[dict]:
    """Get all available tools for AI function calling"""

    tools = []

    # Add MCP tools
    if self.mcp_client:
        mcp_tools = await self.mcp_client.list_tools()
        for server_name, server_tools in mcp_tools.items():
            for tool in server_tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{server_name}_{tool.name}",
                        "description": tool.description,
                        "parameters": tool.input_schema
                    }
                })

    return tools
```

### 3. Resource Access

#### MCP Resource Management
```python
class MCPResourceManager:
    """Manage MCP resources (files, databases, APIs)"""

    async def list_resources(self, server_name: str = None) -> List[MCPResource]:
        """List available resources"""

    async def read_resource(self, resource_uri: str) -> ResourceContent:
        """Read resource content"""

    async def subscribe_to_resource(self, resource_uri: str,
                                   callback: Callable) -> str:
        """Subscribe to resource changes"""

    def get_resource_info(self, resource_uri: str) -> ResourceInfo:
        """Get resource metadata and capabilities"""
```

#### Resource URI Handling
```python
# Example resource URIs
file_resource = "file:///Users/user/Documents/project/README.md"
db_resource = "sqlite:///path/to/database.db#table:users"
api_resource = "http://api.example.com/users/123"
github_resource = "github://owner/repo/path/to/file.md"
```

### 4. Prompt Sharing

#### MCP Prompt Integration
```python
class MCPPromptProvider:
    """Integrate MCP prompts with Nova's prompt system"""

    async def fetch_prompts(self, server_name: str) -> List[MCPPrompt]:
        """Fetch prompts from MCP server"""

    def convert_to_nova_template(self, mcp_prompt: MCPPrompt) -> PromptTemplate:
        """Convert MCP prompt to Nova template format"""

    async def sync_prompts(self) -> None:
        """Synchronize MCP prompts with local library"""
```

## Implementation Details

### 1. Core MCP Client

#### MCPClient Class
```python
class MCPClient:
    """Main MCP protocol client"""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.servers: Dict[str, MCPServerConnection] = {}
        self.transport_handlers = {
            'stdio': StdioTransport,
            'http': HTTPTransport,
            'websocket': WebSocketTransport
        }

    async def start_server(self, server_config: MCPServerConfig) -> bool:
        """Start and connect to MCP server"""

    async def stop_server(self, server_name: str) -> None:
        """Stop MCP server connection"""

    async def list_capabilities(self, server_name: str) -> ServerCapabilities:
        """Get server capabilities"""

    async def call_tool(self, server_name: str, tool_name: str,
                       arguments: dict) -> ToolResult:
        """Execute tool on server"""

    async def read_resource(self, server_name: str,
                           resource_uri: str) -> ResourceContent:
        """Read resource from server"""

    async def get_prompt(self, server_name: str,
                        prompt_name: str, arguments: dict = None) -> str:
        """Get prompt from server"""
```

#### Transport Implementations
```python
class StdioTransport:
    """stdio-based MCP transport (most common)"""

    async def start(self, command: List[str], env: dict = None) -> None:
        """Start process and establish stdio communication"""

    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send JSON-RPC request over stdio"""

class HTTPTransport:
    """HTTP-based MCP transport"""

    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send HTTP request to MCP server"""

class WebSocketTransport:
    """WebSocket-based MCP transport"""

    async def connect(self, url: str, headers: dict = None) -> None:
        """Connect to WebSocket MCP server"""

    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send request over WebSocket"""
```

### 2. Configuration Models

#### MCP Configuration
```python
class MCPServerConfig(BaseModel):
    """Individual MCP server configuration"""

    name: str = Field(description="Server display name")
    command: List[str] | None = Field(default=None, description="Command to start server (stdio)")
    url: str | None = Field(default=None, description="Server URL (HTTP/WebSocket)")
    transport: Literal["stdio", "http", "websocket"] = Field(default="stdio")
    enabled: bool = Field(default=True, description="Enable this server")
    auto_start: bool = Field(default=True, description="Auto-start on Nova startup")
    timeout: int = Field(default=30, description="Connection timeout seconds")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")

class MCPConfig(BaseModel):
    """MCP system configuration"""

    enabled: bool = Field(default=False, description="Enable MCP support")
    servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    auto_discovery: bool = Field(default=True, description="Auto-discover MCP servers")
    max_concurrent_requests: int = Field(default=10, description="Max concurrent requests per server")
    request_timeout: int = Field(default=30, description="Default request timeout")
    retry_attempts: int = Field(default=3, description="Retry failed requests")

class NovaConfig(BaseModel):
    # ... existing fields
    mcp: MCPConfig = Field(default_factory=MCPConfig)
```

### 3. Chat Integration

#### MCP Commands
```python
# Add to ChatManager._handle_command()

elif cmd == "/mcp status":
    # Show MCP server status
    await self._show_mcp_status()

elif cmd == "/mcp servers":
    # List available MCP servers
    self._list_mcp_servers()

elif cmd.startswith("/mcp start "):
    # Start specific MCP server
    server_name = cmd[11:].strip()
    await self._start_mcp_server(server_name)

elif cmd.startswith("/mcp stop "):
    # Stop specific MCP server
    server_name = cmd[10:].strip()
    await self._stop_mcp_server(server_name)

elif cmd == "/mcp tools":
    # List available MCP tools
    await self._list_mcp_tools()

elif cmd == "/mcp resources":
    # List available MCP resources
    await self._list_mcp_resources()

elif cmd.startswith("/mcp read "):
    # Read MCP resource
    resource_uri = cmd[10:].strip()
    await self._read_mcp_resource(resource_uri)
```

#### Automatic Tool Discovery
```python
class ChatSession:
    def __init__(self, config: NovaConfig, conversation_id: str | None = None):
        # ... existing init
        self.mcp_client = MCPClient(config.mcp) if config.mcp.enabled else None
        if self.mcp_client:
            asyncio.create_task(self._initialize_mcp_servers())

    async def _initialize_mcp_servers(self):
        """Initialize configured MCP servers"""
        for server_name, server_config in self.config.mcp.servers.items():
            if server_config.enabled and server_config.auto_start:
                try:
                    await self.mcp_client.start_server(server_config)
                    print_success(f"Started MCP server: {server_name}")
                except Exception as e:
                    print_error(f"Failed to start MCP server {server_name}: {e}")

    async def get_available_tools(self) -> List[dict]:
        """Get all available tools including MCP tools"""
        tools = []

        # Add MCP tools if available
        if self.mcp_client:
            try:
                mcp_tools = await self.mcp_client.list_all_tools()
                for server_name, server_tools in mcp_tools.items():
                    for tool in server_tools:
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": f"mcp_{server_name}_{tool.name}",
                                "description": f"[{server_name}] {tool.description}",
                                "parameters": tool.input_schema
                            }
                        })
            except Exception as e:
                print_error(f"Failed to load MCP tools: {e}")

        return tools
```

### 4. Popular MCP Servers Integration

#### Built-in Server Configurations
```python
POPULAR_MCP_SERVERS = {
    "filesystem": {
        "name": "File System Access",
        "command": ["npx", "@modelcontextprotocol/server-filesystem"],
        "description": "Access local file system",
        "install_command": "npm install -g @modelcontextprotocol/server-filesystem"
    },
    "sqlite": {
        "name": "SQLite Database",
        "command": ["mcp-server-sqlite"],
        "description": "Query SQLite databases",
        "install_command": "pip install mcp-server-sqlite"
    },
    "github": {
        "name": "GitHub Integration",
        "command": ["mcp-server-github"],
        "description": "Access GitHub repositories",
        "install_command": "pip install mcp-server-github"
    },
    "postgres": {
        "name": "PostgreSQL Database",
        "command": ["mcp-server-postgres"],
        "description": "Query PostgreSQL databases",
        "install_command": "pip install mcp-server-postgres"
    },
    "brave-search": {
        "name": "Brave Search",
        "command": ["mcp-server-brave-search"],
        "description": "Web search using Brave Search API",
        "install_command": "pip install mcp-server-brave-search"
    },
    "google-drive": {
        "name": "Google Drive",
        "command": ["mcp-server-google-drive"],
        "description": "Access Google Drive files",
        "install_command": "pip install mcp-server-google-drive"
    }
}
```

#### MCP Server Installation Helper
```python
class MCPServerInstaller:
    """Help users install and configure MCP servers"""

    def list_available_servers(self) -> List[dict]:
        """List popular MCP servers available for installation"""

    async def install_server(self, server_id: str) -> bool:
        """Install MCP server using appropriate package manager"""

    def generate_config(self, server_id: str, **kwargs) -> MCPServerConfig:
        """Generate configuration for installed server"""

    def validate_installation(self, server_id: str) -> bool:
        """Validate that server is properly installed"""
```

## Required Dependencies

### Core MCP Dependencies
```toml
[project.optional-dependencies]
mcp = [
    "mcp>=1.0.0",                    # Official MCP Python SDK
    "asyncio-subprocess>=0.1.0",     # Process management
    "websockets>=12.0",              # WebSocket transport
    "httpx>=0.25.0",                # HTTP transport
    "jsonschema>=4.0.0",            # Schema validation
    "typing-extensions>=4.5.0",     # Enhanced typing support
]

# Development dependencies for MCP server testing
mcp-dev = [
    "mcp-server-filesystem>=0.1.0", # File system server for testing
    "mcp-server-sqlite>=0.1.0",     # SQLite server for testing
]
```

## Implementation Integration with Unified System

**Note**: MCP implementation is integrated into the unified tools system phases:

### Phase 1: Integrated with Unified Tools Core (Week 2-3 of unified plan)
**Scope**: Basic MCP integration alongside built-in tools
- `MCPClient` core implementation with stdio transport
- `MCPIntegrationManager` for registry integration
- Basic MCP tool registration and execution
- MCP server lifecycle management

**Integration Points**:
- MCP tools registered in unified `FunctionRegistry`
- MCP tools available through standard AI function calling
- Unified permission system covers MCP tools
- Standard chat commands work with MCP tools

### Phase 2: Full MCP Features (Week 4-6 of unified plan)
**Scope**: Complete MCP protocol support and advanced features
- Multi-transport support (HTTP, WebSocket, stdio)
- Resource access and management
- MCP prompt integration with Nova's prompt system
- Server auto-discovery and installation helpers

**Integration Points**:
- MCP resources exposed as specialized tools
- MCP prompts sync with Nova's prompt library
- Advanced MCP features in unified tool suggestion engine
- Comprehensive MCP server management

### Phase 3: MCP Optimization and Polish (Week 7-8 of unified plan)
**Scope**: Performance optimization and ecosystem integration
- Performance optimization and caching for MCP calls
- Popular MCP server configuration templates
- Advanced MCP workflows and automation
- Community MCP server discovery

**Integration Points**:
- MCP tools participate in unified tool workflows
- MCP server marketplace and discovery
- Advanced MCP analytics and monitoring
- Complete integration testing

## Popular MCP Servers to Support

### Development Tools
- **GitHub**: Repository access, issue management, code search
- **GitLab**: Project management, CI/CD integration
- **Docker**: Container management and deployment
- **Kubernetes**: Cluster management and monitoring

### Data Sources
- **SQLite/PostgreSQL/MySQL**: Database querying and management
- **Filesystem**: Local file access and manipulation
- **Google Drive/Dropbox**: Cloud storage integration
- **Notion**: Knowledge base access
- **Airtable**: Database and spreadsheet integration

### External Services
- **Slack**: Team communication and workflow
- **Jira**: Project management and issue tracking
- **Calendar**: Google Calendar, Outlook integration
- **Email**: Gmail, Outlook email management
- **Weather**: Weather data and forecasts

### AI and Search
- **Brave Search**: Web search functionality
- **Tavily**: AI-optimized search
- **Perplexity**: Research and fact-checking
- **Wolfram Alpha**: Computational knowledge

## Usage Examples

### Seamless AI Integration (Primary Usage)
```bash
# User interactions are identical to built-in tools - MCP tools work transparently

# User: "Read the README.md file in my project"
# → AI automatically calls mcp_filesystem_read_file if filesystem MCP server is active
# → Or falls back to built-in read_file tool

# User: "Search GitHub for Python async examples"
# → AI calls mcp_github_search tool automatically

# User: "What's the weather like in San Francisco?"
# → AI calls mcp_weather_get_current tool if weather MCP server configured

# User: "List all my tasks and analyze the database"
# → AI calls built-in list_tasks AND mcp_sqlite_query seamlessly
```

### Unified Tool Interface
```bash
# All tools (built-in and MCP) appear in unified commands
/tools list                          # Shows ALL available tools
/tools list --source mcp_server      # Filter to MCP tools only
/tools list --source built_in        # Filter to built-in tools

# Execute any tool directly
/tool mcp_github_search --query "python async"
/tool mcp_filesystem_read --path README.md
```

### MCP-Specific Management
```bash
# MCP server management
/mcp status                    # Show MCP server status
/mcp start github             # Start GitHub MCP server
/mcp stop filesystem          # Stop filesystem MCP server
/mcp install brave-search     # Install new MCP server

# MCP resource access (exposed as tools)
/tool mcp_filesystem_list --directory /Users/user/Documents
/tool mcp_database_query --query "SELECT * FROM users LIMIT 10"
```

## Security and Safety Considerations

### Security Measures
- **Sandboxing**: Isolate MCP server processes
- **Permission System**: User approval for sensitive operations
- **Resource Limits**: Prevent resource exhaustion
- **Input Validation**: Validate all MCP requests and responses
- **Transport Security**: TLS for HTTP/WebSocket connections

### Safety Features
```python
class MCPSecurityManager:
    """Manage MCP security and permissions"""

    def validate_tool_call(self, server_name: str, tool_name: str,
                          arguments: dict) -> bool:
        """Validate tool call safety"""

    def check_resource_access(self, resource_uri: str) -> bool:
        """Check if resource access is allowed"""

    def approve_sensitive_operation(self, operation: str) -> bool:
        """Request user approval for sensitive operations"""
```

## Quality Assurance

### Testing Strategy
- **Unit Tests**: Individual MCP components
- **Integration Tests**: End-to-end MCP workflows with real servers
- **Mock Testing**: Simulated MCP servers for consistent testing
- **Security Tests**: Permission and sandboxing validation
- **Performance Tests**: Latency and throughput measurement

### Documentation Requirements
- **User Guide**: Setting up and using MCP servers
- **Server Development**: Creating custom MCP servers
- **Integration Guide**: Adding MCP support to existing workflows
- **Troubleshooting**: Common issues and solutions
- **Security Guide**: Best practices for safe MCP usage

## Success Criteria

### Technical Metrics
- MCP request latency < 500ms (95th percentile)
- Server connection success rate > 98%
- Zero security incidents in first 6 months
- Support for 10+ popular MCP servers

### User Experience
- Seamless integration with existing Nova workflows
- Intuitive server management and configuration
- Clear error messages and troubleshooting guidance
- Automatic tool discovery and suggestions

### Adoption Metrics
- 70%+ of users enable MCP functionality
- 5+ MCP servers actively used by community
- Positive feedback from MCP server developers
- Integration with major development workflows

---

**Status**: Planning Phase - Integrated with Unified Tools Plan
**Priority**: High
**Estimated Effort**: Integrated into 8-12 week unified tools plan
**Dependencies**: Unified function calling infrastructure, Core chat system stable
**Integration Notes**:
- MCP implementation runs parallel to built-in tool development
- Shared infrastructure reduces total development time
- Unified user experience from day one
- No separate MCP learning curve for users

**Next Steps**:
1. Begin unified tools infrastructure (includes MCP integration points)
2. Set up development environment with test MCP servers
3. Implement MCP client alongside built-in tools (Phase 1)
4. Create comprehensive testing framework covering both systems
5. Engage with MCP community for validation and popular server support
