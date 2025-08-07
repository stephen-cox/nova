"""Core prompt management system"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any

import yaml

from nova.models.config import PromptConfig
from nova.models.prompts import (
    PromptCategory,
    PromptTemplate,
    PromptVariable,
    ValidationResult,
    VariableType,
)

logger = logging.getLogger(__name__)


class PromptTemplateEngine:
    """Simple template engine for prompt rendering"""

    def __init__(self):
        self.context_vars = {
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "user_name": os.getenv("USER", "User"),
        }

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Render template with variables"""
        try:
            # Combine context variables with user variables
            all_vars = {**self.context_vars, **variables}

            # Use Python's Template class for safe substitution
            template_obj = Template(template)

            # Replace template variables (${var} format)
            return template_obj.safe_substitute(all_vars)

        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return template  # Return original template on error


class PromptValidator:
    """Validates prompt templates for safety and correctness"""

    MAX_TEMPLATE_LENGTH = 8192
    MAX_VARIABLES = 20
    DANGEROUS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"eval\(",
        r"exec\(",
        r"__import__",
        r"subprocess",
        r"os\.system",
    ]

    def validate_template(self, template: PromptTemplate) -> ValidationResult:
        """Validate a complete template"""
        errors = []

        # Check template length
        if len(template.template) > self.MAX_TEMPLATE_LENGTH:
            errors.append(
                f"Template too long: {len(template.template)} > {self.MAX_TEMPLATE_LENGTH}"
            )

        # Check variable count
        if len(template.variables) > self.MAX_VARIABLES:
            errors.append(
                f"Too many variables: {len(template.variables)} > {self.MAX_VARIABLES}"
            )

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, template.template, re.IGNORECASE):
                errors.append(f"Potentially dangerous pattern found: {pattern}")

        # Validate variable names
        for var in template.variables:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var.name):
                errors.append(f"Invalid variable name: {var.name}")

        is_valid = len(errors) == 0
        message = (
            "Valid template" if is_valid else f"Found {len(errors)} validation errors"
        )

        return ValidationResult(is_valid=is_valid, message=message, errors=errors)

    def validate_variables(
        self, variables: dict[str, Any], template: PromptTemplate
    ) -> ValidationResult:
        """Validate provided variables against template requirements"""
        errors = []

        # Check required variables
        required_vars = {var.name for var in template.get_required_variables()}
        provided_vars = set(variables.keys())

        missing_vars = required_vars - provided_vars
        if missing_vars:
            errors.append(f"Missing required variables: {', '.join(missing_vars)}")

        # Validate variable types
        for var in template.variables:
            if var.name in variables:
                value = variables[var.name]
                if not self._validate_variable_type(value, var.type):
                    errors.append(f"Invalid type for {var.name}: expected {var.type}")

        is_valid = len(errors) == 0
        message = (
            "Valid variables" if is_valid else f"Found {len(errors)} variable errors"
        )

        return ValidationResult(is_valid=is_valid, message=message, errors=errors)

    def _validate_variable_type(self, value: Any, var_type: VariableType) -> bool:
        """Validate a single variable's type"""
        if var_type == VariableType.STRING:
            return isinstance(value, str)
        elif var_type == VariableType.TEXT:
            return isinstance(value, str)
        elif var_type == VariableType.INTEGER:
            return isinstance(value, int)
        elif var_type == VariableType.BOOLEAN:
            return isinstance(value, bool)
        elif var_type == VariableType.LIST:
            return isinstance(value, list)
        return True  # Unknown type, allow it


