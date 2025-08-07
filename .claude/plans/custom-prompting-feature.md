# Custom Prompting Feature Implementation Plan

## Overview
Add comprehensive custom prompting functionality to Nova AI Assistant, enabling configurable system prompts and a rich library of user-accessible prompts for various tasks and workflows.

## Architecture Design

### 1. Prompt Management System
- **Location**: `nova/core/prompts.py`
- **Purpose**: Core service for managing, storing, and applying custom prompts
- **Key Components**:
  - `PromptManager`: Main orchestrator for prompt operations
  - `PromptTemplate`: Template engine with variable substitution
  - `PromptLibrary`: Built-in and user-defined prompt collection
  - `PromptValidator`: Validation and safety checks

### 2. Configuration Extension
- **Location**: `nova/models/config.py`
- **New Models**:
  - `PromptConfig`: Prompt-specific configuration
  - `SystemPromptConfig`: System prompt settings per profile
  - Integration with existing `NovaConfig` and `AIProfile`
- **Configuration Options**:
  - Custom system prompts per AI profile
  - Default prompt library location
  - Prompt validation settings
  - Variable substitution rules

### 3. Data Models
- **Location**: `nova/models/prompts.py`
- **Key Models**:
  - `PromptTemplate`: Template definition with metadata
  - `PromptVariable`: Variable definitions and validation
  - `PromptCategory`: Organizational structure
  - `PromptLibrary`: Collection management

## Core Features

### 1. System Prompt Configuration

#### Per-Profile System Prompts
```yaml
# Example configuration
profiles:
  coding-assistant:
    name: "Coding Assistant"
    provider: "anthropic"
    model_name: "claude-3-5-sonnet-20241022"
    system_prompt: |
      You are an expert software developer and code reviewer.
      Focus on writing clean, maintainable, and well-documented code.
      Always explain your reasoning and suggest best practices.

  creative-writer:
    name: "Creative Writer"
    provider: "openai"
    model_name: "gpt-4"
    system_prompt: |
      You are a creative writing assistant with expertise in storytelling,
      character development, and narrative structure. Help users craft
      compelling stories and improve their writing style.
```

#### Dynamic System Prompt Variables
```yaml
system_prompt: |
  You are Nova, an AI assistant created by {user_name}.
  Current date: {current_date}
  User preferences: {user_preferences}
  Previous context: {conversation_summary}
```

### 2. User Prompt Library

#### Built-in Prompt Categories
- **Writing & Communication**
  - Email drafting
  - Technical documentation
  - Creative writing
  - Proofreading and editing

- **Analysis & Research**
  - Data analysis
  - Literature review
  - Competitive analysis
  - SWOT analysis

- **Development & Engineering**
  - Code review
  - Architecture design
  - Debugging assistance
  - Documentation generation

- **Business & Strategy**
  - Meeting summarization
  - Project planning
  - Risk assessment
  - Decision frameworks

- **Education & Learning**
  - Concept explanation
  - Quiz generation
  - Study guides
  - Skill assessment

#### Prompt Template Structure
```yaml
# Example prompt template
name: "code-review"
title: "Code Review Assistant"
description: "Comprehensive code review with security and performance focus"
category: "development"
version: "1.2"
author: "Nova Team"
tags: ["code", "review", "security", "performance"]
variables:
  - name: "code"
    type: "text"
    required: true
    description: "Code to review"
  - name: "language"
    type: "string"
    required: false
    default: "auto-detect"
    description: "Programming language"
  - name: "focus_areas"
    type: "list"
    required: false
    default: ["security", "performance", "maintainability"]
    description: "Areas to focus the review on"

template: |
  Please conduct a thorough code review of the following {language} code:

  ```{language}
  {code}
  ```

  Focus areas: {focus_areas}

  Provide feedback on:
  1. Code quality and best practices
  2. Security vulnerabilities
  3. Performance optimizations
  4. Maintainability improvements
  5. Documentation suggestions

  Format your response with specific line references and actionable recommendations.
```

