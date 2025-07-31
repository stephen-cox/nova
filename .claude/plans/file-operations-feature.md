# File Operations Feature Implementation Plan

## Overview
Add comprehensive file operations capabilities to Nova AI Assistant, enabling it to read, write, create, modify, and manage files and directories through both AI function calling and direct user commands.

## Architecture Design

### 1. File Operations Core System
- **Location**: `nova/core/files/`
- **Purpose**: Core file operations with safety, permissions, and integration
- **Key Components**:
  - `FileManager`: Main orchestrator for file operations
  - `FileOperations`: Low-level file system operations
  - `SecurityManager`: Permission validation and safety checks
  - `ProjectManager`: Project-aware file operations
  - `GitIntegration`: Version control integration

### 2. Supported Operations

#### Basic File Operations
- **Read**: Read file contents with encoding detection
- **Write**: Create/overwrite files with backup option
- **Append**: Add content to existing files
- **Delete**: Remove files with confirmation and trash option
- **Copy**: Copy files and directories
- **Move**: Move/rename files and directories
- **Create**: Create new files from templates

#### Directory Operations
- **List**: List directory contents with filtering
- **Create**: Create directories recursively
- **Remove**: Remove directories with safety checks
- **Tree**: Display directory structure
- **Find**: Search for files and directories

#### Advanced Operations
- **Edit**: In-place file editing with diff preview
- **Patch**: Apply patches to files
- **Compare**: Compare files and show differences
- **Backup**: Create backups before modifications
- **Restore**: Restore from backups
- **Watch**: Monitor file changes

## Core Features

### 1. File System Integration

#### File Manager Class
```python
class FileManager:
    """Main file operations manager"""

    def __init__(self, config: FileOperationsConfig):
        self.config = config
        self.security = SecurityManager(config.security)
        self.project = ProjectManager(config.project_detection)
        self.git = GitIntegration() if config.git_integration else None
        self.backup = BackupManager(config.backup)

    async def read_file(self, path: Path, encoding: str = "auto") -> FileContent:
        """Read file with automatic encoding detection"""

    async def write_file(self, path: Path, content: str,
                        create_backup: bool = True) -> FileResult:
        """Write file with optional backup"""

    async def edit_file(self, path: Path, changes: List[FileEdit]) -> FileResult:
        """Apply edits to file with preview"""

    async def create_from_template(self, template: str, path: Path,
                                  variables: Dict[str, str]) -> FileResult:
        """Create file from template"""

    def list_directory(self, path: Path, recursive: bool = False,
                      pattern: str = None) -> List[FileInfo]:
        """List directory contents with filtering"""
```

#### Security Manager
```python
class SecurityManager:
    """Handle file operation security and permissions"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.allowed_paths = set(config.allowed_paths)
        self.blocked_paths = set(config.blocked_paths)
        self.dangerous_extensions = set(config.dangerous_extensions)

    def validate_path(self, path: Path, operation: str) -> ValidationResult:
        """Validate if path operation is allowed"""

    def check_file_safety(self, path: Path, content: str = None) -> SafetyResult:
        """Check if file/content is safe to operate on"""

    def request_permission(self, operation: str, path: Path) -> bool:
        """Request user permission for sensitive operations"""

    def is_project_file(self, path: Path) -> bool:
        """Check if file is part of current project"""
```

### 2. Function Calling Integration

#### AI Function Tools
```python
# Tool definitions for AI models
FILE_OPERATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "encoding": {"type": "string", "description": "File encoding (auto-detected if not specified)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                    "create_backup": {"type": "boolean", "description": "Create backup before writing"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit specific parts of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "line_start": {"type": "integer"},
                                "line_end": {"type": "integer"},
                                "new_content": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["path", "edits"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "recursive": {"type": "boolean", "description": "List recursively"},
                    "pattern": {"type": "string", "description": "Filter pattern (glob)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file from template or content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to create"},
                    "content": {"type": "string", "description": "File content"},
                    "template": {"type": "string", "description": "Template to use"},
                    "variables": {"type": "object", "description": "Template variables"}
                },
                "required": ["path"]
            }
        }
    }
]
```

### 3. Chat Command Integration

