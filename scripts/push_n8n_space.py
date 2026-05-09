"""
Push TILLU Engine (n8n) to HuggingFace Space.
Creates the Space if it doesn't exist, then uploads all files.
"""
from huggingface_hub import HfApi, create_repo
from huggingface_hub.utils import RepositoryNotFoundError
import os

import os

TOKEN = os.environ.get("HF_TOKEN", "")
if not TOKEN:
    raise ValueError("Set HF_TOKEN environment variable before running this script")
REPO_ID = "tillu-AI/tillu-engine"
SPACE_DIR = os.path.join(os.path.dirname(__file__), "..", "deployments", "huggingface", "n8n-space")

api = HfApi(token=TOKEN)

# ── Step 1: Create Space if it doesn't exist ─────────────────────
print(f"Checking Space: {REPO_ID} ...")
try:
    api.repo_info(repo_id=REPO_ID, repo_type="space")
    print("Space already exists.")
except RepositoryNotFoundError:
    print("Creating Space...")
    create_repo(
        repo_id=REPO_ID,
        repo_type="space",
        space_sdk="docker",
        private=False,
        token=TOKEN,
    )
    print(f"Space created: https://huggingface.co/spaces/{REPO_ID}")

# ── Step 2: Upload all files ──────────────────────────────────────
files_to_upload = []

for root, dirs, files in os.walk(SPACE_DIR):
    # Skip hidden dirs
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for fname in files:
        local_path = os.path.join(root, fname)
        # Path relative to SPACE_DIR = path in the Space repo
        rel_path = os.path.relpath(local_path, SPACE_DIR).replace("\\", "/")
        files_to_upload.append((local_path, rel_path))

print(f"\nUploading {len(files_to_upload)} files to {REPO_ID}:")
for local_path, repo_path in files_to_upload:
    print(f"  {repo_path}")
    api.upload_file(
        path_or_fileobj=local_path,
        path_in_repo=repo_path,
        repo_id=REPO_ID,
        repo_type="space",
        commit_message=f"upload {repo_path}",
    )

print(f"\n✅ Done! Space live at: https://huggingface.co/spaces/{REPO_ID}")
print("⏳ Build will start automatically — check the Space for logs.")