### 3. Chat Integration

#### Prompt Commands
```bash
# List available prompts
/prompts list

# Search prompts by category or tag
/prompts search "code review"
/prompts category development

# Use a prompt
/prompt code-review language=python focus_areas=security,performance
[paste code here]

# Save current conversation as a prompt template
/prompt save "my-analysis-template"

# Show prompt details
/prompt show code-review

# Edit/customize a prompt for current session
/prompt edit code-review
```

#### Interactive Prompt Builder
```bash
# Start interactive prompt creation
/prompt create

# Guided prompts for common tasks
/prompt guide email-draft
/prompt guide data-analysis
/prompt guide creative-writing
```

### 4. Template Engine Features

#### Variable Substitution
- **Basic Variables**: `{variable_name}`
- **Default Values**: `{variable_name:default_value}`
- **Conditional Logic**: `{if variable_exists}...{endif}`
- **Loops**: `{for item in list}...{endfor}`
- **Date/Time Functions**: `{current_date}`, `{current_time}`
- **Context Variables**: `{user_name}`, `{conversation_history}`

#### Advanced Template Features
```yaml
# Conditional sections
template: |
  {if code}
  Please review this code:
  ```{language:auto}
  {code}
  ```
  {endif}

  {if requirements}
  Requirements to consider:
  {for req in requirements}
  - {req}
  {endfor}
  {endif}

# Template inheritance
extends: "base-analysis-prompt"
template: |
  {parent}

  Additional instructions:
  - Focus specifically on {analysis_type}
  - Provide {detail_level} level of detail
```

## Implementation Details

### 1. Core Classes

#### PromptManager
```python
class PromptManager:
    """Main prompt management system"""

    def __init__(self, config: PromptConfig):
        self.config = config
        self.library = PromptLibrary(config.library_path)
        self.template_engine = TemplateEngine()

    def get_system_prompt(self, profile: str, context: dict = None) -> str:
        """Get configured system prompt with variable substitution"""

    def apply_prompt(self, template_name: str, variables: dict) -> str:
        """Apply prompt template with variables"""

    def list_prompts(self, category: str = None, tags: list = None) -> list[PromptTemplate]:
        """List available prompts"""

    def search_prompts(self, query: str) -> list[PromptTemplate]:
        """Search prompts by keywords"""

    def validate_prompt(self, template: PromptTemplate) -> ValidationResult:
        """Validate prompt template"""

    def save_prompt(self, template: PromptTemplate, user_library: bool = True) -> bool:
        """Save custom prompt to library"""
```

#### PromptTemplate
```python
class PromptTemplate(BaseModel):
    """Prompt template definition"""

    name: str = Field(description="Unique prompt identifier")
    title: str = Field(description="Human-readable title")
    description: str = Field(description="Prompt description")
    category: str = Field(description="Prompt category")
    tags: list[str] = Field(default_factory=list)
    variables: list[PromptVariable] = Field(default_factory=list)
    template: str = Field(description="Prompt template content")
    version: str = Field(default="1.0")
    author: str = Field(default="User")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def render(self, variables: dict) -> str:
        """Render template with variables"""

    def validate_variables(self, variables: dict) -> ValidationResult:
        """Validate provided variables"""
```

### 2. Storage System

#### File-Based Library Structure
```
~/.nova/prompts/
├── system/                 # Built-in prompts (read-only)
│   ├── writing/
│   │   ├── email-draft.yaml
│   │   ├── technical-doc.yaml
│   │   └── creative-story.yaml
│   ├── development/
│   │   ├── code-review.yaml
│   │   ├── debug-help.yaml
│   │   └── architecture.yaml
│   └── analysis/
│       ├── data-analysis.yaml
│       └── research-summary.yaml
├── user/                   # User custom prompts
│   ├── my-prompts/
│   └── shared/
├── templates/              # Template inheritance
│   ├── base-analysis.yaml
│   └── base-writing.yaml
└── config/
    ├── library.yaml        # Library configuration
    └── categories.yaml     # Category definitions
```