#### File Commands
```python
# Add to ChatManager._handle_command()

elif cmd.startswith("/read "):
    # Read file command
    path = cmd[6:].strip()
    await self._read_file_command(path)

elif cmd.startswith("/write "):
    # Write file command
    parts = cmd[7:].strip().split(" ", 1)
    if len(parts) == 2:
        path, content = parts
        await self._write_file_command(path, content)

elif cmd.startswith("/edit "):
    # Interactive file editing
    path = cmd[6:].strip()
    await self._edit_file_command(path)

elif cmd.startswith("/ls ") or cmd.startswith("/list "):
    # List directory
    path = cmd.split(" ", 1)[1].strip() if " " in cmd else "."
    self._list_directory_command(path)

elif cmd.startswith("/mkdir "):
    # Create directory
    path = cmd[7:].strip()
    await self._create_directory_command(path)

elif cmd.startswith("/cp ") or cmd.startswith("/copy "):
    # Copy file/directory
    parts = cmd.split(" ", 2)[1:]
    if len(parts) == 2:
        await self._copy_command(parts[0], parts[1])

elif cmd.startswith("/mv ") or cmd.startswith("/move "):
    # Move/rename file/directory
    parts = cmd.split(" ", 2)[1:]
    if len(parts) == 2:
        await self._move_command(parts[0], parts[1])

elif cmd.startswith("/rm ") or cmd.startswith("/delete "):
    # Delete file/directory
    path = cmd.split(" ", 1)[1].strip()
    await self._delete_command(path)

elif cmd.startswith("/find "):
    # Find files
    query = cmd[6:].strip()
    await self._find_command(query)

elif cmd.startswith("/diff "):
    # Compare files
    parts = cmd.split(" ", 2)[1:]
    if len(parts) == 2:
        await self._diff_command(parts[0], parts[1])

elif cmd == "/pwd":
    # Print working directory
    self._pwd_command()

elif cmd.startswith("/cd "):
    # Change directory
    path = cmd[4:].strip()
    self._cd_command(path)
```

### 4. Project Intelligence

#### Project Detection
```python
class ProjectManager:
    """Detect and manage project contexts"""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.detectors = {
            'python': PythonProjectDetector(),
            'javascript': JSProjectDetector(),
            'rust': RustProjectDetector(),
            'git': GitProjectDetector()
        }

    def detect_project_type(self, path: Path) -> List[ProjectType]:
        """Detect project types in directory"""

    def get_project_root(self, path: Path) -> Optional[Path]:
        """Find project root directory"""

    def get_project_files(self, project_root: Path) -> List[Path]:
        """Get relevant project files"""

    def suggest_file_structure(self, project_type: str) -> Dict[str, str]:
        """Suggest file structure for project type"""

class PythonProjectDetector:
    """Detect Python project structure"""

    def detect(self, path: Path) -> Optional[ProjectInfo]:
        # Look for pyproject.toml, setup.py, requirements.txt
        # Detect virtual environments
        # Identify package structure

    def get_templates(self) -> Dict[str, str]:
        return {
            '__init__.py': '"""Package initialization."""\n',
            'main.py': PYTHON_MAIN_TEMPLATE,
            'test_*.py': PYTHON_TEST_TEMPLATE
        }
```

### 5. File Templates System

#### Template Engine
```python
class FileTemplateEngine:
    """Generate files from templates"""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.templates = self._load_templates()

    def create_from_template(self, template_name: str, output_path: Path,
                           variables: Dict[str, str]) -> str:
        """Create file from template"""

    def list_templates(self, category: str = None) -> List[Template]:
        """List available templates"""

    def register_template(self, template: Template) -> None:
        """Register new template"""

# Built-in templates
TEMPLATES = {
    'python': {
        'module': '''"""${description}

Author: ${author}
Created: ${date}
"""

def main():
    """Main function."""
    pass

if __name__ == "__main__":
    main()
''',
        'class': '''"""${description}"""

class ${class_name}:
    """${class_description}"""

    def __init__(self):
        """Initialize ${class_name}."""
        pass
''',
        'test': '''"""Tests for ${module_name}."""

import pytest
from ${module_name} import ${class_name}

class Test${class_name}:
    """Test cases for ${class_name}."""

    def test_init(self):
        """Test initialization."""
        instance = ${class_name}()
        assert instance is not None
'''
    },
    'javascript': {
        'module': '''/**
 * ${description}
 *
 * @author ${author}
 * @created ${date}
 */

export default class ${class_name} {
    constructor() {
        // Initialize
    }
}
''',
        'react_component': '''import React from 'react';

interface ${component_name}Props {
    // Define props
}

const ${component_name}: React.FC<${component_name}Props> = () => {
    return (
        <div>
            <h1>${component_name}</h1>
        </div>
    );
};

export default ${component_name};
'''
    }
}
```

### 6. Git Integration

#### Version Control Operations
```python
class GitIntegration:
    """Git version control integration"""

    def __init__(self):
        self.git_available = self._check_git_availability()

    def init_repository(self, path: Path) -> GitResult:
        """Initialize git repository"""

    def add_files(self, files: List[Path]) -> GitResult:
        """Add files to git staging"""

    def commit(self, message: str, files: List[Path] = None) -> GitResult:
        """Commit changes"""

    def get_status(self, path: Path = None) -> GitStatus:
        """Get git status"""

    def get_diff(self, file_path: Path = None) -> GitDiff:
        """Get git diff"""

    def create_branch(self, branch_name: str) -> GitResult:
        """Create new branch"""

    def switch_branch(self, branch_name: str) -> GitResult:
        """Switch to branch"""

    def get_log(self, limit: int = 10) -> List[GitCommit]:
        """Get commit history"""
```

