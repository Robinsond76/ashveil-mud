"""Tests for client UI structure."""
from pathlib import Path


def test_html_has_output_and_input_sections():
    """Verify index.html has separate output and input sections."""
    html_path = Path("client/index.html")
    content = html_path.read_text()
    
    # Should have output-container div
    assert 'id="output-container"' in content
    # Should have input-container div  
    assert 'id="input-container"' in content
    # Should not have old terminal-wrapper
    assert 'id="terminal-wrapper"' not in content
