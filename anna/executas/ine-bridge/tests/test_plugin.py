import json
import subprocess
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

import ine_plugin as plugin  # noqa: E402


CREDS = {"INE_BASE_URL": "http://ine.test", "INE_USERNAME": "admin", "INE_PASSWORD": "secret"}


def _invoke(tool, arguments=None, credentials=None):
    return plugin.handle_invoke(
        {
            "tool": tool,
            "arguments": arguments or {},
            "context": {"credentials": credentials if credentials is not None else CREDS},
        }
    )


def test_describe_lists_tools_and_credentials():
    manifest = plugin.handle_describe({})
    names = [t["name"] for t in manifest["tools"]]
    assert "list_projects" in names
    assert "generate" in names
    assert "start_auto_write" in names
    cred_names = [c["name"] for c in manifest["credentials"]]
    assert cred_names == ["INE_BASE_URL", "INE_USERNAME", "INE_PASSWORD"]


def test_health_probe():
    assert plugin.handle_health({})["status"] == "ready"


def test_list_projects(monkeypatch):
    calls = []

    def fake_request(method, url, *, headers, body, timeout):
        calls.append((method, url, headers.get("Authorization", ""), body))
        return 200, [{"id": 1, "name": "DEMO"}], "[]"

    monkeypatch.setattr(plugin, "request_json", fake_request)
    result = _invoke("list_projects")
    assert result["success"] is True
    assert result["data"][0]["name"] == "DEMO"
    assert calls[0][0] == "GET"
    assert calls[0][1] == "http://ine.test/api/v1/projects"
    assert calls[0][2].startswith("Basic ")


def test_missing_password():
    result = _invoke("list_projects", credentials={"INE_BASE_URL": "http://ine.test", "INE_USERNAME": "admin"})
    assert result["success"] is False
    assert "INE_PASSWORD" in result["error"]


def test_unknown_tool():
    result = _invoke("not_a_tool")
    assert result["success"] is False
    assert "unknown tool" in result["error"]


def test_story_twin_omits_graphs(monkeypatch):
    twin = {
        "health": {"score": 90, "label": "healthy"},
        "characters": {"nodes": [{"id": 1}], "edges": []},
        "world": {"nodes": [], "edges": []},
        "timeline": {"nodes": [1, 2], "edges": [1]},
    }

    def fake_request(method, url, *, headers, body, timeout):
        return 200, twin, ""

    monkeypatch.setattr(plugin, "request_json", fake_request)
    result = _invoke("get_story_twin", {"project_id": "3"})
    assert result["success"] is True
    assert result["data"]["characters"]["omitted"] is True
    assert result["data"]["characters"]["node_count"] == 1
    assert result["data"]["timeline"]["edge_count"] == 1

    full = _invoke("get_story_twin", {"project_id": 3, "include_graphs": True})
    assert full["data"]["characters"]["nodes"][0]["id"] == 1


def test_generate_payload(monkeypatch):
    captured = {}

    def fake_request(method, url, *, headers, body, timeout):
        captured["url"] = url
        captured["body"] = json.loads(body.decode())
        captured["timeout"] = timeout
        return 200, {"text": "続き", "model": "qwen3:8b"}, ""

    monkeypatch.setattr(plugin, "request_json", fake_request)
    result = _invoke(
        "generate",
        {"project_id": 1, "episode_id": 9, "instruction": "続けて", "mode": "continue"},
    )
    assert result["success"] is True
    assert captured["url"].endswith("/ai/generate")
    assert captured["body"]["episode_id"] == 9
    assert captured["timeout"] == 120


def test_api_error_is_invoke_failure(monkeypatch):
    def fake_request(method, url, *, headers, body, timeout):
        return 404, {"detail": "Project not found"}, ""

    monkeypatch.setattr(plugin, "request_json", fake_request)
    result = _invoke("get_project", {"project_id": 99})
    assert result["success"] is False
    assert "404" in result["error"]


def test_stdio_describe_and_unknown_method():
    proc = subprocess.Popen(
        [sys.executable, str(PLUGIN_DIR / "ine_plugin.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "describe", "id": 1}) + "\n")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "nope", "id": 2}) + "\n")
        proc.stdin.close()
        out = proc.stdout.read().strip().splitlines()
        assert len(out) == 2
        described = json.loads(out[0])
        assert described["id"] == 1
        assert described["result"]["display_name"] == "INE Bridge"
        unknown = json.loads(out[1])
        assert unknown["error"]["code"] == -32601
    finally:
        proc.kill()
        proc.wait(timeout=5)
