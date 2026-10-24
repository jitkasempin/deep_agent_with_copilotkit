"""Typed alias for Google's lazy public Client export.

SDK 2.5.0 exposes agentplatform.Client through module __getattr__; Pyright
infers ModuleType | Any. Use its concrete class for STATIC analysis only,
while the running example uses the documented public import. Recheck this
small shim when upgrading; it is not a runtime import of a private module.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentplatform._genai.client import Client as AgentPlatformClient
else:
    from agentplatform import Client as AgentPlatformClient
