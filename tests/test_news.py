"""Test the Serper news parser without hitting the network.

_headlines is pure, so we feed it a representative Serper /news payload and check
that it keeps only the fields the panel renders, caps the count, and drops
malformed items -- mirroring the same split test_web_search uses for _format.
"""

from backend.routes.news import _headlines, MAX_HEADLINES


def test_extracts_headline_fields():
    data = {
        "news": [
            {
                "title": "Rocket reaches orbit",
                "source": "Space News",
                "date": "2 hours ago",
                "link": "https://example.com/rocket",
                "imageUrl": "https://example.com/img.png",  # dropped
            }
        ]
    }

    out = _headlines(data)

    assert out == [
        {
            "title": "Rocket reaches orbit",
            "source": "Space News",
            "date": "2 hours ago",
            "link": "https://example.com/rocket",
        }
    ]


def test_skips_items_without_a_title():
    data = {"news": [{"source": "No Title Co"}, {"title": "Real headline"}]}
    out = _headlines(data)
    assert len(out) == 1
    assert out[0]["title"] == "Real headline"


def test_caps_the_number_of_headlines():
    data = {"news": [{"title": f"Story {i}"} for i in range(MAX_HEADLINES + 5)]}
    out = _headlines(data)
    assert len(out) == MAX_HEADLINES


def test_empty_or_missing_news_key():
    assert _headlines({}) == []
    assert _headlines({"news": []}) == []
