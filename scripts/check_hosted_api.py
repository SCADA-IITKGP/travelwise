"""Run a safe, minimal test against the configured hosted LLM and embedding APIs.

Usage:
  Set LLM_MODE=hosted, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL=Qwen/Qwen3-8B, LLM_CA_CERT_FILE
  and optionally EMBEDDING_BASE_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL=bge-small-en-v1.5, EMBEDDING_CA_CERT_FILE
  python -m scripts.check_hosted_api

This script never prints API keys or authorization headers.
"""
import asyncio
from backend import embeddings
from backend.llm import health_check


async def main():
    try:
        result = await health_check()
        print("Hosted LLM API connectivity: SUCCESS")
        print("Configured model is available:", result["model_available"])
        print("Configured model ID:", result["configured_model"])
    except Exception as exc:
        print("Hosted LLM API connectivity: FAILED")
        print("Reason:", str(exc))

    if embeddings.is_configured():
        try:
            vectors = embeddings.embed_texts(["Example document chunk", "Example search query"])
            print("Capstone Embedding API connectivity: SUCCESS")
            print("Embedding model ID:", embeddings.current_model())
            print("Vector count & dimension:", len(vectors), len(vectors[0]))
        except Exception as exc:
            print("Capstone Embedding API connectivity: FAILED")
            print("Reason:", str(exc))
    else:
        print("Capstone Embedding API: NOT CONFIGURED (set EMBEDDING_API_KEY and EMBEDDING_CA_CERT_FILE)")


if __name__ == "__main__":
    asyncio.run(main())
