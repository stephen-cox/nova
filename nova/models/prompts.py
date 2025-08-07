"""Prompt data models and schemas"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    """Supported variable types"""

    TEXT = "text"
    STRING = "string"
    LIST = "list"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class PromptVariable(BaseModel):
    """Prompt template variable definition"""

    name: str = Field(description="Variable name")
    type: VariableType = Field(default=VariableType.TEXT, description="Variable type")
    required: bool = Field(default=True, description="Whether variable is required")
    default: Any = Field(default=None, description="Default value if not provided")
    description: str = Field(default="", description="Variable description")


class PromptCategory(str, Enum):
    """Built-in prompt categories"""

    WRITING = "writing"
    DEVELOPMENT = "development"
    ANALYSIS = "analysis"
    BUSINESS = "business"
    EDUCATION = "education"
    COMMUNICATION = "communication"
    GENERAL = "general"


class PromptTemplate(BaseModel):
    """Prompt template definition"""

    name: str = Field(description="Unique prompt identifier")
    title: str = Field(description="Human-readable title")
    description: str = Field(description="Prompt description")
    category: PromptCategory = Field(
        default=PromptCategory.GENERAL, description="Prompt category"
    )
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    variables: list[PromptVariable] = Field(
        default_factory=list, description="Template variables"
    )
    template: str = Field(description="Prompt template content")
    version: str = Field(default="1.0", description="Template version")
    author: str = Field(default="Nova", description="Template author")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    def get_required_variables(self) -> list[PromptVariable]:
        """Get list of required variables"""
        return [var for var in self.variables if var.required]

    def get_optional_variables(self) -> list[PromptVariable]:
        """Get list of optional variables"""
        return [var for var in self.variables if not var.required]

    def has_variable(self, name: str) -> bool:
        """Check if template has a specific variable"""
        return any(var.name == name for var in self.variables)


class ValidationResult(BaseModel):
    """Result of prompt validation"""

    is_valid: bool = Field(description="Whether validation passed")
    message: str = Field(default="", description="Validation message")
    errors: list[str] = Field(default_factory=list, description="Validation errors")


class PromptLibraryEntry(BaseModel):
    """Entry in the prompt library index"""

    name: str = Field(description="Prompt name")
    title: str = Field(description="Display title")
    category: PromptCategory = Field(description="Prompt category")
    tags: list[str] = Field(default_factory=list, description="Tags")
    file_path: Path = Field(description="Path to template file")
    is_builtin: bool = Field(
        default=True, description="Whether this is a built-in prompt"
    )
    usage_count: int = Field(default=0, description="Usage statistics")
    last_used: datetime | None = Field(default=None, description="Last usage timestamp")
