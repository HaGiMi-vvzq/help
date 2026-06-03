"""Download Qwen3 local models for embedding and reranking.

Downloads from HuggingFace to backend/model_cache/.
Requires: pip install huggingface_hub sentence-transformers

Usage:
    cd backend
    python download_models.py              # download both models (~1.5 GB total)
    python download_models.py --embed-only  # only Qwen3-Embedding-0.6B
    python download_models.py --rerank-only # only Qwen3-Reranker-0.6B
"""

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("download_models")

MODEL_CACHE_DIR = Path(__file__).resolve().parent / "model_cache"

MODELS = {
    "embed": {
        "repo": "Qwen/Qwen3-Embedding-0.6B",
        "dir": "Qwen3-Embedding-0.6B",
        "desc": "Qwen3 Embedding (text embeddings for semantic search)",
    },
    "rerank": {
        "repo": "Qwen/Qwen3-Reranker-0.6B",
        "dir": "Qwen3-Reranker-0.6B",
        "desc": "Qwen3 Reranker (cross-encoder for result refinement)",
    },
}

# Approximate sizes for progress display
SIZES_MB = {"embed": 1200, "rerank": 500}


def download_via_sentence_transformers(model_key: str) -> bool:
    """Download using sentence-transformers (handles model + tokenizer)."""
    from sentence_transformers import SentenceTransformer

    info = MODELS[model_key]
    target = MODEL_CACHE_DIR / info["dir"]
    target_str = str(target)

    if target.exists() and any(target.iterdir()):
        logger.info("%s already exists at %s, skipping", info["desc"], target)
        return True

    logger.info("Downloading %s from %s (~%d MB)...", info["desc"], info["repo"], SIZES_MB[model_key])
    try:
        model = SentenceTransformer(info["repo"], cache_folder=str(MODEL_CACHE_DIR))
        model.save(target_str)
        logger.info("%s saved to %s", info["desc"], target)
        return True
    except Exception as exc:
        logger.error("Failed to download %s: %s", info["repo"], exc)
        return False


def download_via_huggingface_hub(model_key: str) -> bool:
    """Fallback: download all repo files via huggingface_hub."""
    from huggingface_hub import snapshot_download

    info = MODELS[model_key]
    target = MODEL_CACHE_DIR / info["dir"]

    if target.exists() and any(target.iterdir()):
        logger.info("%s already exists at %s, skipping", info["desc"], target)
        return True

    logger.info("Downloading %s via huggingface_hub from %s...", info["desc"], info["repo"])
    try:
        snapshot_download(
            repo_id=info["repo"],
            local_dir=str(target),
            local_dir_use_symlinks=False,
        )
        logger.info("%s saved to %s", info["desc"], target)
        return True
    except Exception as exc:
        logger.error("Failed to download %s: %s", info["repo"], exc)
        return False


def main():
    parser = argparse.ArgumentParser(description="Download Qwen3 local models")
    parser.add_argument("--embed-only", action="store_true", help="Only download embedding model")
    parser.add_argument("--rerank-only", action="store_true", help="Only download reranker model")
    args = parser.parse_args()

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.embed_only:
        keys = ["embed"]
    elif args.rerank_only:
        keys = ["rerank"]
    else:
        keys = ["embed", "rerank"]

    success = True
    for key in keys:
        # Try sentence-transformers first, fallback to huggingface_hub
        if not download_via_sentence_transformers(key):
            logger.info("Retrying with huggingface_hub fallback...")
            if not download_via_huggingface_hub(key):
                success = False

    if success:
        logger.info("All models downloaded successfully to %s", MODEL_CACHE_DIR)
    else:
        logger.error("Some models failed to download. Check network and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
