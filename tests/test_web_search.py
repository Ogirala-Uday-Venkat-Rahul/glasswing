"""Test the Serper response formatter without hitting the network.

_format is pure, so we feed it a representative Serper payload and check that the
knowledge panel and organic results both make it into the text the model sees.
"""

from agent.tools.web_search import _format, SNIPPET_CHARS


def test_formats_knowledge_panel_and_organic():
    data = {
        "knowledgeGraph": {
            "title": "SSTech LLC",
            "type": "IT consulting company",
            "attributes": {"Address": "Irving, TX"},
        },
        "organic": [
            {"title": "SSTech LLC Home", "link": "https://sstech-llc.com", "snippet": "Digital solutions."},
            {"title": "SSTech on LinkedIn", "link": "https://linkedin.com/company/sstech-llc", "snippet": "Overview."},
        ],
    }

    out = _format(data)

    assert "SSTech LLC" in out
    assert "Irving, TX" in out          # knowledge panel attribute
    assert "https://sstech-llc.com" in out  # organic link


def test_answer_box_included():
    out = _format({"answerBox": {"answer": "Paris"}})
    assert "Paris" in out


def test_empty_response():
    assert _format({}) == "No results found."


def test_snippet_is_truncated():
    long_snippet = "x" * 1000
    data = {"organic": [{"title": "t", "link": "u", "snippet": long_snippet}]}
    out = _format(data)
    # The cap means the full snippet must not appear whole, but everything up to
    # the cap must survive. Reference the constant so the test tracks the config.
    assert "x" * 1000 not in out
    assert "x" * SNIPPET_CHARS in out
