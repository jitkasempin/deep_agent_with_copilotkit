import asyncio
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
provider = SimpleNamespace(fetch_myfxbook=AsyncMock(return_value=[]))
with patch.dict(sys.modules, {"tools.providers.myfxbook": provider}), \
        patch("toolbox_langchain.ToolboxClient") as toolbox:
    toolbox.return_value.load_toolset.return_value = []
    server = importlib.import_module("backend.server")


def make_tool(name):
    return StructuredTool.from_function(lambda: "ok", name=name, description=name)


class MCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "SCRAPLING_MCP_URL": "https://example.test/mcp",
            "SCRAPLING_MCP_AUTH_TOKEN": "",
        }))

    async def test_auth_allowlist_and_namespace(self):
        with patch.object(server, "MultiServerMCPClient") as client:
            client.return_value.get_tools = AsyncMock(return_value=[
                make_tool("fetch"), make_tool("list_sessions"), make_tool("new_tool"),
            ])
            with patch.dict(os.environ, {"SCRAPLING_MCP_AUTH_TOKEN": "test-token"}):
                tools = await server._load_mcp_tools()
            self.assertEqual([t.name for t in tools], [
                "scrapling__fetch", "scrapling__list_sessions",
            ])
            connection = client.call_args.args[0]["scrapling"]
            self.assertEqual(connection["headers"], {"Authorization": "Bearer test-token"})
            self.assertEqual(connection["timeout"].total_seconds(), 120)
            client.return_value.get_tools.assert_awaited_once_with(server_name="scrapling")

    async def test_env_file_resolves_from_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("SCRAPLING_MCP_URL=https://from-env.test/mcp\n")
            with patch.dict(os.environ), patch.object(server, "_LESSON_ROOT", root):
                os.environ.pop("SCRAPLING_MCP_URL", None)
                with patch.object(server, "MultiServerMCPClient") as client:
                    client.return_value.get_tools = AsyncMock(return_value=[make_tool("fetch")])
                    await server._load_mcp_tools()
                    connection = client.call_args.args[0]["scrapling"]
                    self.assertEqual(connection["url"], "https://from-env.test/mcp")
                    self.assertNotIn("headers", connection)

    async def test_missing_url_fails(self):
        with patch.dict(os.environ, {"SCRAPLING_MCP_URL": " "}), \
                self.assertRaisesRegex(ValueError, "SCRAPLING_MCP_URL"):
            await server._load_mcp_tools()

    async def test_discovery_failure_propagates(self):
        with patch.object(server, "MultiServerMCPClient") as client:
            client.return_value.get_tools = AsyncMock(side_effect=ConnectionError("unavailable"))
            with self.assertRaises(ConnectionError):
                await server._build_graph()

    async def test_no_allowed_tools_fails(self):
        with patch.object(server, "MultiServerMCPClient") as client:
            client.return_value.get_tools = AsyncMock(return_value=[make_tool("new_tool")])
            with self.assertRaisesRegex(RuntimeError, "no allowlisted tools"):
                await server._load_mcp_tools()

    async def test_tool_deadline(self):
        with patch.object(server, "MCP_TOOL_TIMEOUT", 0.01), self.assertRaises(TimeoutError):
            await server._mcp_tool_timeout(None, lambda _: asyncio.sleep(10))

    async def test_graph_keeps_existing_tools(self):
        mcp_tool, bq_tool = make_tool("scrapling__fetch"), make_tool("bigquery")
        with patch.object(server, "_load_mcp_tools", AsyncMock(return_value=[mcp_tool])), \
                patch.object(server, "bigquery_insert_tool", [bq_tool]), \
                patch.object(server, "ChatGoogleGenerativeAI"), \
                patch.object(server, "create_deep_agent") as create:
            graph = await server._build_graph()
            self.assertIs(graph, create.return_value)
            self.assertEqual(create.call_args.kwargs["tools"], [
                server.get_eurusd_sentiment, server.web_search, bq_tool, mcp_tool,
            ])

    async def test_real_mcp_transport_and_prefixed_invocation(self):
        mcp = FastMCP("test", stateless_http=True, json_response=True)
        mcp.add_tool(lambda: "sessions-ok", name="list_sessions")
        mcp.add_tool(lambda: "excluded", name="unapproved_tool")
        app = mcp.streamable_http_app()

        def make_client(connections, **kwargs):
            connections["scrapling"]["httpx_client_factory"] = lambda **options: httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), **options,
            )
            return MultiServerMCPClient(connections, **kwargs)

        async with mcp.session_manager.run():
            with patch.dict(os.environ, {"SCRAPLING_MCP_URL": "http://localhost:8000/mcp"}), \
                    patch.object(server, "MultiServerMCPClient", side_effect=make_client):
                tools = await server._load_mcp_tools()
                self.assertEqual([t.name for t in tools], ["scrapling__list_sessions"])
                result = await tools[0].ainvoke({})
                self.assertEqual(result[0]["type"], "text")
                self.assertEqual(result[0]["text"], "sessions-ok")


class StartupTests(unittest.TestCase):
    def test_synchronous_launcher_registers_endpoint_in_lifespan(self):
        with patch("helper.start_server") as start, \
                patch.object(server, "_build_graph", AsyncMock(return_value=object())) as build, \
                patch.object(server, "LangGraphAGUIAgent") as agent, \
                patch.object(server, "add_langgraph_fastapi_endpoint") as endpoint:
            server.start_backend(port=8123)
            app = start.call_args.args[0]
            build.assert_not_awaited()
            with TestClient(app):
                build.assert_awaited_once()
                endpoint.assert_called_once_with(app=app, agent=agent.return_value, path="/")
            self.assertEqual(start.call_args.kwargs["port"], 8123)

    def test_startup_fails_when_mcp_is_unavailable(self):
        with patch("helper.start_server") as start, \
                patch.object(server, "_build_graph", AsyncMock(side_effect=ConnectionError("MCP unavailable"))):
            server.start_backend()
            with self.assertRaises(ConnectionError), TestClient(start.call_args.args[0]):
                pass


if __name__ == "__main__":
    unittest.main()
