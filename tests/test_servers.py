import importlib.util
import os
import sys
import types
import anyio
import json
import threading
import http.client
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python-sdk" / "src"))

# Stubs for optional deps so recipe-extractor can be imported
sys.modules.setdefault("yt_dlp", types.ModuleType("yt_dlp"))
sys.modules.setdefault("openai", types.ModuleType("openai"))

os.environ.setdefault("OPENAI_API_KEY", "test-key")

spec = importlib.util.spec_from_file_location(
    "recipe_extractor", Path(__file__).resolve().parents[1] / "recipe-extractor.py"
)
recipe_extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe_extractor)


def test_rest_server_basic():
    results = []

    def fake_extract(url, language, fmt):
        results.append((url, language, fmt))
        return "{}" if fmt == "json" else "# ok"

    recipe_extractor.extract_recipe = fake_extract

    server = recipe_extractor.run_rest_server("127.0.0.1", 0, serve_forever=False)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/extract?url=http://v")
        resp = conn.getresponse()
        body = resp.read().decode()
        assert resp.status == 200
        assert body == "{}"
        assert results == [("http://v", "english", "json")]
    finally:
        server.shutdown()
        thread.join()


def test_mcp_server_basic():
    results = []

    def fake_extract(url, language, fmt):
        results.append((url, language, fmt))
        return "done"

    recipe_extractor.extract_recipe = fake_extract

    mcp = recipe_extractor.run_mcp_server(serve_forever=False)

    async def run():
        from mcp.shared.memory import (
            create_connected_server_and_client_session as client_session,
        )

        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("extract_recipe", {"url": "http://v"})
            assert len(result.content) == 1
            assert result.content[0].text == "done"

    anyio.run(run)
    assert results == [("http://v", "english", "json")]