#### Database Option (Future Enhancement)
- SQLite database for better search and indexing
- Version control for prompt templates
- Usage analytics and recommendations
- Sharing and collaboration features

### 3. Configuration Integration

#### Extended Configuration Models
```python
class PromptConfig(BaseModel):
    """Prompt system configuration"""

    enabled: bool = Field(default=True, description="Enable custom prompting")
    library_path: Path = Field(default=Path("~/.nova/prompts"), description="Prompt library location")
    allow_user_prompts: bool = Field(default=True, description="Allow user-defined prompts")
    validate_prompts: bool = Field(default=True, description="Validate prompt templates")
    max_prompt_length: int = Field(default=10000, description="Maximum prompt length")
    enable_template_inheritance: bool = Field(default=True, description="Enable template inheritance")

class AIProfile(BaseModel):
    # ... existing fields
    system_prompt: str | None = Field(default=None, description="Custom system prompt")
    system_prompt_template: str | None = Field(default=None, description="System prompt template name")
    prompt_variables: dict[str, str] = Field(default_factory=dict, description="Default prompt variables")

class NovaConfig(BaseModel):
    # ... existing fields
    prompts: PromptConfig = Field(default_factory=PromptConfig)
```

### 4. Safety and Validation

#### Prompt Validation Rules
- **Content Safety**: Scan for harmful or inappropriate content
- **Length Limits**: Enforce maximum prompt lengths
- **Variable Validation**: Ensure required variables are provided
- **Template Syntax**: Validate template syntax and logic
- **Injection Prevention**: Prevent prompt injection attacks

#### Security Considerations
```python
class PromptValidator:
    """Validates prompt templates for safety and correctness"""

    def validate_content(self, prompt: str) -> ValidationResult:
        """Check for harmful content"""

    def validate_variables(self, variables: dict, template: PromptTemplate) -> ValidationResult:
        """Validate variable inputs"""

    def validate_template_syntax(self, template: str) -> ValidationResult:
        """Check template syntax"""

    def check_injection_attempts(self, user_input: str) -> ValidationResult:
        """Detect potential prompt injection"""
```

## Chat Integration Details

### 1. Enhanced Chat Commands

#### Prompt Management Commands
```python
# Add to ChatManager._handle_command()

elif cmd == "/prompts list":
    # List all available prompts
    prompts = self.prompt_manager.list_prompts()
    self._display_prompt_list(prompts)

elif cmd.startswith("/prompts search "):
    query = cmd[16:].strip()
    results = self.prompt_manager.search_prompts(query)
    self._display_prompt_search_results(results)

elif cmd.startswith("/prompt use "):
    # Interactive prompt application
    template_name = cmd[12:].strip()
    self._apply_prompt_interactively(template_name)

elif cmd.startswith("/prompt save "):
    # Save current conversation context as template
    template_name = cmd[13:].strip()
    self._save_conversation_as_prompt(template_name)
```

#### Interactive Prompt Application
```python
def _apply_prompt_interactively(self, template_name: str):
    """Guide user through prompt application"""

    template = self.prompt_manager.get_template(template_name)
    if not template:
        print_error(f"Prompt template '{template_name}' not found")
        return

    print_info(f"Applying prompt: {template.title}")
    print_info(template.description)

    # Collect variables interactively
    variables = {}
    for var in template.variables:
        if var.required or not var.default:
            value = input(f"{var.description} ({var.name}): ")
            variables[var.name] = value
        elif var.default:
            use_default = input(f"Use default for {var.name} ({var.default})? [Y/n]: ")
            if use_default.lower() not in ['n', 'no']:
                variables[var.name] = var.default

    # Apply template
    rendered_prompt = template.render(variables)
    print_success("Prompt applied successfully!")

    # Add to conversation context
    self.conversation.add_message(MessageRole.SYSTEM, rendered_prompt)
```