## Configuration Integration

### Extended Configuration Models
```python
class FileOperationsConfig(BaseModel):
    """File operations configuration"""

    enabled: bool = Field(default=True, description="Enable file operations")

    # Security settings
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Backup settings
    backup: BackupConfig = Field(default_factory=BackupConfig)

    # Project detection
    project_detection: bool = Field(default=True, description="Enable project detection")

    # Git integration
    git_integration: bool = Field(default=True, description="Enable git integration")

    # Template settings
    templates: TemplateConfig = Field(default_factory=TemplateConfig)

class SecurityConfig(BaseModel):
    """File operations security configuration"""

    # Path restrictions
    allowed_paths: List[str] = Field(default_factory=lambda: ["~/", "./"])
    blocked_paths: List[str] = Field(default_factory=lambda: ["/etc/", "/usr/", "/bin/"])

    # File restrictions
    dangerous_extensions: List[str] = Field(default_factory=lambda: [".exe", ".bat", ".sh"])
    max_file_size: int = Field(default=10*1024*1024, description="Max file size in bytes")

    # Safety settings
    require_confirmation: List[str] = Field(default_factory=lambda: ["delete", "overwrite"])
    backup_before_edit: bool = Field(default=True, description="Backup before editing")

class BackupConfig(BaseModel):
    """Backup configuration"""

    enabled: bool = Field(default=True, description="Enable backups")
    backup_dir: str = Field(default="~/.nova/backups", description="Backup directory")
    max_backups: int = Field(default=10, description="Max backups per file")
    retention_days: int = Field(default=30, description="Backup retention days")

class NovaConfig(BaseModel):
    # ... existing fields
    files: FileOperationsConfig = Field(default_factory=FileOperationsConfig)
```

## Safety and Security Measures

### 1. Path Validation
```python
class PathValidator:
    """Validate file paths for security"""

    def validate_path(self, path: Path, operation: str) -> ValidationResult:
        """Comprehensive path validation"""

        # Check path traversal attacks
        if self._has_path_traversal(path):
            return ValidationResult(False, "Path traversal detected")

        # Check against allowed paths
        if not self._is_allowed_path(path):
            return ValidationResult(False, "Path not in allowed directories")

        # Check against blocked paths
        if self._is_blocked_path(path):
            return ValidationResult(False, "Path is blocked")

        # Check file extension safety
        if operation in ['write', 'create'] and self._is_dangerous_extension(path):
            return ValidationResult(False, "Dangerous file extension")

        return ValidationResult(True, "Path is safe")

    def _has_path_traversal(self, path: Path) -> bool:
        """Check for path traversal attempts"""
        path_str = str(path)
        return ".." in path_str or path_str.startswith("/")
```

### 2. Content Safety
```python
class ContentValidator:
    """Validate file content for safety"""

    def validate_content(self, content: str, file_path: Path) -> ContentValidation:
        """Validate file content"""

        # Check for potentially harmful content
        if self._contains_harmful_patterns(content):
            return ContentValidation(False, "Potentially harmful content detected")

        # Check file size
        if len(content) > self.max_size:
            return ContentValidation(False, "Content exceeds size limit")

        # Validate syntax for code files
        if self._is_code_file(file_path):
            syntax_result = self._validate_syntax(content, file_path)
            if not syntax_result.valid:
                return ContentValidation(False, f"Syntax error: {syntax_result.error}")

        return ContentValidation(True, "Content is safe")
```

### 3. User Confirmation System
```python
class ConfirmationManager:
    """Handle user confirmations for sensitive operations"""

    def request_confirmation(self, operation: str, details: Dict[str, Any]) -> bool:
        """Request user confirmation"""

        if operation == "delete":
            file_path = details["path"]
            print_warning(f"⚠️  Delete file: {file_path}")
            return self._get_user_confirmation("Delete this file?")

        elif operation == "overwrite":
            file_path = details["path"]
            print_warning(f"⚠️  File exists: {file_path}")
            return self._get_user_confirmation("Overwrite existing file?")

        elif operation == "dangerous_extension":
            file_path = details["path"]
            print_warning(f"⚠️  Potentially dangerous file type: {file_path}")
            return self._get_user_confirmation("Create file with this extension?")

        return True

    def _get_user_confirmation(self, message: str) -> bool:
        """Get yes/no confirmation from user"""
        response = input(f"{message} [y/N]: ").strip().lower()
        return response in ['y', 'yes']
```