class PromptManager:
    """Main prompt management system"""

    def __init__(self, config: PromptConfig):
        self.config = config
        self.template_engine = PromptTemplateEngine()
        self.validator = PromptValidator()
        self.library_path = Path(config.library_path).expanduser()
        self.builtin_templates: dict[str, PromptTemplate] = {}
        self.user_templates: dict[str, PromptTemplate] = {}

        # Initialize directories and load templates
        self._ensure_directories()
        self._load_builtin_templates()
        self._load_user_templates()

    def _ensure_directories(self):
        """Create necessary directories"""
        self.library_path.mkdir(parents=True, exist_ok=True)
        (self.library_path / "user").mkdir(exist_ok=True)
        (self.library_path / "user" / "custom").mkdir(exist_ok=True)
        (self.library_path / "cache").mkdir(exist_ok=True)
        (self.library_path / "config").mkdir(exist_ok=True)

    def _load_builtin_templates(self):
        """Load built-in prompt templates from YAML files"""
        self.builtin_templates = {}

        # Get the project root directory (where prompts/ is located)
        project_root = Path(__file__).parent.parent.parent
        builtin_prompts_dir = project_root / "prompts"

        if not builtin_prompts_dir.exists():
            logger.warning(
                f"Built-in prompts directory not found: {builtin_prompts_dir}"
            )
            return

        # Load all YAML files in the prompts directory
        for yaml_file in builtin_prompts_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)

                # Convert string category to PromptCategory enum
                if "category" in data:
                    category_str = data["category"].upper()
                    data["category"] = PromptCategory[category_str]

                # Convert variable dictionaries to PromptVariable objects
                if "variables" in data:
                    variables = []
                    for var_data in data["variables"]:
                        # Convert string type to VariableType enum if present
                        if "type" in var_data:
                            type_str = var_data["type"].upper()
                            var_data["type"] = VariableType[type_str]
                        variables.append(PromptVariable(**var_data))
                    data["variables"] = variables

                template = PromptTemplate(**data)
                self.builtin_templates[template.name] = template
                logger.debug(f"Loaded built-in template: {template.name}")

            except Exception as e:
                logger.warning(f"Failed to load built-in template {yaml_file}: {e}")

    def _load_user_templates(self):
        """Load user-defined prompt templates"""
        user_dir = self.library_path / "user" / "custom"
        if not user_dir.exists():
            return

        for yaml_file in user_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                    template = PromptTemplate(**data)
                    self.user_templates[template.name] = template
                    logger.debug(f"Loaded user template: {template.name}")
            except Exception as e:
                logger.warning(f"Failed to load user template {yaml_file}: {e}")

    def get_template(self, name: str) -> PromptTemplate | None:
        """Get a template by name"""
        # Check user templates first, then built-in
        if name in self.user_templates:
            return self.user_templates[name]
        return self.builtin_templates.get(name)

    def list_templates(
        self, category: PromptCategory | None = None
    ) -> list[PromptTemplate]:
        """List all available templates"""
        all_templates = list(self.builtin_templates.values()) + list(
            self.user_templates.values()
        )

        if category:
            return [t for t in all_templates if t.category == category]
        return all_templates

    def search_templates(self, query: str) -> list[PromptTemplate]:
        """Search templates by name, title, description, or tags"""
        query_lower = query.lower()
        results = []

        for template in self.list_templates():
            # Search in name, title, description, and tags
            searchable_text = f"{template.name} {template.title} {template.description} {' '.join(template.tags)}"
            if query_lower in searchable_text.lower():
                results.append(template)

        return results

    def render_template(self, name: str, variables: dict[str, Any]) -> str | None:
        """Render a template with provided variables"""
        template = self.get_template(name)
        if not template:
            return None

        # Validate variables if validation is enabled
        if self.config.validate_prompts:
            validation = self.validator.validate_variables(variables, template)
            if not validation.is_valid:
                logger.error(f"Variable validation failed: {validation.message}")
                return None

        # Fill in default values for missing optional variables
        final_variables = {}
        for var in template.variables:
            if var.name in variables:
                final_variables[var.name] = variables[var.name]
            elif not var.required and var.default is not None:
                final_variables[var.name] = var.default

        return self.template_engine.render(template.template, final_variables)

    def save_template(
        self, template: PromptTemplate, user_defined: bool = True
    ) -> bool:
        """Save a template to storage"""
        if not self.config.allow_user_prompts and user_defined:
            logger.warning("User-defined prompts are disabled")
            return False

        # Validate template
        if self.config.validate_prompts:
            validation = self.validator.validate_template(template)
            if not validation.is_valid:
                logger.error(f"Template validation failed: {validation.message}")
                return False

        try:
            if user_defined:
                # Save to user directory
                file_path = (
                    self.library_path / "user" / "custom" / f"{template.name}.yaml"
                )
                with open(file_path, "w") as f:
                    yaml.dump(template.model_dump(), f, default_flow_style=False)
                self.user_templates[template.name] = template
            else:
                # Add to built-in templates (in memory only)
                self.builtin_templates[template.name] = template

            logger.info(f"Saved template: {template.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save template {template.name}: {e}")
            return False

    def delete_template(self, name: str) -> bool:
        """Delete a user-defined template"""
        if name in self.user_templates:
            try:
                file_path = self.library_path / "user" / "custom" / f"{name}.yaml"
                if file_path.exists():
                    file_path.unlink()
                del self.user_templates[name]
                logger.info(f"Deleted template: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete template {name}: {e}")
                return False
        return False

    def get_system_prompt(
        self, profile_prompt: str | None, context: dict[str, Any] | None = None
    ) -> str:
        """Get system prompt, either direct or from template"""
        if not profile_prompt:
            return ""

        # Check if it's a template reference
        template = self.get_template(profile_prompt)
        if template:
            # It's a template reference
            variables = context or {}
            return self.render_template(profile_prompt, variables) or ""
        else:
            # It's a direct system prompt, apply basic variable substitution
            if context:
                return self.template_engine.render(profile_prompt, context)
            return profile_prompt
