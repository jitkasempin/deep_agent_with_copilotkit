"""Offline contract tests. All policy text and model responses below are fixtures.

Real installed SDK models, serializers, LangChain tools, and Deep Agents graph
execution are used. Only cloud HTTP/operation boundaries and LLM decisions are
mocked. Tests cannot establish cloud IAM, indexing quality, or model quality.
"""
from __future__ import annotations

import json
import socket
from collections.abc import Callable, Sequence
from typing import Any
from unittest.mock import Mock

import pytest
from agentplatform import types as ap_types
from google import genai
from google.auth.credentials import AnonymousCredentials
from google.cloud.aiplatform_v1 import types as vertex_types
from google.genai import types as genai_types
from google.protobuf import json_format
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from common import Settings
from sdk_client import AgentPlatformClient
from step1_provision_rag_corpus import create_corpus, import_gcs_documents, list_all_files
from step2_rag_engine_tools import make_retrieval_tool
from step3_deep_agent_integration import build_agent
from step4_grounded_gemini import grounded_answer

CORPUS = "projects/test-project/locations/us-west1/ragCorpora/123"
FIXTURE_TEXT = "TEST FIXTURE ONLY: remote work requires manager approval."
FIXTURE_URI = "gs://test-fixtures/policy.txt"


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline suite attempted a real network connection")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def client():
    return AgentPlatformClient(
        project="test-project", location="us-west1",
        credentials=AnonymousCredentials(),
        http_options=genai_types.HttpOptions(api_version="v1"),
    )


def mock_response(payload: dict) -> genai_types.HttpResponse:
    return genai_types.HttpResponse(body=json.dumps(payload))


def retrieval_fixture() -> dict:
    return {"contexts": {"contexts": [{
        "text": FIXTURE_TEXT, "sourceUri": FIXTURE_URI,
        "sourceDisplayName": "policy.txt", "score": 1.2, "distance": 1.2,
        "chunk": {"pageSpan": {"firstPage": 2, "lastPage": 3}, "chunkId": "fixture-chunk"},
    }]}}


def install_transport(monkeypatch: pytest.MonkeyPatch, client, payload: dict):
    request = Mock(return_value=mock_response(payload))
    monkeypatch.setattr(client._api_client, "request", request)
    return request


class ScriptedModel(GenericFakeChatModel):
    """A deterministic test model, not an LLM or evidence of model accuracy."""
    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *, tool_choice: str | None = None,
        **kwargs: Any,
    ):
        return self


