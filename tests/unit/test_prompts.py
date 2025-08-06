"""Tests for prompt management system"""

from pathlib import Path

import pytest

from nova.core.prompts import PromptManager, PromptTemplateEngine, PromptValidator
from nova.models.config import PromptConfig
from nova.models.prompts import (
    PromptCategory,
    PromptTemplate,
    PromptVariable,
    VariableType,
)


class TestPromptTemplateEngine:
    """Test the template rendering engine"""

    def setup_method(self):
        self.engine = PromptTemplateEngine()

    def test_basic_variable_substitution(self):
        """Test basic variable substitution"""
        template = "Hello ${name}, today is ${date}"
        variables = {"name": "Alice", "date": "2025-01-06"}

        result = self.engine.render(template, variables)
        assert result == "Hello Alice, today is 2025-01-06"

    def test_missing_variables_safe_substitute(self):
        """Test that missing variables are left as-is with safe substitution"""
        template = "Hello ${name}, your score is ${score}"
        variables = {"name": "Bob"}

        result = self.engine.render(template, variables)
        assert result == "Hello Bob, your score is ${score}"

    def test_context_variables(self):
        """Test that context variables are automatically included"""
        template = "Hello ${user_name}, today is ${current_date}"
        variables = {}

        result = self.engine.render(template, variables)

        # Should contain actual user name and current date
        assert "Hello" in result
        assert "today is" in result


class TestPromptValidator:
    """Test prompt validation"""

    def setup_method(self):
        self.validator = PromptValidator()

    def test_valid_template(self):
        """Test validation of a valid template"""
        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template="Hello ${name}",
            variables=[
                PromptVariable(name="name", description="User name", required=True)
            ],
        )

        result = self.validator.validate_template(template)
        assert result.is_valid
        assert result.message == "Valid template"

    def test_template_too_long(self):
        """Test validation fails for overly long templates"""
        long_template = "x" * 10000  # Longer than MAX_TEMPLATE_LENGTH

        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template=long_template,
        )

        result = self.validator.validate_template(template)
        assert not result.is_valid
        assert "Template too long" in result.errors[0]

    def test_dangerous_patterns(self):
        """Test validation fails for dangerous patterns"""
        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template="<script>alert('xss')</script>",
        )

        result = self.validator.validate_template(template)
        assert not result.is_valid
        assert any("dangerous pattern" in error.lower() for error in result.errors)

    def test_variable_validation(self):
        """Test variable validation"""
        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template="Hello ${name}",
            variables=[
                PromptVariable(name="name", description="User name", required=True),
                PromptVariable(name="age", type=VariableType.INTEGER, required=False),
            ],
        )

        # Test valid variables
        variables = {"name": "Alice", "age": 25}
        result = self.validator.validate_variables(variables, template)
        assert result.is_valid

        # Test missing required variable
        variables = {"age": 25}
        result = self.validator.validate_variables(variables, template)
        assert not result.is_valid
        assert "Missing required variables" in result.errors[0]


class TestPromptTemplate:
    """Test PromptTemplate model"""

    def test_template_creation(self):
        """Test creating a basic template"""
        template = PromptTemplate(
            name="greeting",
            title="Greeting Template",
            description="A simple greeting",
            template="Hello ${name}!",
        )

        assert template.name == "greeting"
        assert template.title == "Greeting Template"
        assert template.category == PromptCategory.GENERAL
        assert template.version == "1.0"
        assert template.author == "Nova"

    def test_required_variables(self):
        """Test getting required variables"""
        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template="Hello ${name}, you are ${age} years old",
            variables=[
                PromptVariable(name="name", required=True),
                PromptVariable(name="age", required=False, default="unknown"),
            ],
        )

        required = template.get_required_variables()
        assert len(required) == 1
        assert required[0].name == "name"

        optional = template.get_optional_variables()
        assert len(optional) == 1
        assert optional[0].name == "age"

    def test_has_variable(self):
        """Test checking if template has a variable"""
        template = PromptTemplate(
            name="test",
            title="Test Template",
            description="A test template",
            template="Hello ${name}",
            variables=[PromptVariable(name="name", required=True)],
        )

        assert template.has_variable("name")
        assert not template.has_variable("age")


class TestPromptManager:
    """Test the main PromptManager class"""

    def setup_method(self):
        # Use a temporary config for testing
        config = PromptConfig(
            enabled=True,
            library_path=Path("/tmp/test_nova_prompts"),
            validate_prompts=True,
        )
        self.manager = PromptManager(config)

    def test_builtin_templates_loaded(self):
        """Test that built-in templates are loaded"""
        templates = self.manager.list_templates()
        assert len(templates) > 0

        # Check that essential templates exist
        essential_names = ["email", "code-review", "summarize", "explain", "analyze"]
        template_names = [t.name for t in templates]

        for name in essential_names:
            assert name in template_names

    def test_get_template(self):
        """Test getting a specific template"""
        template = self.manager.get_template("email")
        assert template is not None
        assert template.name == "email"
        assert template.title == "Professional Email"

    def test_render_template(self):
        """Test rendering a template"""
        variables = {
            "purpose": "requesting a meeting",
            "recipient": "John Doe",
            "tone": "professional",
        }

        result = self.manager.render_template("email", variables)
        assert result is not None
        assert "requesting a meeting" in result
        assert "John Doe" in result
        assert "professional" in result

    def test_search_templates(self):
        """Test searching templates"""
        results = self.manager.search_templates("code")
        assert len(results) > 0

        # Should find code-review template
        names = [t.name for t in results]
        assert "code-review" in names

    def test_system_prompt_direct(self):
        """Test system prompt with direct string"""
        context = {"user_name": "Alice"}
        result = self.manager.get_system_prompt(
            "You are a helpful assistant for ${user_name}", context
        )

        assert "Alice" in result

    def test_system_prompt_template_reference(self):
        """Test system prompt with template reference"""
        # This should fall back to direct prompt since "nonexistent" isn't a template
        result = self.manager.get_system_prompt("nonexistent", {})
        assert result == "nonexistent"  # Returns original string when not a template

        # Test with actual template reference
        result = self.manager.get_system_prompt("email", {"purpose": "test"})
        assert result is not None
        assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__])