## Implementation Phases

### Phase 1: Core File Operations (2-3 weeks)
**Scope**: Basic file operations with safety measures
- Basic file read/write operations
- Directory listing and navigation
- Security validation and path checking
- Simple chat command integration

**Features**:
- Read, write, create, delete files
- List directories with filtering
- Path validation and security checks
- Basic backup system
- Function calling integration for AI models

**Deliverables**:
- `FileManager` core implementation
- `SecurityManager` with validation
- Basic chat commands (`/read`, `/write`, `/ls`)
- Function calling tools for AI integration
- Unit tests for core operations

### Phase 2: Advanced Operations (2-3 weeks)
**Scope**: Advanced file operations and project intelligence
- File editing with diff preview
- Project detection and templates
- Advanced directory operations
- Git integration basics

**Features**:
- In-place file editing with change preview
- File templates for common project types
- Project structure detection
- Copy, move, find operations
- Basic git status and operations

**Deliverables**:
- `ProjectManager` with project detection
- `FileTemplateEngine` with built-in templates
- Advanced chat commands (`/edit`, `/find`, `/diff`)
- Git integration for status and basic operations
- Enhanced security measures

### Phase 3: Production Features (2-3 weeks)
**Scope**: Production-ready features and optimizations
- Advanced git integration
- File watching and monitoring
- Backup management and restoration
- Performance optimization

**Features**:
- Full git integration (commit, branch, merge)
- File system monitoring and change detection
- Advanced backup and restoration system
- Performance optimization and caching
- Comprehensive error handling

**Deliverables**:
- `GitIntegration` with full git operations
- File monitoring and change detection
- Advanced backup management
- Performance optimizations
- Complete documentation and examples

## Usage Examples

### AI Function Calling
```bash
# User asks AI to create a file
"Create a Python script called hello.py that prints 'Hello, World!'"
# → AI automatically calls create_file function

# User asks to modify existing file
"Add a docstring to the main function in app.py"
# → AI calls read_file, then edit_file with changes

# User asks to analyze project structure
"What files are in my project and what do they do?"
# → AI calls list_directory and read_file for analysis
```

### Direct Chat Commands
```bash
# Read file contents
/read src/main.py

# Write new file
/write config.json {"debug": true, "port": 8080}

# List directory contents
/ls src/ --pattern="*.py"

# Edit file interactively
/edit README.md

# Create directory structure
/mkdir -p src/utils tests/unit

# Find files
/find "*.py" --contains="TODO"

# Git operations
/git status
/git add .
/git commit "Add new feature"
```

### Template Usage
```bash
# Create from template
/create src/models/user.py --template=python_class --vars="class_name=User,description=User model"

# List available templates
/templates list

# Create custom template
/template create my_template --content="..."
```

## Quality Assurance

### Testing Strategy
- **Unit Tests**: Individual file operations and validation
- **Integration Tests**: End-to-end file workflows
- **Security Tests**: Path traversal, permission validation
- **Performance Tests**: Large file operations, directory scanning
- **Safety Tests**: Backup/restore, error recovery

### Monitoring and Metrics
- **Operation Success Rate**: Track file operation success/failure
- **Security Violations**: Monitor blocked operations
- **Performance Metrics**: File operation latency
- **User Safety**: Backup usage and restoration success

## Security Considerations

### File System Security
- **Sandboxing**: Restrict operations to allowed directories
- **Path Validation**: Prevent directory traversal attacks
- **Permission Checks**: Validate file system permissions
- **Content Scanning**: Check for potentially harmful content

### User Safety
- **Backup System**: Automatic backups before modifications
- **Confirmation Prompts**: User confirmation for destructive operations
- **Undo Capability**: Ability to revert changes
- **Audit Logging**: Log all file operations for review

## Success Criteria

### Technical Metrics
- File operation success rate > 99%
- Security validation accuracy > 99.9%
- Operation latency < 100ms for small files
- Zero data loss incidents

### User Experience
- Intuitive chat command interface
- Clear error messages and guidance
- Seamless AI integration
- Reliable backup and recovery

### Adoption Metrics
- 80%+ of users utilize file operations
- High user satisfaction with safety measures
- Integration with common development workflows
- Positive feedback on productivity improvement

---

**Status**: Planning Phase
**Priority**: Critical
**Estimated Effort**: 6-9 weeks total
**Dependencies**: Core chat system stable, Function calling implemented
**Next Steps**:
1. Review and approve security model
2. Create detailed security specifications
3. Set up development sandbox environment
4. Begin Phase 1 implementation
5. Create comprehensive test suite
6. User testing with restricted permissions
