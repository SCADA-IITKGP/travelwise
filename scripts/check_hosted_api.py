"""Run a safe, minimal test against the configured hosted API.

Usage:
  Set LLM_MODE=hosted, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL and LLM_CA_CERT_FILE
  python -m scripts.check_hosted_api

This script never prints the API key or authorization headers.
"""
import asyncio
from backend.llm import health_check

async def main():
    try:
        result = await health_check()
        print("Hosted API connectivity: SUCCESS")
        print("Configured model is available:", result["model_available"])
        print("Configured model ID:", result["configured_model"])
    except Exception as exc:
        print("Hosted API connectivity: FAILED")
        print("Reason:", str(exc))

if __name__ == "__main__":
    asyncio.run(main())