def call_message(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_real_sdk_request_and_citations(client, monkeypatch):
    request = install_transport(monkeypatch, client, retrieval_fixture())
    tool = make_retrieval_tool(client, CORPUS)
    result = tool.invoke({"query": "remote work", "top_k": 3})
    assert result["status"] == "ok" and result["chunk_count"] == 1
    chunk = result["chunks"][0]
    assert chunk["text"] == FIXTURE_TEXT and chunk["source_uri"] == FIXTURE_URI
    assert chunk["score"] == 1.2  # Valid distance, not a 0..1 confidence probability.
    assert chunk["chunk"]["page_span"] == {"first_page": 2, "last_page": 3}
    assert chunk["citation_id"].startswith("R-")
    method, path, body, _ = request.call_args.args
    assert method == "post" and path == ":retrieveContexts"
    # SDK 2.5 emits snake_case in some nested fields and camelCase in others.
    # Decode through the real schema, which accepts both JSON field spellings.
    store = genai_types.VertexRagStore.model_validate(body["vertexRagStore"])
    query = ap_types.RagQuery.model_validate(body["query"])
    assert store.rag_resources and store.rag_resources[0].rag_corpus == CORPUS
    assert query.rag_retrieval_config.top_k == 3
    assert query.rag_retrieval_config.filter is None


def test_citation_id_is_stable(client, monkeypatch):
    install_transport(monkeypatch, client, retrieval_fixture())
    tool = make_retrieval_tool(client, CORPUS)
    first = tool.invoke({"query": "one"})
    second = tool.invoke({"query": "two"})
    assert first["chunks"][0]["citation_id"] == second["chunks"][0]["citation_id"]


@pytest.mark.parametrize("payload", [{}, {"contexts": {}}, {"contexts": {"contexts": []}}])
def test_empty_response_is_explicit(client, monkeypatch, payload):
    install_transport(monkeypatch, client, payload)
    out = make_retrieval_tool(client, CORPUS).invoke({"query": "no match"})
    assert out["status"] == "no_matching_contexts" and out["chunks"] == []


@pytest.mark.parametrize("arguments", [
    {"query": ""}, {"query": "a", "top_k": 0}, {"query": "a", "top_k": 11},
    {"query": "a", "corpus_name": "unauthorized"}, {"query": "a" * 2001},
])
def test_input_validation_prevents_request(client, monkeypatch, arguments):
    request = install_transport(monkeypatch, client, {})
    with pytest.raises(ValidationError):
        make_retrieval_tool(client, CORPUS).invoke(arguments)
    request.assert_not_called()


def test_blank_query_rejected(client, monkeypatch):
    request = install_transport(monkeypatch, client, {})
    with pytest.raises(ValueError, match="non-whitespace"):
        make_retrieval_tool(client, CORPUS).invoke({"query": "   "})
    request.assert_not_called()


def test_service_error_is_not_reported_as_empty_evidence(client, monkeypatch):
    request = Mock(side_effect=RuntimeError("fixture service unavailable"))
    monkeypatch.setattr(client._api_client, "request", request)
    with pytest.raises(RuntimeError, match="service unavailable"):
        make_retrieval_tool(client, CORPUS).invoke({"query": "test"})


def test_large_passage_has_explicit_truncation(client, monkeypatch):
    payload = retrieval_fixture()
    payload["contexts"]["contexts"][0]["text"] = "x" * 6500
    install_transport(monkeypatch, client, payload)
    passage = make_retrieval_tool(client, CORPUS).invoke({"query": "test"})["chunks"][0]
    assert len(passage["text"]) == 6000 and passage["text_truncated"] is True


@pytest.mark.parametrize("corpus,location", [
    (None, "us-west1"), ("display-name", "us-west1"), (CORPUS, "us-central1"),
])
def test_corpus_configuration_rejected(corpus, location):
    with pytest.raises(ValueError):
        Settings(project="test-project", rag_location=location, corpus_name=corpus).require_corpus()


def test_no_silent_placeholder_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT"):
        Settings.from_env()


def test_real_graph_calls_tool_and_returns_evidence(client, monkeypatch):
    request = install_transport(monkeypatch, client, retrieval_fixture())
    model = ScriptedModel(messages=iter([
        call_message("retrieve_rag_corpus", {"query": "remote work", "top_k": 2}, "lookup-1"),
        AIMessage(content="Scripted answer based on the fixture tool response."),
    ]))
    agent = build_agent(model, make_retrieval_tool(client, CORPUS))
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Test policy?"}]},
        config={"configurable": {"thread_id": "direct-test"}},
    )
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert FIXTURE_TEXT in str(tool_messages[0].content)
    assert result["messages"][-1].content.startswith("Scripted answer")
    assert request.call_count == 1


def test_subagent_retrieval_and_evidence_reaches_parent(client, monkeypatch):
    request = install_transport(monkeypatch, client, retrieval_fixture())
    model = ScriptedModel(messages=iter([
        call_message("task", {"description": "Find policy and save evidence", "subagent_type": "gcp-rag-researcher"}, "delegate-1"),
        call_message("retrieve_rag_corpus", {"query": "remote work"}, "sub-lookup"),
        call_message("write_file", {"file_path": "/evidence/test-policy.txt", "content": FIXTURE_TEXT}, "save-1"),
        AIMessage(content="Fixture evidence saved at /evidence/test-policy.txt."),
        AIMessage(content="Scripted supervisor response."),
    ]))
    agent = build_agent(model, make_retrieval_tool(client, CORPUS))
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Research test policy"}]},
        config={"configurable": {"thread_id": "subagent-test"}},
    )
    assert request.call_count == 1
    assert "/evidence/test-policy.txt" in result["files"]
    assert result["files"]["/evidence/test-policy.txt"]["content"] == FIXTURE_TEXT
    # Only final task output is visible in parent messages, not subagent search history.
    assert not any(isinstance(m, ToolMessage) and m.name == "retrieve_rag_corpus" for m in result["messages"])


