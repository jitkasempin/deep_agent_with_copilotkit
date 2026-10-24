"""Configuration shared by the runnable integration examples.

No credentials are read and no network requests occur on import. Production
services must supply project/corpus configuration from trusted server settings,
not from an LLM or an unauthenticated request body.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentplatform._genai.client import Client as AgentPlatformClient
else:
    from agentplatform import Client as AgentPlatformClient

# from sdk_client import AgentPlatformClient
from google.genai import types as genai_types


@dataclass(frozen=True)
class Settings:
    project: str
    rag_location: str
    corpus_name: str | None = None
    model: str | None = None
    model_location: str = "global"

    def require_corpus(self) -> str:
        if not self.corpus_name:
            raise ValueError("Set VERTEX_RAG_CORPUS_NAME to the returned full resource name.")
        match = re.fullmatch(
            r"projects/([^/]+)/locations/([^/]+)/ragCorpora/([^/]+)", self.corpus_name
        )
        if not match:
            raise ValueError("Invalid corpus resource name; do not supply a display name.")
        if match[2] != self.rag_location:
            raise ValueError("VERTEX_RAG_LOCATION must match the corpus resource location.")
        # A project ID and its numeric project number may identify the same project.
        # Do not try to normalize or infer that mapping here.
        return self.corpus_name

    @classmethod
    def from_env(cls) -> Settings:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("VERTEX_RAG_LOCATION")
        if not project or not location:
            raise ValueError("Set GOOGLE_CLOUD_PROJECT and VERTEX_RAG_LOCATION.")
        return cls(
            project=project,
            rag_location=location,
            corpus_name=os.environ.get("VERTEX_RAG_CORPUS_NAME"),
            model=os.environ.get("GOOGLE_MODEL"),
            model_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        )


def make_rag_client(settings: Settings) -> AgentPlatformClient:
    """Use ADC and a regional RAG endpoint; do not default RAG to global.

    A request timeout is not an end-to-end ingestion-job deadline. Provisioning
    and import helpers can poll long-running operations beyond this timeout.
    """
    return AgentPlatformClient(
        project=settings.project,
        location=settings.rag_location,
        http_options=genai_types.HttpOptions(api_version="v1", timeout=60_000),
    )
