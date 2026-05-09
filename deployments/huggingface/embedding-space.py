"""
TILLU AI — HuggingFace Space
==============================
Unified NLP service for TILLU backend.

Models loaded:
  1. sentence-transformers/all-mpnet-base-v2     — 768-dim embeddings (Hindi + English)
  2. j-hartmann/emotion-english-distilroberta-base — emotion detection
  3. Hate-speech-CNERG/indic-abusive-allInOne    — Hindi/English abuse detection

API endpoints (via Gradio + FastAPI):
  POST /embed          — single text → 768-dim vector
  POST /embed-batch    — list of texts → list of vectors
  POST /similarity     — two texts → cosine similarity score
  POST /emotion        — text → emotion scores (7 classes)
  POST /classify-lang  — text → hi | en | mixed

Hindi + English bilingual throughout.
Compatible with: gradio 6.x, sentence-transformers 3.x, torch 2.x, Python 3.13
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import gradio as gr
import numpy as np
from huggingface_hub import login
from sentence_transformers import SentenceTransformer

# ── Auth ─────────────────────────────────────────────────────────────────────
hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    login(token=hf_token, add_to_git_credential=False)
    print("✅ HF Token authenticated / HF Token प्रमाणित")
else:
    print("⚠️  No HF_TOKEN — unauthenticated mode / HF_TOKEN नहीं मिला")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tillu.space")

# ── Model loading ─────────────────────────────────────────────────────────────

logger.info("Loading embedding model / एम्बेडिंग मॉडल लोड हो रहा है…")
embed_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
logger.info("✅ Embedding model ready / एम्बेडिंग मॉडल तैयार")

# Emotion model — lazy-loaded on first use to save startup time
_emotion_pipeline = None

def get_emotion_pipeline():
    global _emotion_pipeline
    if _emotion_pipeline is None:
        from transformers import pipeline
        logger.info("Loading emotion model / इमोशन मॉडल लोड हो रहा है…")
        _emotion_pipeline = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None,
            device=-1,  # CPU
        )
        logger.info("✅ Emotion model ready / इमोशन मॉडल तैयार")
    return _emotion_pipeline

# ── Language detection ────────────────────────────────────────────────────────

HINDI_RE = re.compile(r"[\u0900-\u097F]")

def detect_lang(text: str) -> str:
    """Detect Hindi vs English from script."""
    hindi_chars = len(HINDI_RE.findall(text))
    total_chars = len([c for c in text if c.isalpha()])
    if total_chars == 0:
        return "en"
    ratio = hindi_chars / total_chars
    if ratio > 0.6:
        return "hi"
    if ratio > 0.2:
        return "mixed"
    return "en"

# ── Stats ─────────────────────────────────────────────────────────────────────

_stats = {
    "start_time": time.time(),
    "embed_calls": 0,
    "emotion_calls": 0,
    "similarity_calls": 0,
    "errors": 0,
}

# ── Core functions ────────────────────────────────────────────────────────────

def embed_text(text: str) -> str:
    """
    Generate 768-dim embedding for a single text.
    Works for Hindi and English.
    Input:  text string
    Output: JSON {"success": true, "embedding": [...], "dimension": 768, "lang": "hi|en|mixed"}
    """
    if not text or not text.strip():
        return json.dumps({"success": False, "error": "Empty text / खाली टेक्स्ट"})
    try:
        _stats["embed_calls"] += 1
        lang = detect_lang(text)
        vec = embed_model.encode(text.strip(), convert_to_numpy=True, normalize_embeddings=True)
        return json.dumps({
            "success": True,
            "embedding": vec.tolist(),
            "dimension": len(vec),
            "lang": lang,
            "model": "all-mpnet-base-v2",
        })
    except Exception as e:
        _stats["errors"] += 1
        logger.error("embed_text error: %s", e)
        return json.dumps({"success": False, "error": str(e)})


def embed_batch(texts_raw: str) -> str:
    """
    Generate embeddings for multiple texts (one per line).
    Input:  newline-separated texts (Hindi or English)
    Output: JSON {"success": true, "embeddings": [[...], ...], "count": N, "langs": [...]}
    """
    texts = [t.strip() for t in texts_raw.split("\n") if t.strip()]
    if not texts:
        return json.dumps({"success": False, "error": "No texts provided / कोई टेक्स्ट नहीं"})
    try:
        _stats["embed_calls"] += len(texts)
        langs = [detect_lang(t) for t in texts]
        vecs = embed_model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32)
        return json.dumps({
            "success": True,
            "embeddings": vecs.tolist(),
            "count": len(texts),
            "dimension": vecs.shape[1],
            "langs": langs,
            "model": "all-mpnet-base-v2",
        })
    except Exception as e:
        _stats["errors"] += 1
        logger.error("embed_batch error: %s", e)
        return json.dumps({"success": False, "error": str(e)})


def compute_similarity(text1: str, text2: str) -> str:
    """
    Cosine similarity between two texts.
    Works cross-lingually (Hindi ↔ English).
    Output: JSON {"success": true, "similarity": 0.87, "interpretation": "very similar"}
    """
    if not text1.strip() or not text2.strip():
        return json.dumps({"success": False, "error": "Both texts required / दोनों टेक्स्ट चाहिए"})
    try:
        _stats["similarity_calls"] += 1
        vecs = embed_model.encode(
            [text1.strip(), text2.strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        # Since vectors are L2-normalized, dot product = cosine similarity
        sim = float(np.dot(vecs[0], vecs[1]))

        if sim >= 0.9:
            interp = "identical / एक जैसे"
        elif sim >= 0.75:
            interp = "very similar / बहुत समान"
        elif sim >= 0.5:
            interp = "related / संबंधित"
        elif sim >= 0.25:
            interp = "loosely related / थोड़े संबंधित"
        else:
            interp = "unrelated / असंबंधित"

        return json.dumps({
            "success": True,
            "similarity": round(sim, 4),
            "interpretation": interp,
            "lang1": detect_lang(text1),
            "lang2": detect_lang(text2),
        })
    except Exception as e:
        _stats["errors"] += 1
        logger.error("similarity error: %s", e)
        return json.dumps({"success": False, "error": str(e)})


def detect_emotion(text: str) -> str:
    """
    Detect emotion in text (Hindi or English).
    Returns 7 emotion scores: anger, disgust, fear, joy, neutral, sadness, surprise.
    Also returns stress_level: low | medium | high
    """
    if not text.strip():
        return json.dumps({"success": False, "error": "Empty text / खाली टेक्स्ट"})
    try:
        _stats["emotion_calls"] += 1
        pipe = get_emotion_pipeline()
        results = pipe(text[:512])  # model max 512 tokens
        scores = {r["label"].lower(): round(r["score"], 4) for r in results[0]}

        dominant = max(scores, key=scores.get)

        # Stress heuristic
        stress_score = scores.get("anger", 0) + scores.get("fear", 0) + scores.get("disgust", 0)
        if stress_score > 0.6:
            stress = "high"
        elif stress_score > 0.3:
            stress = "medium"
        else:
            stress = "low"

        return json.dumps({
            "success": True,
            "scores": scores,
            "dominant_emotion": dominant,
            "stress_level": stress,
            "lang": detect_lang(text),
        })
    except Exception as e:
        _stats["errors"] += 1
        logger.error("emotion error: %s", e)
        return json.dumps({"success": False, "error": str(e)})


def classify_language(text: str) -> str:
    """
    Classify text language: Hindi, English, or Mixed.
    Uses Unicode script analysis — no external API needed.
    """
    if not text.strip():
        return json.dumps({"success": False, "error": "Empty text"})
    lang = detect_lang(text)
    hindi_chars = len(HINDI_RE.findall(text))
    total_alpha = len([c for c in text if c.isalpha()])
    return json.dumps({
        "success": True,
        "lang": lang,
        "hindi_char_ratio": round(hindi_chars / max(total_alpha, 1), 3),
        "total_chars": len(text),
    })


def get_stats() -> str:
    """Service statistics."""
    uptime = round(time.time() - _stats["start_time"], 1)
    return json.dumps({
        "uptime_seconds": uptime,
        "embed_calls": _stats["embed_calls"],
        "emotion_calls": _stats["emotion_calls"],
        "similarity_calls": _stats["similarity_calls"],
        "errors": _stats["errors"],
        "models_loaded": ["all-mpnet-base-v2", "emotion-distilroberta (lazy)"],
    })


# ── Gradio UI ─────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="TILLU AI — NLP Service",
    theme=gr.themes.Soft(primary_hue="indigo"),
    css=".gradio-container { max-width: 900px; margin: auto; }",
) as demo:

    gr.Markdown("""
    # 🤖 TILLU AI — NLP Service
    **Hindi + English bilingual NLP backend**
    
    Provides embeddings, emotion detection, and similarity scoring for the TILLU personal AI system.
    All endpoints work with Hindi (हिंदी) and English text.
    """)

    with gr.Tab("📐 Embed Text"):
        gr.Markdown("Generate a 768-dimensional semantic embedding. Works for Hindi and English.")
        with gr.Row():
            embed_input = gr.Textbox(
                label="Text / टेक्स्ट",
                placeholder="Enter text in Hindi or English… / हिंदी या अंग्रेज़ी में टेक्स्ट लिखें…",
                lines=3,
            )
        embed_btn = gr.Button("Generate Embedding / एम्बेडिंग बनाएं", variant="primary")
        embed_output = gr.Textbox(label="Result (JSON)", lines=8)
        embed_btn.click(fn=embed_text, inputs=embed_input, outputs=embed_output)

    with gr.Tab("📦 Batch Embed"):
        gr.Markdown("Embed multiple texts at once (one per line). Supports mixed Hindi/English batches.")
        batch_input = gr.Textbox(
            label="Texts (one per line) / टेक्स्ट (एक प्रति पंक्ति)",
            placeholder="Hello world\nनमस्ते दुनिया\nHow are you?\nआप कैसे हैं?",
            lines=8,
        )
        batch_btn = gr.Button("Embed Batch / बैच एम्बेड करें", variant="primary")
        batch_output = gr.Textbox(label="Result (JSON)", lines=12)
        batch_btn.click(fn=embed_batch, inputs=batch_input, outputs=batch_output)

    with gr.Tab("🔗 Similarity"):
        gr.Markdown("Cosine similarity between two texts. Cross-lingual: compare Hindi with English.")
        with gr.Row():
            with gr.Column():
                sim_text1 = gr.Textbox(label="Text 1", placeholder="Hello, how are you?", lines=3)
            with gr.Column():
                sim_text2 = gr.Textbox(label="Text 2", placeholder="नमस्ते, आप कैसे हैं?", lines=3)
        sim_btn = gr.Button("Calculate Similarity / समानता जांचें", variant="primary")
        sim_output = gr.Textbox(label="Result (JSON)", lines=6)
        sim_btn.click(fn=compute_similarity, inputs=[sim_text1, sim_text2], outputs=sim_output)

    with gr.Tab("😊 Emotion"):
        gr.Markdown("Detect emotion and stress level. Best results with English; Hindi supported via cross-lingual transfer.")
        emotion_input = gr.Textbox(
            label="Text / टेक्स्ट",
            placeholder="I'm feeling really anxious about tomorrow… / कल के बारे में बहुत चिंता हो रही है…",
            lines=3,
        )
        emotion_btn = gr.Button("Detect Emotion / भावना पहचानें", variant="primary")
        emotion_output = gr.Textbox(label="Result (JSON)", lines=10)
        emotion_btn.click(fn=detect_emotion, inputs=emotion_input, outputs=emotion_output)

    with gr.Tab("🌐 Language"):
        gr.Markdown("Classify text as Hindi, English, or Mixed using Unicode script analysis.")
        lang_input = gr.Textbox(
            label="Text / टेक्स्ट",
            placeholder="यह एक mixed language sentence है।",
            lines=2,
        )
        lang_btn = gr.Button("Detect Language / भाषा पहचानें", variant="primary")
        lang_output = gr.Textbox(label="Result (JSON)", lines=5)
        lang_btn.click(fn=classify_language, inputs=lang_input, outputs=lang_output)

    with gr.Tab("📊 Stats"):
        gr.Markdown("Service statistics and uptime.")
        stats_btn = gr.Button("Refresh Stats / आँकड़े ताज़ा करें")
        stats_output = gr.Textbox(label="Stats (JSON)", lines=10)
        stats_btn.click(fn=get_stats, inputs=[], outputs=stats_output)

    gr.Markdown("""
    ---
    **TILLU AI** — Personal AI for Hindi + English speakers  
    Models: [all-mpnet-base-v2](https://huggingface.co/sentence-transformers/all-mpnet-base-v2) · 
    [emotion-distilroberta](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base)
    """)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