def test_creation_polls_operation_and_reads_back(client, monkeypatch):
    corpus = {"name": CORPUS, "displayName": "test corpus"}
    operation = {"name": "projects/test-project/locations/us-west1/operations/create-test", "done": True, "response": corpus}
    def transport(method, path, body, http_options):
        if method == "post":
            assert path == "ragCorpora"
            json_format.ParseDict(body, vertex_types.RagCorpus.pb()())
            assert body["displayName"] == "test corpus"
            assert "ragVectorDbConfig" not in body
            endpoint = body["vectorDbConfig"]["ragEmbeddingModelConfig"]["vertexPredictionEndpoint"]["endpoint"]
            assert endpoint == (
                "projects/test-project/locations/us-west1/"
                "publishers/google/models/text-embedding-005"
            )
            return mock_response(operation)
        return mock_response(operation if "operations/" in path else corpus)
    request = Mock(side_effect=transport)
    monkeypatch.setattr(client._api_client, "request", request)
    result = create_corpus(
        client, "test corpus",
        settings=Settings(project="test-project", rag_location="us-west1"),
    )
    assert result.name == CORPUS
    assert any(c.args[0] == "get" and c.args[1] == CORPUS for c in request.call_args_list)


def test_import_serializes_chunking_and_preserves_failure_counts(client, monkeypatch):
    # Bucket ownership check is a separate Cloud Storage network boundary.
    from agentplatform._genai import _gcs_utils
    ownership = Mock(return_value=True)
    monkeypatch.setattr(_gcs_utils.GcsUtils, "_verify_bucket_ownership", ownership)
    counts = {"importedRagFilesCount": 1, "failedRagFilesCount": 1, "skippedRagFilesCount": 0}
    operation = {"name": "projects/test-project/locations/us-west1/operations/import-test", "done": True, "response": counts}
    def transport(method, path, body, http_options):
        if method == "post":
            assert path == CORPUS + "/ragFiles:import"
            config = body["importRagFilesConfig"]
            json_format.ParseDict(config, vertex_types.ImportRagFilesConfig.pb()())
            assert config["gcsSource"]["uris"] == ["gs://test-fixtures/policy.txt"]
            transform = ap_types.RagFileTransformationConfig.model_validate(config["ragFileTransformationConfig"])
            assert transform.rag_file_chunking_config is not None
            assert transform.rag_file_chunking_config.fixed_length_chunking is not None
            assert transform.rag_file_chunking_config.fixed_length_chunking.chunk_size == 512
            assert transform.rag_file_chunking_config.fixed_length_chunking.chunk_overlap == 100
        return mock_response(operation)
    monkeypatch.setattr(client._api_client, "request", Mock(side_effect=transport))
    response = import_gcs_documents(client, CORPUS, [FIXTURE_URI])
    assert response.imported_rag_files_count == 1 and response.failed_rag_files_count == 1
    ownership.assert_called_once()


def test_file_listing_follows_all_pages(client, monkeypatch):
    request = Mock(side_effect=[
        mock_response({"ragFiles": [{"name": CORPUS + "/ragFiles/1"}], "nextPageToken": "page-two"}),
        mock_response({"ragFiles": [{"name": CORPUS + "/ragFiles/2"}]}),
    ])
    monkeypatch.setattr(client._api_client, "request", request)
    files = list(list_all_files(client, CORPUS))
    assert [f.name for f in files] == [CORPUS + "/ragFiles/1", CORPUS + "/ragFiles/2"]
    assert "pageToken=page-two" in request.call_args_list[1].args[1]


def test_native_grounding_keeps_support_mapping(monkeypatch):
    client = genai.Client(enterprise=True, project="test-project", location="us-west1", credentials=AnonymousCredentials())
    payload = {"candidates": [{
        "content": {"role": "model", "parts": [{"text": "Fixture grounded answer."}]},
        "groundingMetadata": {
            "groundingChunks": [{"retrievedContext": {"uri": FIXTURE_URI, "title": "policy.txt"}}],
            "groundingSupports": [{"segment": {"startIndex": 0, "endIndex": 24, "text": "Fixture grounded answer."}, "groundingChunkIndices": [0]}],
        },
    }]}
    request = install_transport(monkeypatch, client, payload)
    out = grounded_answer(client, CORPUS, "Fixture question", "test-model")
    assert out["grounding_metadata"]["grounding_supports"][0]["grounding_chunk_indices"] == [0]
    body = request.call_args.args[2]
    tools = body["generationConfig"]["tools"] if "tools" in body.get("generationConfig", {}) else body["tools"]
    assert len(tools) == 1 and "retrieval" in tools[0]
    assert "functionDeclarations" not in tools[0]
    client.close()
