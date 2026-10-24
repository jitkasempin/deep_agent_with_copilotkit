"""Create/import/list RAG resources outside the answering agent.

These commands make real, billable GCP requests when explicitly run.
Reference: current official RAG quickstart, source [28] in the research folder.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Iterator

from sdk_client import AgentPlatformClient
from agentplatform import types
from google.genai import types as genai_types

from common import Settings, make_rag_client


def create_corpus(
    client: AgentPlatformClient, display_name: str, *, settings: Settings
) -> types.RagCorpus:
    """Create once; retain its resource name. Display names are not unique keys.

    This does not silently change the project/region RagManagedDb billing tier.
    Review that tier in GCP before creation; managed storage may incur charges.
    """
    corpus = client.rag.create_corpus(
        rag_corpus=types.RagCorpus(
            display_name=display_name,
            vector_db_config=types.RagVectorDbConfig(
                rag_embedding_model_config=types.RagEmbeddingModelConfig(
                    vertex_prediction_endpoint=types.RagEmbeddingModelConfigVertexPredictionEndpoint(
                        endpoint=(
                            f"projects/{settings.project}/locations/{settings.rag_location}/"
                            "publishers/google/models/text-embedding-005"
                        )
                    )
                )
            ),
        )
    )
    if not corpus.name:
        raise RuntimeError("Create response contained no corpus resource name.")
    # The SDK already waits for creation and gets the corpus; this explicit
    # read also makes the verification requirement clear to callers.
    return client.rag.get_corpus(name=corpus.name)


def import_gcs_documents(
    client: AgentPlatformClient, corpus_name: str, gcs_uris: list[str]
) -> types.ImportRagFilesResponse:
    """Wait for an import operation. Counts may include partial failures.

    SDK 2.5.0 checks source bucket ownership against the client's project.
    Use a same-project bucket for this walkthrough, and grant bucket metadata
    read permission to the provisioning identity plus objectViewer to the
    separate Vertex RAG Data Service Agent. See the guide's IAM discussion.
    """
    if not gcs_uris or any(not uri.startswith("gs://") for uri in gcs_uris):
        raise ValueError("Supply at least one gs://bucket/object-or-prefix URI.")
    return client.rag.import_files(
        name=corpus_name,
        import_config=types.ImportRagFilesConfig(
            gcs_source=genai_types.GcsSource(uris=gcs_uris),
            rag_file_transformation_config=types.RagFileTransformationConfig(
                rag_file_chunking_config=types.RagFileChunkingConfig(
                    fixed_length_chunking=types.RagFileChunkingConfigFixedLengthChunking(
                        chunk_size=512, chunk_overlap=100
                    )
                )
            ),
            # Example ingestion cap, not a claim about your granted quota.
            max_embedding_requests_per_min=100,
        ),
    )


def list_all_files(
    client: AgentPlatformClient, corpus_name: str
) -> Iterator[types.RagFile]:
    """The client returns a response object, not an auto-paginating list."""
    page_token: str | None = None
    while True:
        page = client.rag.list_files(
            name=corpus_name,
            config=types.ListRagFilesConfig(page_size=100, page_token=page_token),
        )
        yield from page.rag_files or []
        page_token = page.next_page_token
        if not page_token:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create a new billable corpus ONCE")
    create.add_argument("--display-name", required=True)
    ingest = commands.add_parser("import", help="Import GCS documents; consumes resources")
    ingest.add_argument("gcs_uris", nargs="+")
    commands.add_parser("list", help="List every imported file")
    args = parser.parse_args()
    settings = Settings.from_env()
    client = make_rag_client(settings)
    if args.command == "create":
        corpus = create_corpus(client, args.display_name, settings=settings)
        print(corpus.model_dump_json(exclude_none=True, indent=2))
    elif args.command == "import":
        corpus = settings.require_corpus()
        result = import_gcs_documents(client, corpus, args.gcs_uris)
        print(result.model_dump_json(exclude_none=True, indent=2))
        files = [f.model_dump(mode="json", exclude_none=True) for f in list_all_files(client, corpus)]
        print(json.dumps({"listed_file_count": len(files), "files": files}, indent=2))
        if result.failed_rag_files_count:
            raise SystemExit("Import reported failures; inspect the result sink and retry deliberately.")
    else:
        files = [f.model_dump(mode="json", exclude_none=True)
                 for f in list_all_files(client, settings.require_corpus())]
        print(json.dumps({"file_count": len(files), "files": files}, indent=2))


if __name__ == "__main__":
    main()
