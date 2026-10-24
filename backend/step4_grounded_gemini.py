"""Optional: isolated Gemini server-side RAG generation, NOT a root-agent native tool.

This incurs model and retrieval charges when run with real credentials. The
main integration uses raw retrieved passages instead; use this only if Gemini
server-side grounding metadata is a requirement. Historical mixed-tool bugs
are a compatibility caution, not proof every current model rejects mixing.
"""
from __future__ import annotations

import argparse
import json

from google import genai
from google.genai import types

from common import Settings


def grounded_answer(
    client: genai.Client, corpus_name: str, question: str, model: str
) -> dict:
    result = client.models.generate_content(
        model=model,
        contents=question,
        config=types.GenerateContentConfig(
            tools=[types.Tool(retrieval=types.Retrieval(
                vertex_rag_store=types.VertexRagStore(
                    rag_resources=[types.VertexRagStoreRagResource(rag_corpus=corpus_name)],
                    rag_retrieval_config=types.RagRetrievalConfig(top_k=5),
                )
            ))],
            temperature=0,
        ),
    )
    candidates = result.candidates or []
    metadata = candidates[0].grounding_metadata if candidates else None
    return {
        "answer": result.text,
        "corpus": corpus_name,
        # Retain both grounding_chunks AND grounding_supports. A source list
        # alone does not map generated answer spans back to retrieved passages.
        "grounding_metadata": metadata.model_dump(mode="json", exclude_none=True)
                              if metadata else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.model:
        raise ValueError("Set GOOGLE_MODEL to a Gemini model supporting RAG grounding.")
    corpus = settings.require_corpus()
    # Start co-located for native grounding; do not assume global/cross-region
    # support. This is distinct from the decoupled raw-retrieval architecture.
    client = genai.Client(
        enterprise=True,
        project=settings.project,
        location="global",
        http_options=types.HttpOptions(api_version="v1", timeout=60_000),
    )
    try:
        print(json.dumps(grounded_answer(client, corpus, args.question, settings.model), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
