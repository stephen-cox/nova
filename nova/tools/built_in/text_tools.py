"""Text processing tools using the new decorator system

These tools demonstrate the new @tool decorator approach.
"""

import re
import textwrap

from nova.models.tools import PermissionLevel, ToolCategory, ToolExample
from nova.tools import tool


@tool(
    description="Convert text to different cases (upper, lower, title, etc.)",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["text", "transform", "case"],
    examples=[
        ToolExample(
            description="Convert to uppercase",
            arguments={"text": "hello world", "case_type": "upper"},
            expected_result="HELLO WORLD",
        ),
        ToolExample(
            description="Convert to title case",
            arguments={"text": "hello world", "case_type": "title"},
            expected_result="Hello World",
        ),
    ],
)
def transform_text_case(text: str, case_type: str = "lower") -> str:
    """
    Transform text to different cases.

    Args:
        text: The text to transform
        case_type: Type of case transformation (upper, lower, title, capitalize)

    Returns:
        The transformed text
    """
    case_type = case_type.lower()

    if case_type == "upper":
        return text.upper()
    elif case_type == "lower":
        return text.lower()
    elif case_type == "title":
        return text.title()
    elif case_type == "capitalize":
        return text.capitalize()
    else:
        return f"Unknown case type: {case_type}. Use: upper, lower, title, capitalize"


@tool(
    description="Count words, characters, and lines in text",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["text", "analysis", "count"],
    examples=[
        ToolExample(
            description="Analyze text statistics",
            arguments={"text": "Hello world!\nThis is a test."},
            expected_result="Words: 6, Characters: 26, Lines: 2",
        )
    ],
)
def analyze_text(text: str, include_spaces: bool = True) -> str:
    """
    Analyze text and return statistics.

    Args:
        text: The text to analyze
        include_spaces: Whether to include spaces in character count

    Returns:
        Text analysis results
    """
    lines = len(text.splitlines())
    words = len(text.split())

    if include_spaces:
        characters = len(text)
    else:
        characters = len(text.replace(" ", ""))

    return f"Words: {words}, Characters: {characters}, Lines: {lines}"


@tool(
    description="Extract and validate email addresses from text",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["text", "email", "extract", "validate"],
    examples=[
        ToolExample(
            description="Extract emails from text",
            arguments={"text": "Contact us at hello@example.com or support@test.org"},
            expected_result="Found 2 emails: hello@example.com, support@test.org",
        )
    ],
)
def extract_emails(text: str, validate: bool = True) -> str:
    """
    Extract email addresses from text.

    Args:
        text: Text to search for email addresses
        validate: Whether to validate email format

    Returns:
        List of found email addresses
    """
    # Basic email regex pattern
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    emails = re.findall(email_pattern, text)

    if validate:
        # More strict validation
        valid_emails = []
        for email in emails:
            if re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$", email):
                valid_emails.append(email)
        emails = valid_emails

    if not emails:
        return "No email addresses found"

    return f"Found {len(emails)} email{'s' if len(emails) != 1 else ''}: {', '.join(emails)}"


@tool(
    description="Format and wrap text with various options",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["text", "format", "wrap"],
    examples=[
        ToolExample(
            description="Wrap text to 40 characters",
            arguments={
                "text": "This is a very long line that needs to be wrapped",
                "width": 40,
            },
            expected_result="Wrapped text with line breaks at 40 characters",
        )
    ],
)
def format_text(
    text: str, width: int = 80, indent: str = "", bullet_point: str | None = None
) -> str:
    """
    Format and wrap text with various options.

    Args:
        text: Text to format
        width: Maximum line width for wrapping
        indent: String to indent each line with
        bullet_point: Add bullet points to each paragraph

    Returns:
        Formatted text
    """
    # Split into paragraphs
    paragraphs = text.split("\n\n")
    formatted_paragraphs = []

    for paragraph in paragraphs:
        # Remove extra whitespace
        paragraph = " ".join(paragraph.split())

        if not paragraph:
            continue

        # Wrap the paragraph
        wrapped = textwrap.fill(
            paragraph, width=width, initial_indent=indent, subsequent_indent=indent
        )

        # Add bullet point if requested
        if bullet_point:
            lines = wrapped.split("\n")
            lines[0] = bullet_point + " " + lines[0][len(indent) :]
            wrapped = "\n".join(lines)

        formatted_paragraphs.append(wrapped)

    return "\n\n".join(formatted_paragraphs)


@tool(
    description="Remove or replace specific patterns in text",
    permission_level=PermissionLevel.SAFE,
    category=ToolCategory.GENERAL,
    tags=["text", "clean", "remove", "replace"],
    examples=[
        ToolExample(
            description="Remove extra whitespace",
            arguments={
                "text": "Hello    world   with   spaces",
                "pattern": "extra_whitespace",
            },
            expected_result="Hello world with spaces",
        )
    ],
)
def clean_text(
    text: str, pattern: str = "extra_whitespace", replacement: str = " "
) -> str:
    """
    Clean text by removing or replacing patterns.

    Args:
        text: Text to clean
        pattern: Pattern to clean (extra_whitespace, numbers, punctuation, or custom regex)
        replacement: What to replace the pattern with

    Returns:
        Cleaned text
    """
    if pattern == "extra_whitespace":
        # Replace multiple spaces with single space
        return re.sub(r"\s+", replacement, text.strip())
    elif pattern == "numbers":
        # Remove all numbers
        return re.sub(r"\d+", replacement, text)
    elif pattern == "punctuation":
        # Remove punctuation
        return re.sub(r"[^\w\s]", replacement, text)
    elif pattern == "emails":
        # Remove email addresses
        return re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", replacement, text
        )
    else:
        # Treat as custom regex pattern
        try:
            return re.sub(pattern, replacement, text)
        except re.error as e:
            return f"Invalid regex pattern: {e}"
