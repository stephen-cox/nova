#!/usr/bin/env python3

"""Test script to verify YAML frontmatter functionality"""

import tempfile
from pathlib import Path

from nova.core.history import HistoryManager
from nova.models.message import Conversation, MessageRole

# Create temporary directory
with tempfile.TemporaryDirectory() as temp_dir:
    history_dir = Path(temp_dir) / "history"
    manager = HistoryManager(history_dir)

    # Create conversation with tags and markdown content
    conversation = Conversation(id="test-yaml", title="YAML Test Chat")
    conversation.add_tag("yaml")
    conversation.add_tag("frontmatter")
    conversation.add_message(MessageRole.USER, "Show me markdown headings")

    assistant_content = """Here's markdown with YAML frontmatter support:

# Heading 1

Some text.

## Heading 2

More text with **bold** and *italic*.

### Code Example

```python
def hello():
    print("Hello World")
```

---

Horizontal rule above."""

    conversation.add_message(MessageRole.ASSISTANT, assistant_content)

    # Save conversation
    saved_path = manager.save_conversation(conversation)

    print("=== SAVED MARKDOWN FILE WITH YAML FRONTMATTER ===")
    with open(saved_path) as f:
        markdown_content = f.read()
        print(markdown_content)

    print("\n=== PARSING BACK ===")

    # Load conversation back
    loaded_conv = manager.load_conversation(saved_path)

    print(f"Conversation ID: {loaded_conv.id}")
    print(f"Title: {loaded_conv.title}")
    print(f"Tags: {list(loaded_conv.tags)}")
    print(f"Number of messages: {len(loaded_conv.messages)}")

    for i, msg in enumerate(loaded_conv.messages):
        print(f"\nMessage {i}: {msg.role}")
        print(f"Content length: {len(msg.content)} chars")
        print(f"Content preview: {msg.content[:100]}...")

    # Verify markdown headings are preserved
    assistant_msg = loaded_conv.messages[1]
    assert "# Heading 1" in assistant_msg.content
    assert "## Heading 2" in assistant_msg.content
    assert "### Code Example" in assistant_msg.content
    assert "```python" in assistant_msg.content
    assert "---" in assistant_msg.content

    print("\n✅ All markdown content preserved!")
    print("✅ YAML frontmatter working correctly!")