### 2. System Prompt Integration

#### Dynamic System Prompt Loading
```python
class ChatSession:
    def __init__(self, config: NovaConfig, conversation_id: str | None = None):
        # ... existing init
        self.prompt_manager = PromptManager(config.prompts) if config.prompts.enabled else None
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt with context"""

        profile = self.config.get_active_profile()
        if not profile or not profile.system_prompt:
            return self._get_default_system_prompt()

        # Use template if specified
        if profile.system_prompt_template and self.prompt_manager:
            template = self.prompt_manager.get_template(profile.system_prompt_template)
            if template:
                context_vars = self._get_system_prompt_context()
                return template.render({**profile.prompt_variables, **context_vars})

        # Use direct system prompt with variable substitution
        context_vars = self._get_system_prompt_context()
        return self._substitute_variables(profile.system_prompt, context_vars)

    def _get_system_prompt_context(self) -> dict:
        """Get context variables for system prompt"""
        return {
            'current_date': datetime.now().strftime('%Y-%m-%d'),
            'current_time': datetime.now().strftime('%H:%M:%S'),
            'conversation_id': self.conversation.id,
            'user_name': os.getenv('USER', 'User'),
            'nova_version': get_nova_version(),
            'active_profile': self.config.active_profile
        }
```

## Implementation Phases

### Phase 1: Basic System Prompts (2-3 weeks)
**Scope**: Core system prompt functionality
- System prompt configuration per AI profile
- Basic variable substitution
- Configuration management
- Simple chat integration

**Features**:
- Custom system prompts in AI profiles
- Basic template variables (`{current_date}`, `{user_name}`)
- Configuration commands
- System prompt validation

**Deliverables**:
- `PromptConfig` model
- Basic `PromptManager` class
- System prompt integration in `ChatSession`
- Configuration commands

### Phase 2: User Prompt Library (3-4 weeks)
**Scope**: Full prompt template system
- Prompt template engine
- Built-in prompt library
- Chat command interface
- File-based storage

**Features**:
- Complete template engine with variables and logic
- Built-in prompt library (50+ templates)
- Full chat command interface (`/prompt`, `/prompts`)
- User custom prompt creation and storage
- Prompt search and categorization

**Deliverables**:
- `PromptTemplate` and related models
- Template rendering engine
- Built-in prompt library
- Chat command handlers
- File-based storage system

### Phase 3: Advanced Features (2-3 weeks)
**Scope**: Enhanced functionality and safety
- Advanced template features
- Prompt validation and safety
- Import/export capabilities
- Usage analytics

**Features**:
- Template inheritance and composition
- Advanced variable handling and validation
- Prompt safety and injection prevention
- Import/export functionality
- Usage tracking and recommendations
- Prompt sharing capabilities

**Deliverables**:
- Advanced template engine features
- Comprehensive validation system
- Import/export functionality
- Safety and security measures
- Documentation and examples

## Revised Built-in Prompt Library

### Phase 0.5: Essential Prompts (5 prompts)
- `email`: Professional email drafting
- `code-review`: Basic code review
- `summarize`: Content summarization
- `explain`: Concept explanation
- `analyze`: General analysis framework

### Phase 1: Core Library (10 prompts)
- Previous 5 plus:
- `debug-help`: Debugging assistance
- `technical-doc`: Technical documentation
- `meeting-notes`: Meeting summarization
- `creative-writing`: Creative writing assistance
- `data-analysis`: Data interpretation

### Phase 2: Complete Library (30+ prompts)

