"""
YouTube SEO Insights Generator — Streamlit Frontend
Provides a rich UI for generating AI-powered YouTube SEO metadata.
"""

import os
import sys
import streamlit as st
from src.logger import get_logger
from src.extractor import extract_video_metadata
from src.ai_model import generate_seo_metadata, MAX_TRANSCRIPT_CHARS
from src.exception import APIException, ValidationException, SEOAppException

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Page config (MUST be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube SEO Insights Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* Google Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* Dark gradient background */
        .stApp {
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
        }

        /* Header banner */
        .hero-banner {
            background: linear-gradient(90deg, #ff0000 0%, #c0392b 100%);
            border-radius: 14px;
            padding: 24px 32px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(255, 0, 0, 0.3);
        }
        .hero-banner h1 { color: #fff; font-size: 2rem; margin: 0; font-weight: 700; }
        .hero-banner p  { color: rgba(255,255,255,0.85); margin: 6px 0 0; font-size: 1rem; }

        /* Section expander headers */
        .section-title {
            font-size: 1rem;
            font-weight: 600;
            color: #e0e0e0;
            letter-spacing: 0.03em;
        }

        /* Output card style */
        .output-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 12px;
        }

        /* Tag pill */
        .tag-pill {
            display: inline-block;
            background: rgba(255, 0, 0, 0.18);
            border: 1px solid rgba(255, 0, 0, 0.4);
            color: #ff6b6b;
            border-radius: 20px;
            padding: 3px 12px;
            margin: 3px 4px 3px 0;
            font-size: 0.82rem;
            font-weight: 500;
        }

        /* Streamlit widget tweaks */
        .stTextArea textarea { background: rgba(255,255,255,0.05) !important; color: #e0e0e0 !important; }
        .stTextInput input  { background: rgba(255,255,255,0.05) !important; color: #e0e0e0 !important; }
        div[data-testid="stSidebar"] { background: rgba(255,255,255,0.03) !important; }

        /* Generate button */
        .stButton > button {
            background: linear-gradient(90deg, #ff0000, #c0392b);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1rem;
            padding: 10px 32px;
            width: 100%;
            transition: opacity 0.2s;
        }
        .stButton > button:hover { opacity: 0.85; }
        .stButton > button:disabled { opacity: 0.4; cursor: not-allowed; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Hero Banner
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-banner">
        <h1>🎬 YouTube SEO Insights Generator</h1>
        <p>Generate A/B titles, descriptions, timestamps, tags, social posts &amp;
           thumbnail ideas — powered by GPT-4.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Configuration Inputs
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Video Settings")

    content_type = st.radio(
        "Content Type",
        options=["Long-Form Video", "YouTube Short"],
        index=0,
        horizontal=True,
        help="Shorts get tighter titles (≤45 chars) and no timestamps.",
    )

    output_language = st.selectbox(
        "Output Language",
        options=[
            "English", "Hinglish", "Hindi", "Spanish", "French",
            "German", "Japanese", "Korean", "Portuguese", "Arabic",
        ],
        index=0,
        help="The AI will translate all outputs into this language.",
    )

    st.markdown("---")
    st.markdown("## 🔗 Competitor Reference (Optional)")
    competitor_url = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=...",
        help="We'll scrape metadata to give the AI competitive context.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main — Content Inputs
# ─────────────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown("### 📝 Video Details")

    topic = st.text_input(
        "Core Topic ✱",
        placeholder="e.g. How to build a passive income stream with AI tools in 2024",
        help="Be specific. Minimum 2 words required to enable generation.",
        key="topic",
    )
    topic_word_count = len(topic.strip().split()) if topic.strip() else 0
    st.caption(f"{'✅' if topic_word_count >= 2 else '⚠️'} {topic_word_count} word(s) — minimum 2 required")

    audience = st.text_input(
        "Target Audience ✱",
        placeholder="e.g. Beginner entrepreneurs aged 20-35 interested in side hustles",
        key="audience",
    )

with col_right:
    st.markdown("### 📋 Chapter Notes")
    chapter_notes = st.text_area(
        "Rough Chapter Breakdown (for timestamps)",
        placeholder="0:00 Intro\n1:30 What is passive income?\n4:00 AI tool #1 — Notion AI\n...",
        height=158,
        help="Only for long-form. Leave blank to skip timestamp generation.",
        key="chapter_notes",
    )

# ── Transcript / Visual Description ──────────────────────────────────────────
st.markdown("### 🎙️ Transcript or Script")

use_visual_desc = st.checkbox(
    "This is a silent / gameplay / no-speech video — use visual description instead",
    key="use_visual_desc",
)

if use_visual_desc:
    visual_description = st.text_area(
        "Visual Description",
        placeholder=(
            "Describe what happens in the video. e.g.: "
            "'Timelapse of a city skyline from dawn to dusk, "
            "featuring drone shots of busy streets and skyscrapers...'"
        ),
        height=160,
        key="visual_description",
    )
    transcript = ""
else:
    transcript = st.text_area(
        "Transcript / Script (Optional)",
        placeholder=(
            "Paste your full video transcript or script here. "
            "Transcripts over 5,000 words will be summarised automatically. "
            f"Hard limit: {MAX_TRANSCRIPT_CHARS:,} characters."
        ),
        height=200,
        max_chars=MAX_TRANSCRIPT_CHARS,
        key="transcript",
    )
    visual_description = ""

    if transcript:
        char_count = len(transcript)
        pct = char_count / MAX_TRANSCRIPT_CHARS * 100
        st.caption(
            f"{'🟡' if pct > 70 else '🟢'} {char_count:,} / {MAX_TRANSCRIPT_CHARS:,} characters"
        )

# ─────────────────────────────────────────────────────────────────────────────
# Generate Button (disabled until topic has ≥5 words)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")

can_generate = topic_word_count >= 2 and bool(audience.strip())
if not can_generate:
    st.info(
        "💡 Fill in a **Core Topic** (≥2 words) and **Target Audience** to enable generation.",
        icon="ℹ️",
    )

generate_clicked = st.button(
    "✨ Generate SEO Metadata",
    disabled=not can_generate,
    key="generate_btn",
)

# ─────────────────────────────────────────────────────────────────────────────
# Internal: cache-wrapped AI call
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_generate(
    topic: str,
    audience: str,
    content_type: str,
    output_language: str,
    transcript: str,
    visual_description: str,
    chapter_notes: str,
    competitor_context: str,
) -> dict:
    """Cache key is the full set of inputs; avoids duplicate API calls on re-renders."""
    return generate_seo_metadata(
        topic=topic,
        audience=audience,
        content_type=content_type,
        output_language=output_language,
        transcript=transcript,
        visual_description=visual_description,
        chapter_notes=chapter_notes,
        competitor_context=competitor_context,
    )


# ─────────────────────────────────────────────────────────────────────────────
# On Generate
# ─────────────────────────────────────────────────────────────────────────────
if generate_clicked:

    # ── 1. Optional competitor scraping ──────────────────────────────────────
    competitor_context = ""
    if competitor_url.strip():
        with st.spinner("🔍 Scraping competitor video metadata..."):
            meta = extract_video_metadata(competitor_url.strip())
        if meta:
            parts = []
            if meta.get("title"):       parts.append(f"Title: {meta['title']}")
            if meta.get("description"): parts.append(f"Description: {meta['description']}")
            if meta.get("creator"):     parts.append(f"Channel: {meta['creator']}")
            competitor_context = "\n".join(parts)
            st.success(
                f"✅ Scraped competitor: **{meta.get('title', 'Unknown')}** "
                f"by **{meta.get('creator', 'Unknown')}**"
            )
        else:
            st.warning(
                "⚠️ Could not scrape the competitor URL (possible bot protection or invalid link). "
                "Generating from your inputs only.",
                icon="⚠️",
            )

    # ── 2. AI generation ─────────────────────────────────────────────────────
    try:
        with st.spinner("🤖 GPT-4 is crafting your SEO package... this may take 15-30 seconds"):
            result = _cached_generate(
                topic=topic.strip(),
                audience=audience.strip(),
                content_type=content_type,
                output_language=output_language,
                transcript=transcript.strip(),
                visual_description=visual_description.strip() if use_visual_desc else "",
                chapter_notes=chapter_notes.strip(),
                competitor_context=competitor_context,
            )
        st.session_state["last_result"] = result
        st.session_state["last_content_type"] = content_type
        logger.info("UI: SEO generation complete. Rendering results.")

    except APIException as e:
        st.error(f"🚨 **API Error:** {e}", icon="🚨")
        logger.error(f"API error during generation: {e}")
        st.stop()

    except ValidationException as e:
        st.error(f"⚠️ **Output Validation Error:** {e}", icon="⚠️")
        logger.error(f"Validation error during generation: {e}")
        st.stop()

    except SEOAppException as e:
        st.error(f"❌ **Application Error:** {e}", icon="❌")
        logger.error(f"App error during generation: {e}")
        st.stop()

    except Exception as e:
        st.error(f"❌ **Unexpected Error:** {e}. Please try again.", icon="❌")
        logger.error(f"Unhandled exception in UI: {e}")
        st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Results Rendering
# ─────────────────────────────────────────────────────────────────────────────
result = st.session_state.get("last_result")
last_content_type = st.session_state.get("last_content_type", "Long-Form Video")

if result:
    st.markdown("---")
    st.success("🎉 Your SEO package is ready! Use the expanders below to copy each section.", icon="✅")

    # ── Titles ────────────────────────────────────────────────────────────────
    with st.expander("🏆 A/B Titles", expanded=True):
        st.markdown("*Click the copy icon on any title to copy it to your clipboard.*")
        for i, title in enumerate(result.get("titles", []), 1):
            st.markdown(f"**Option {i}**")
            st.code(title, language=None)

    # ── Description ───────────────────────────────────────────────────────────
    with st.expander("📄 Optimized Description", expanded=True):
        st.code(result.get("description", ""), language=None)

    # ── Timestamps (long-form only) ───────────────────────────────────────────
    timestamps = result.get("timestamps", [])
    if last_content_type == "Long-Form Video":
        with st.expander("⏱️ Timestamps", expanded=bool(timestamps)):
            if timestamps:
                ts_text = "\n".join(
                    f"{ts.get('time', '')} {ts.get('label', '')}"
                    for ts in timestamps
                )
                st.code(ts_text, language=None)
            else:
                st.info(
                    "No timestamps generated — provide Chapter Notes to enable this section.",
                    icon="ℹ️",
                )

    # ── Tags ─────────────────────────────────────────────────────────────────
    with st.expander("🏷️ SEO Tags", expanded=True):
        tags = result.get("tags", [])
        if tags:
            # Visual pill display
            tag_html = "".join(f'<span class="tag-pill">{t}</span>' for t in tags)
            st.markdown(
                f'<div class="output-card">{tag_html}</div>', unsafe_allow_html=True
            )
            # Also a copyable version
            st.markdown("**Copy all tags (comma-separated):**")
            st.code(", ".join(tags), language=None)
            total_chars = len(", ".join(tags))
            st.caption(f"Tag character count: {total_chars}/500")
        else:
            st.warning("No tags returned.")

    # ── Social Media Posts ────────────────────────────────────────────────────
    with st.expander("📱 Social Media Posts", expanded=True):
        social = result.get("social_posts", {})
        tab_tw, tab_li, tab_ig = st.tabs(["Twitter / X", "LinkedIn", "Instagram"])
        with tab_tw:
            tweet = social.get("twitter", "")
            st.code(tweet, language=None)
            st.caption(f"{len(tweet)}/280 characters")
        with tab_li:
            st.code(social.get("linkedin", ""), language=None)
        with tab_ig:
            st.code(social.get("instagram", ""), language=None)

    # ── Thumbnail Ideas ───────────────────────────────────────────────────────
    with st.expander("🖼️ Thumbnail Ideas", expanded=True):
        for i, idea in enumerate(result.get("thumbnail_ideas", []), 1):
            st.markdown(f"**Concept {i}:** {idea}")
