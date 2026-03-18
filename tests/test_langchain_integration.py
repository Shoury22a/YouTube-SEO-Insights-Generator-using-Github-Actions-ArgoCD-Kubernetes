"""
Tests for LangChain integration in src/ai_model.py
Verifies structure, parsing, and chain wiring WITHOUT hitting the real API.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.ai_model import (
    SEOOutput,
    NicheAnalysis,
    TimestampEntry,
    SocialPosts,
    _count_words,
    _validate_timestamps,
    _enforce_tag_limit,
    _enforce_short_titles,
    generate_seo_metadata,
    MAX_TRANSCRIPT_WORDS,
)


# ---------------------------------------------------------------------------
# Sample valid SEOOutput payload (mirrors Pydantic model)
# ---------------------------------------------------------------------------

SAMPLE_SEO_OUTPUT = SEOOutput(
    titles=[
        "How to Master LangChain in 30 Days",
        "LangChain for Beginners: Full Crash Course",
        "Build AI Apps Fast with LangChain",
    ],
    description="LangChain is the leading framework for building LLM-powered applications...",
    timestamps=[
        TimestampEntry(time="0:00", label="Intro"),
        TimestampEntry(time="1:30", label="What is LangChain?"),
        TimestampEntry(time="5:45", label="Building Your First Chain"),
    ],
    tags=["langchain", "ai tutorial", "llm", "python ai", "build ai apps"],
    social_posts=SocialPosts(
        twitter="Just dropped a full LangChain crash course 🔥 Watch now!",
        linkedin="Excited to share my deep dive into LangChain, the framework behind modern AI apps.",
        instagram="LangChain tutorial live now 🚀 Link in bio! #AI #LangChain #Python",
    ),
    thumbnail_ideas=[
        "Bold text 'LangChain in 30 Days' on dark background with chain graphic",
        "Split screen: tangled code vs clean AI output",
        "Developer with surprised expression, 'It's this simple?' text overlay",
    ],
    niche_analysis=NicheAnalysis(
        saturation_score=6,
        competition_level="Medium",
        recommendation="Focus on beginner-friendly content with real project demos.",
    ),
    contrarian_titles=[
        "Why Most LangChain Tutorials Are WRONG",
        "Stop Using LangChain Until You Watch This",
    ],
)


# ---------------------------------------------------------------------------
# Unit tests — Pydantic model validation
# ---------------------------------------------------------------------------

class TestSEOOutputModel:
    def test_valid_model_passes(self):
        assert SAMPLE_SEO_OUTPUT.titles[0] == "How to Master LangChain in 30 Days"
        assert SAMPLE_SEO_OUTPUT.niche_analysis.saturation_score == 6
        assert len(SAMPLE_SEO_OUTPUT.timestamps) == 3

    def test_model_dump_returns_dict(self):
        data = SAMPLE_SEO_OUTPUT.model_dump()
        assert isinstance(data, dict)
        assert "titles" in data
        assert "social_posts" in data
        assert "niche_analysis" in data

    def test_all_required_keys_present(self):
        data = SAMPLE_SEO_OUTPUT.model_dump()
        required_keys = [
            "titles", "description", "timestamps", "tags",
            "social_posts", "thumbnail_ideas", "niche_analysis", "contrarian_titles"
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Unit tests — helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_count_words(self):
        assert _count_words("hello world foo") == 3
        assert _count_words("") == 0

    def test_validate_timestamps_ascending(self):
        ts = [{"time": "0:00", "label": "Intro"}, {"time": "2:30", "label": "Part 2"}]
        result = _validate_timestamps(ts)
        assert len(result) == 2

    def test_validate_timestamps_drops_out_of_order(self):
        ts = [{"time": "5:00", "label": "Late"}, {"time": "1:00", "label": "Early"}]
        result = _validate_timestamps(ts)
        assert len(result) == 1
        assert result[0]["time"] == "5:00"

    def test_enforce_tag_limit_respects_500_chars(self):
        # Create tags that would exceed 500 chars total
        fat_tags = [f"tag_{i}_with_some_extra_padding" for i in range(30)]
        result = _enforce_tag_limit(fat_tags)
        total = len(", ".join(result))
        assert total <= 500

    def test_enforce_short_titles_trims(self):
        long_title = "A" * 60
        result = _enforce_short_titles([long_title])
        assert len(result[0]) <= 45

    def test_enforce_short_titles_keeps_short(self):
        short = "Short Title"
        assert _enforce_short_titles([short]) == [short]


# ---------------------------------------------------------------------------
# Integration test — generate_seo_metadata (with mocked LangChain chain)
# ---------------------------------------------------------------------------

class TestGenerateSEOMetadata:

    @patch("src.ai_model._build_llm_with_fallback")
    def test_returns_all_required_keys(self, mock_llm_builder):
        """
        Mocks the LangChain chain so no real API call is made.
        Verifies generate_seo_metadata() returns a dict with all expected keys.
        """
        # Build a fake chain that returns SAMPLE_SEO_OUTPUT directly
        mock_chain_output = SAMPLE_SEO_OUTPUT
        mock_llm = MagicMock()

        # Chain is: prompt | llm | parser → we mock the whole invoke
        with patch("src.ai_model.ChatPromptTemplate") as mock_prompt_cls, \
             patch("src.ai_model.PydanticOutputParser") as mock_parser_cls:

            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt

            mock_parser = MagicMock()
            mock_parser.get_format_instructions.return_value = "Return JSON matching schema."
            mock_parser_cls.return_value = mock_parser

            # Simulate the chain pipeline returning the sample output
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_chain_output
            mock_prompt.__or__ = MagicMock(return_value=mock_chain)
            # The pipe chain: prompt | llm | parser
            mock_llm_chain = MagicMock()
            mock_llm_chain.__or__ = MagicMock(return_value=mock_chain)
            mock_prompt.__or__.return_value = mock_llm_chain
            mock_llm_builder.return_value = mock_llm

            result = generate_seo_metadata(
                topic="LangChain tutorial for beginners",
                audience="Python developers new to AI",
            )

        assert isinstance(result, dict)
        for key in ["titles", "description", "timestamps", "tags",
                    "social_posts", "thumbnail_ideas", "niche_analysis", "contrarian_titles"]:
            assert key in result, f"Missing key in result: {key}"

    @patch("src.ai_model._summarise_transcript")
    @patch("src.ai_model._build_llm_with_fallback")
    def test_long_transcript_triggers_summarisation(self, mock_llm_builder, mock_summarise):
        """Verifies that transcripts > MAX_TRANSCRIPT_WORDS are summarised before being sent."""
        long_transcript = "word " * (MAX_TRANSCRIPT_WORDS + 100)
        mock_summarise.return_value = "This is a concise summary of the long transcript."

        mock_llm = MagicMock()
        mock_llm_builder.return_value = mock_llm

        with patch("src.ai_model.ChatPromptTemplate") as mock_prompt_cls, \
             patch("src.ai_model.PydanticOutputParser") as mock_parser_cls:

            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt

            mock_parser = MagicMock()
            mock_parser.get_format_instructions.return_value = ""
            mock_parser_cls.return_value = mock_parser

            mock_chain = MagicMock()
            mock_chain.invoke.return_value = SAMPLE_SEO_OUTPUT
            mock_llm_chain = MagicMock()
            mock_llm_chain.__or__ = MagicMock(return_value=mock_chain)
            mock_prompt.__or__ = MagicMock(return_value=mock_llm_chain)

            generate_seo_metadata(
                topic="Some topic",
                audience="Developers",
                transcript=long_transcript,
            )

        # _summarise_transcript should have been called once
        mock_summarise.assert_called_once()

    def test_missing_api_key_raises_api_exception(self, monkeypatch):
        """Verifies APIException is raised when GOOGLE_API_KEY is missing."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from src.exception import APIException
        with pytest.raises(APIException):
            generate_seo_metadata(
                topic="Test topic here",
                audience="Developers",
            )
