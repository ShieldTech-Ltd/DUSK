from unittest.mock import patch

import pytest

from dusk import recorder
from dusk.agent import _demo_score, _parse_gemini, research_company
from dusk.models import DuskDecision


@pytest.fixture(autouse=True)
def _reset():
    recorder.clear()
    yield
    recorder.clear()


def test_research_returns_decision():
    gemini_return = {"score": 82, "reasoning": "Strong", "confidence": 0.91, "risk_flags": []}
    tavily_return = [{"title": "Anthropic", "content": "AI safety", "url": ""}]
    with patch("dusk.agent._tavily_search", return_value=tavily_return), \
            patch("dusk.agent._gemini_score", return_value=gemini_return):
        d = research_company("Anthropic")
    assert isinstance(d, DuskDecision)
    assert d.subject == "Anthropic"
    assert d.score == 82
    assert d.confidence == 0.91


def test_research_records_to_store():
    with patch("dusk.agent._tavily_search") as mock_t, patch("dusk.agent._gemini_score") as mock_g:
        mock_t.return_value = []
        mock_g.return_value = {"score": 60, "reasoning": "Ok", "confidence": 0.7, "risk_flags": []}
        research_company("TestCorp")
    assert len(recorder.all_decisions()) == 1


def test_research_uses_demo_fallback_without_keys():
    d = research_company("Anthropic")
    assert d.subject == "Anthropic"
    assert d.score > 0


def test_parse_gemini_valid_json():
    json_str = '{"score": 75, "reasoning": "Good", "confidence": 0.8, "risk_flags": []}'
    result = _parse_gemini(json_str)
    assert result["score"] == 75
    assert result["confidence"] == 0.8


def test_parse_gemini_strips_markdown():
    text = '```json\n{"score": 60, "reasoning": "Ok", "confidence": 0.7, "risk_flags": []}\n```'
    result = _parse_gemini(text)
    assert result["score"] == 60


def test_parse_gemini_bad_json_returns_error():
    result = _parse_gemini("not json at all")
    assert result["score"] == 0
    assert "parse_error" in result["risk_flags"]


def test_demo_score_known_company():
    result = _demo_score("Anthropic")
    assert int(str(result["score"])) > 0
    assert str(result["reasoning"]) != ""


def test_demo_score_unknown_company():
    result = _demo_score("UnknownStartupXYZ")
    assert isinstance(result["score"], int)
