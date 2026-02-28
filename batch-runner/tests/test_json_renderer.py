"""Tests for core/json_renderer.py"""

import json
import pytest
from unittest.mock import Mock, MagicMock

from core.config import DEFAULT_TOKENS
from core.json_renderer import JsonRenderer


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client"""
    client = Mock()
    return client


@pytest.fixture
def json_renderer(mock_llm_client):
    """Create JsonRenderer with mock client"""
    return JsonRenderer(mock_llm_client)


def test_json_renderer_initialization(json_renderer):
    """Test JsonRenderer initializes with llm_client"""
    assert json_renderer.llm_client is not None
    assert json_renderer.max_completion_tokens == DEFAULT_TOKENS["json_render"]


def test_json_renderer_token_override(mock_llm_client):
    """Custom max_completion_tokens should override default"""
    renderer = JsonRenderer(mock_llm_client, max_completion_tokens=5555)
    assert renderer.max_completion_tokens == 5555


def test_extract_json_from_code_block(json_renderer):
    """Test JSON extraction from ```json blocks"""
    text = """Here's the JSON:
```json
{"deliverable_text": "test", "deliverables": []}
```
"""
    result = json_renderer._extract_json(text)
    assert result["deliverable_text"] == "test"
    assert result["deliverables"] == []


def test_extract_json_plain(json_renderer):
    """Test JSON extraction from plain text"""
    text = '{"deliverable_text": "plain test", "deliverables": []}'
    result = json_renderer._extract_json(text)
    assert result["deliverable_text"] == "plain test"


def test_render_text_file(json_renderer):
    """Test rendering text files (md, html)"""
    content = {"text": "# Hello World\n\nThis is markdown."}
    result = json_renderer._render_text(content, "test.md")
    assert result == b"# Hello World\n\nThis is markdown."


def test_render_json_file(json_renderer):
    """Test rendering JSON files"""
    content = {"key": "value", "number": 42}
    result = json_renderer._render_json(content, "test.json")
    parsed = json.loads(result.decode("utf-8"))
    assert parsed["key"] == "value"
    assert parsed["number"] == 42


def test_render_docx(json_renderer):
    """Test rendering DOCX files"""
    content = {
        "title": "Test Document",
        "sections": [
            {"heading": "Section 1", "body": "Content here"}
        ]
    }
    result = json_renderer._render_docx(content, "test.docx")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_render_xlsx(json_renderer):
    """Test rendering XLSX files"""
    content = {
        "sheets": [
            {
                "name": "Sheet1",
                "headers": ["Name", "Age"],
                "rows": [["Alice", 30], ["Bob", 25]]
            }
        ]
    }
    result = json_renderer._render_xlsx(content, "test.xlsx")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_render_pdf(json_renderer):
    """Test rendering PDF files"""
    content = {
        "title": "Test PDF",
        "sections": [
            {"heading": "Introduction", "body": "This is a test."}
        ]
    }
    result = json_renderer._render_pdf(content, "test.pdf")
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result.startswith(b"%PDF")  # PDF magic number


def test_render_pptx(json_renderer):
    """Test rendering PPTX files"""
    content = {
        "slides": [
            {"title": "Slide 1", "body": "Content"}
        ]
    }
    result = json_renderer._render_pptx(content, "test.pptx")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_render_png_chart(json_renderer):
    """Test rendering PNG chart"""
    content = {
        "chart_type": "bar",
        "title": "Test Chart",
        "labels": ["A", "B", "C"],
        "values": [10, 20, 15]
    }
    result = json_renderer._render_png(content, "test.png")
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result.startswith(b"\x89PNG")  # PNG magic number


def test_render_png_diagram(json_renderer):
    """Test rendering PNG diagram"""
    content = {
        "width": 400,
        "height": 300,
        "background": "white",
        "text": "Test Diagram"
    }
    result = json_renderer._render_png(content, "test.png")
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result.startswith(b"\x89PNG")


def test_render_unsupported_type(json_renderer):
    """Test rendering unsupported file type returns None"""
    item = {
        "type": "unsupported",
        "filename": "test.xyz",
        "content": {}
    }
    result = json_renderer._render(item)
    assert result is None


def test_render_missing_fields(json_renderer):
    """Test rendering with missing fields returns None"""
    item = {"type": "docx"}  # Missing filename and content
    result = json_renderer._render(item)
    assert result is None


def test_run_with_mock_response(mock_llm_client, json_renderer):
    """Test full run with mocked LLM response"""
    # Mock LLM response
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="""```json
{
  "deliverable_text": "Task completed",
  "deliverables": [
    {
      "type": "md",
      "filename": "output.md",
      "content": {"text": "# Result"}
    }
  ]
}
```"""))
    ]

    # Mock complete function
    def mock_complete(*args, **kwargs):
        return (mock_response, 100)

    # Patch complete in json_renderer module
    import core.json_renderer
    original_complete = core.json_renderer.complete
    core.json_renderer.complete = mock_complete

    try:
        result = json_renderer.run(task_prompt="Test task", model="gpt-4")

        assert result["success"] is True
        assert result["text"] == "Task completed"
        assert len(result["files"]) == 1
        assert result["files"][0]["filename"] == "output.md"
        assert result["files"][0]["content"] == b"# Result"

    finally:
        # Restore original complete
        core.json_renderer.complete = original_complete


def test_run_with_invalid_json(mock_llm_client, json_renderer):
    """Test run handles invalid JSON gracefully"""
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="This is not valid JSON"))
    ]

    def mock_complete(*args, **kwargs):
        return (mock_response, 100)

    import core.json_renderer
    original_complete = core.json_renderer.complete
    core.json_renderer.complete = mock_complete

    try:
        result = json_renderer.run(task_prompt="Test task", model="gpt-4")

        assert result["success"] is False
        assert "JSON parse error" in result["error"]
        assert result["files"] == []

    finally:
        core.json_renderer.complete = original_complete
