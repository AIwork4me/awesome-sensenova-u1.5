"""Tests for the optional OpenAI-compatible glm_api judge backend."""
import base64
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from fixtures import GOOD_VERDICT
from schemas import validate_verdict
import run_judge_api as rja


def _spawn_mock_server(auth_ok="Bearer k-123", status=200, content=None, raw=None):
    """In-thread OpenAI-compatible mock. Returns (server, base_url, captured)."""
    captured = {}

    class H(BaseHTTPRequestHandler):
        def _reply(self, code, payload):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            captured["auth"] = self.headers.get("Authorization")
            try:
                captured["body"] = json.loads(self.rfile.read(n))
            except ValueError:
                captured["body"] = None
            if captured["auth"] != auth_ok:
                self._reply(401, b'{"error":{"message":"invalid api key"}}')
            elif raw is not None:
                self._reply(status, raw)
            else:
                body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
                self._reply(status, body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/api/paas/v4/chat/completions"
    return srv, url, captured


def _entry(tmp_path, image=b"\x89PNG\r\n\x1a\nrest"):
    img = tmp_path / "im.png"
    img.write_bytes(image)
    pr = tmp_path / "p.txt"
    pr.write_text("a poster", encoding="utf-8")
    return {"image_path": str(img), "prompt_path": str(pr),
            "verdict_path": str(tmp_path / "v.json")}


def test_api_backend_normalizes(monkeypatch, tmp_path):
    content = "```json\n" + json.dumps(GOOD_VERDICT) + "\n```"
    srv, url, cap = _spawn_mock_server(content=content)
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    assert rc == 0
    assert cap["auth"] == "Bearer k-123"
    vp = tmp_path / "v.json"
    saved = json.loads(vp.read_text(encoding="utf-8"))
    assert saved["scores"]["quality"] == 8
    assert validate_verdict(saved) == []  # written verdict is schema-clean for collect
    body = cap["body"]
    assert body["model"] == "glm-4.6v" and body["temperature"] == 0
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == rja.SYSTEM
    user = body["messages"][1]["content"]
    assert user[0]["type"] == "text" and "a poster" in user[0]["text"]
    assert "JSON" in user[0]["text"]  # reply-with-only-json instruction appended
    expected_b64 = base64.standard_b64encode(b"\x89PNG\r\n\x1a\nrest").decode("ascii")
    assert user[1] == {"type": "image_url",
                       "image_url": {"url": f"data:image/png;base64,{expected_b64}"}}


def test_missing_key_fails_fast(monkeypatch, capsys):
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    assert rja.run_one({}) == 2
    assert "GLM_API_KEY" in capsys.readouterr().err


def test_model_and_env_read_at_call_time(monkeypatch, tmp_path):
    content = "```json\n" + json.dumps(GOOD_VERDICT) + "\n```"
    srv, url, cap = _spawn_mock_server(content=content)
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    monkeypatch.setenv("GLM_VLM_MODEL", "my-vlm-x")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    assert rc == 0 and cap["body"]["model"] == "my-vlm-x"


def test_http_401_diagnosed(monkeypatch, tmp_path, capsys):
    srv, url, _cap = _spawn_mock_server()  # wrong key below -> server rejects 401
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "wrong-key")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    err = capsys.readouterr().err
    assert rc == 3 and not (tmp_path / "v.json").exists()
    assert "401" in err and "GLM_API_KEY" in err
    assert "404" in err and "timeout" in err.lower()  # three-class reference present


def test_http_404_diagnosed(monkeypatch, tmp_path, capsys):
    srv, url, _cap = _spawn_mock_server(status=404,
                                        raw=b'{"error":{"message":"model not found"}}')
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    err = capsys.readouterr().err
    assert rc == 3 and not (tmp_path / "v.json").exists()
    assert "404" in err and "GLM_API_BASE" in err


def test_unreachable_endpoint_diagnosed(monkeypatch, tmp_path, capsys):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    port = blocker.getsockname()[1]  # bound but never listening -> refused
    monkeypatch.setenv("GLM_API_BASE", f"http://127.0.0.1:{port}/chat/completions")
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    blocker.close()
    err = capsys.readouterr().err
    assert rc == 3 and not (tmp_path / "v.json").exists()
    assert "unreachable" in err.lower() or "connection" in err.lower()


def test_timeout_diagnosed(monkeypatch, tmp_path, capsys):
    def boom(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(rja.urllib.request, "urlopen", boom)
    monkeypatch.delenv("GLM_API_BASE", raising=False)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    rc = rja.run_one(_entry(tmp_path))
    err = capsys.readouterr().err
    assert rc == 3 and "timeout" in err.lower()


def test_http_200_non_json_body_diagnosed(monkeypatch, tmp_path, capsys):
    srv, url, _cap = _spawn_mock_server(raw=b"<html>502 Bad Gateway</html>")
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    srv.server_close()
    err = capsys.readouterr().err
    assert rc == 3 and not (tmp_path / "v.json").exists()
    assert "non-JSON" in err


def test_null_content_rc4_no_crash(monkeypatch, tmp_path, capsys):
    srv, url, _cap = _spawn_mock_server(content=None)  # choices[0].message.content: null
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    srv.server_close()
    assert rc == 4 and not (tmp_path / "v.json").exists()


@pytest.mark.parametrize("content", [
    "```json\n{\"scores\": {}}\n```",   # fenced JSON that fails the schema
    "sorry, I cannot judge this image",  # no JSON object at all
])
def test_invalid_or_missing_json_rc4_no_file(monkeypatch, tmp_path, capsys, content):
    srv, url, _cap = _spawn_mock_server(content=content)
    monkeypatch.setenv("GLM_API_BASE", url)
    monkeypatch.setenv("GLM_API_KEY", "k-123")
    entry = _entry(tmp_path)
    rc = rja.run_one(entry)
    srv.shutdown()
    srv.server_close()
    srv.server_close()
    err = capsys.readouterr().err
    assert rc == 4 and not (tmp_path / "v.json").exists()
    assert "scores.quality" in err or "JSON" in err