#### Writing & Communication (10 prompts)
- `email-professional`: Professional email drafting
- `email-followup`: Follow-up email templates
- `technical-documentation`: Technical doc generation
- `blog-post`: Blog post structure and content
- `social-media`: Social media content creation
- `presentation-outline`: Presentation structure
- `meeting-agenda`: Meeting agenda creation
- `meeting-minutes`: Meeting summary and action items
- `proofreading`: Text editing and improvement
- `translation`: Language translation assistance
- `creative-story`: Creative writing prompts
- `poetry`: Poetry creation assistance
- `screenplay`: Screenplay formatting and structure
- `resume`: Resume writing and optimization
- `cover-letter`: Cover letter customization

### Development & Engineering (12 prompts)
- `code-review`: Comprehensive code review
- `debug-assistance`: Debugging help and suggestions
- `architecture-design`: System architecture planning
- `api-documentation`: API documentation generation
- `test-generation`: Unit test creation
- `performance-optimization`: Performance analysis
- `security-review`: Security vulnerability assessment
- `database-design`: Database schema design
- `deployment-checklist`: Deployment planning
- `git-commit-message`: Commit message formatting
- `readme-generation`: README file creation
- `code-explanation`: Code explanation and documentation

### Analysis & Research (10 prompts)
- `data-analysis`: Data interpretation and insights
- `literature-review`: Academic literature analysis
- `competitive-analysis`: Market and competitor research
- `swot-analysis`: SWOT analysis framework
- `root-cause-analysis`: Problem diagnosis
- `trend-analysis`: Trend identification and forecasting
- `risk-assessment`: Risk evaluation framework
- `user-research`: User research planning and analysis
- `market-research`: Market analysis and insights
- `financial-analysis`: Financial data interpretation

### Business & Strategy (8 prompts)
- `project-planning`: Project planning and roadmaps
- `stakeholder-analysis`: Stakeholder identification
- `decision-framework`: Decision-making assistance
- `business-plan`: Business plan development
- `marketing-strategy`: Marketing planning
- `product-roadmap`: Product development planning
- `budget-planning`: Budget creation and analysis
- `process-improvement`: Process optimization

### Education & Learning (10 prompts)
- `concept-explanation`: Complex concept breakdown
- `quiz-generation`: Quiz and assessment creation
- `study-guide`: Study material organization
- `lesson-plan`: Educational content planning
- `skill-assessment`: Skill evaluation framework
- `learning-path`: Personalized learning recommendations
- `exam-preparation`: Exam study strategies
- `research-methodology`: Research approach planning
- `citation-formatting`: Academic citation assistance
- `thesis-outline`: Academic thesis structure

## Quality Assurance

### Testing Strategy
- **Unit Tests**: Template rendering, variable substitution
- **Integration Tests**: End-to-end prompt workflows
- **Validation Tests**: Prompt safety and security
- **Performance Tests**: Template rendering speed
- **User Acceptance Tests**: Real-world prompt usage

### Documentation Requirements
- **User Guide**: How to use prompts effectively
- **Template Creation Guide**: Building custom prompts
- **API Documentation**: Developer integration
- **Best Practices**: Prompt design recommendations
- **Troubleshooting**: Common issues and solutions

## Success Criteria

### Technical Metrics
- Template rendering time < 100ms
- Prompt validation accuracy > 95%
- System uptime > 99.9%
- Storage efficiency (templates under 1KB average)

### User Experience
- Easy prompt discovery and application
- Intuitive template creation process
- Consistent and reliable results
- Seamless chat integration

### Adoption Metrics
- 80%+ of users utilize custom prompts
- 50+ built-in prompts actively used
- 100+ user-created templates in community
- High user satisfaction scores (4.5+ stars)

---

**Status**: Planning Phase
**Priority**: High
**Estimated Effort**: 7-10 weeks total
**Dependencies**: Core chat system stable
**Next Steps**:
1. Review and approve plan
2. Design prompt template format
3. Create initial built-in prompt library
4. Begin Phase 1 implementation
5. User testing and feedback collection
