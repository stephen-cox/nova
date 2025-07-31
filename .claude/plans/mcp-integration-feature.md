# MCP (Model Context Protocol) Integration Plan

## Overview
Add comprehensive Model Context Protocol (MCP) support to Nova AI Assistant, enabling integration with external tools, services, and data sources through standardized MCP servers.

## MCP Background

### What is MCP?
Model Context Protocol (MCP) is an open standard that enables AI assistants to connect with external tools and data sources through a standardized interface. It provides:
- **Tools**: Function calling capabilities
- **Resources**: Access to external data (files, databases, APIs)
- **Prompts**: Reusable prompt templates
- **Sampling**: AI model interaction capabilities

### MCP Architecture
```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐
│   Nova Client   │ ◄──────────────► │   MCP Server    │
│   (MCP Client)  │                   │  (Tool/Service) │
└─────────────────┘                   └─────────────────┘
```

## Architecture Design

### 1. MCP Client Integration
- **Location**: `nova/core/mcp/`
- **Purpose**: Core MCP client implementation and server management
- **Key Components**:
  - `MCPClient`: Main MCP protocol client
  - `MCPServerManager`: Manage multiple MCP server connections
  - `MCPTransport`: Handle different transport mechanisms (stdio, HTTP, WebSocket)
  - `MCPRegistry`: Server discovery and configuration

### 2. MCP Protocol Implementation
- **Protocol Version**: MCP 1.0 specification
- **Transport Support**:
  - **stdio**: Process-based servers (most common)
  - **HTTP**: REST API-based servers
  - **WebSocket**: Real-time bidirectional servers
- **Message Types**:
  - Tools (function calling)
  - Resources (data access)
  - Prompts (template sharing)
  - Sampling (AI model calls)

### 3. Configuration Extension
- **Location**: `nova/models/config.py`
- **New Models**:
  - `MCPConfig`: MCP-specific configuration
  - `MCPServer`: Individual server configuration
  - Integration with existing `NovaConfig`

## Core Features

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

## Implementation Phases

### Phase 1: Core MCP Client (3-4 weeks)
**Scope**: Basic MCP protocol implementation
- MCP protocol client with stdio transport
- Basic server management and connection handling
- Tool execution framework
- Configuration models and basic chat commands

**Features**:
- Connect to stdio-based MCP servers
- Execute tools with function calling
- Basic server lifecycle management
- Configuration via YAML files

**Deliverables**:
- `MCPClient` core implementation
- `StdioTransport` for process-based servers
- Basic configuration models
- Essential chat commands (`/mcp status`, `/mcp tools`)

### Phase 2: Multi-Transport and Resources (2-3 weeks)
**Scope**: Full transport support and resource access
- HTTP and WebSocket transport implementations
- Resource reading and management
- Server auto-discovery
- Enhanced error handling and reconnection

**Features**:
- Support for HTTP and WebSocket MCP servers
- Resource access and content reading
- Automatic server discovery and installation helpers
- Robust error handling and reconnection logic

**Deliverables**:
- `HTTPTransport` and `WebSocketTransport`
- `MCPResourceManager` for resource access
- `MCPServerRegistry` for server discovery
- Enhanced chat commands for resource management

### Phase 3: Advanced Features and Integration (2-3 weeks)
**Scope**: Prompt integration, optimization, and polish
- MCP prompt integration with Nova's prompt system
- Performance optimization and caching
- Comprehensive testing and documentation
- Popular server configurations and helpers

**Features**:
- MCP prompt synchronization with local library
- Request caching and performance optimization
- Comprehensive server configuration templates
- Full documentation and user guides

**Deliverables**:
- `MCPPromptProvider` for prompt integration
- Performance optimizations and caching
- Popular MCP server configuration templates
- Complete documentation and examples

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

### Basic Tool Usage
```bash
# Start Nova with MCP support
nova config set mcp.enabled true
nova chat start

# List available MCP tools
/mcp tools

# The AI can now automatically use MCP tools:
"Can you read the README.md file in my current project?"
# → Automatically calls filesystem MCP server

"What's the weather like in San Francisco?"
# → Calls weather MCP server if configured
```

### Resource Access
```bash
# List available resources
/mcp resources

# Read specific resource
/mcp read file:///Users/user/Documents/project.md

# The AI can access resources contextually:
"Analyze the data in my sales database"
# → Accesses SQLite MCP server to query database
```

### Server Management
```bash
# Check server status
/mcp status

# Start/stop specific servers
/mcp start github
/mcp stop filesystem

# Install new MCP server
nova mcp install brave-search
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

**Status**: Planning Phase
**Priority**: High
**Estimated Effort**: 7-10 weeks total
**Dependencies**: Core chat system stable, Function calling implemented
**Next Steps**:
1. Review MCP specification and reference implementations
2. Set up development environment with test MCP servers
3. Begin Phase 1 implementation
4. Create comprehensive testing framework
5. Engage with MCP community for feedback and validation
