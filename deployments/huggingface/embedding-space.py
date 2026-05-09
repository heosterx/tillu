"""
Hugging Face Space for TILLU Embedding Generation
Model: sentence-transformers/all-mpnet-base-v2

Compatible with:
  - gradio 6.x  (injected by HF build system — do NOT pin in requirements.txt)
  - sentence-transformers 3.x
  - torch 2.x
  - Python 3.13
"""
import os
import gradio as gr
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from huggingface_hub import login

# Authenticate with HF token if available (enables higher rate limits + faster downloads)
hf_token = os.environ.get("HF_TOKEN")
if hf_token:
    login(token=hf_token, add_to_git_credential=False)

# Load model
print("Loading embedding model...")
model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
print("Model loaded successfully")


def generate_embedding(text: str) -> str:
    """Generate embedding for input text"""
    try:
        # Generate embedding
        embedding = model.encode(text, convert_to_numpy=True)
        
        # Return as JSON
        return json.dumps({
            "success": True,
            "embedding": embedding.tolist(),
            "dimension": len(embedding),
            "model": "all-mpnet-base-v2"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


def generate_batch_embeddings(texts: str) -> str:
    """Generate embeddings for multiple texts (newline-separated)"""
    try:
        text_list = [t.strip() for t in texts.split('\n') if t.strip()]
        
        if not text_list:
            return json.dumps({"success": False, "error": "No texts provided"})
        
        embeddings = model.encode(text_list, convert_to_numpy=True)
        
        return json.dumps({
            "success": True,
            "embeddings": embeddings.tolist(),
            "count": len(text_list),
            "dimension": embeddings.shape[1],
            "model": "all-mpnet-base-v2"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


def similarity(text1: str, text2: str) -> str:
    """Calculate cosine similarity between two texts"""
    try:
        embeddings = model.encode([text1, text2], convert_to_numpy=True)
        
        # Calculate cosine similarity
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        
        return json.dumps({
            "success": True,
            "similarity": float(similarity),
            "text1": text1,
            "text2": text2
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# Create Gradio interface
with gr.Blocks(title="TILLU Embedding Service") as demo:
    gr.Markdown("# TILLU Embedding Service")
    gr.Markdown("Generate embeddings using sentence-transformers/all-mpnet-base-v2")
    
    with gr.Tab("Single Embedding"):
        with gr.Row():
            text_input = gr.Textbox(
                label="Input Text",
                placeholder="Enter text to generate embedding...",
                lines=3
            )
        
        embed_btn = gr.Button("Generate Embedding")
        embed_output = gr.Textbox(
            label="Embedding (JSON)",
            lines=10
        )
        
        embed_btn.click(
            fn=generate_embedding,
            inputs=text_input,
            outputs=embed_output
        )
    
    with gr.Tab("Batch Embeddings"):
        batch_input = gr.Textbox(
            label="Input Texts (one per line)",
            placeholder="Text 1\nText 2\nText 3",
            lines=10
        )
        
        batch_btn = gr.Button("Generate Batch")
        batch_output = gr.Textbox(
            label="Embeddings (JSON)",
            lines=15
        )
        
        batch_btn.click(
            fn=generate_batch_embeddings,
            inputs=batch_input,
            outputs=batch_output
        )
    
    with gr.Tab("Similarity"):
        with gr.Row():
            with gr.Column():
                sim_text1 = gr.Textbox(label="Text 1")
            with gr.Column():
                sim_text2 = gr.Textbox(label="Text 2")
        
        sim_btn = gr.Button("Calculate Similarity")
        sim_output = gr.Textbox(label="Result (JSON)", lines=5)
        
        sim_btn.click(
            fn=similarity,
            inputs=[sim_text1, sim_text2],
            outputs=sim_output
        )
    
    gr.Markdown("---")
    gr.Markdown("Powered by [sentence-transformers](https://www.sbert.net/)")


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
