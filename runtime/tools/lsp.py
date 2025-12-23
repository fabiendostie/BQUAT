from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Dict, List, Optional

from runtime import config as runtime_config


def encode_message(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    return header + body


def decode_message(stream: IO[bytes]) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            raise EOFError("LSP stream closed")
        if line in {b"\r\n", b"\n"}:
            break
        text = line.decode("utf-8", errors="ignore").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return {}
    body = stream.read(length)
    return json.loads(body.decode("utf-8"))


@dataclass(frozen=True)
class LspServerConfig:
    language: str
    command: List[str]
    root_path: Path
    timeout_seconds: int = 5
    initialization_options: Dict[str, Any] = field(default_factory=dict)


def _node_bin_path(root: Path, name: str) -> Optional[Path]:
    suffixes = [""]
    if os.name == "nt":
        suffixes = [".cmd", ".exe", ""]
    bin_dir = root / "node_modules" / ".bin"
    for suffix in suffixes:
        candidate = bin_dir / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None


def find_lsp_command(language: str, root: Optional[Path] = None) -> Optional[List[str]]:
    base = (root or runtime_config.project_root_from_here()).resolve()
    if language == "python":
        cmd = shutil.which("pyright-langserver")
        if cmd:
            return [cmd, "--stdio"]
        node_cmd = _node_bin_path(base, "pyright-langserver")
        if node_cmd:
            return [str(node_cmd), "--stdio"]
    if language in {"typescript", "javascript"}:
        cmd = shutil.which("typescript-language-server")
        if cmd:
            return [cmd, "--stdio"]
        node_cmd = _node_bin_path(base, "typescript-language-server")
        if node_cmd:
            return [str(node_cmd), "--stdio"]
    return None


def build_server_config(language: str, root: Optional[Path] = None) -> LspServerConfig:
    base = (root or runtime_config.project_root_from_here()).resolve()
    command = find_lsp_command(language, base)
    if not command:
        raise ValueError(f"No LSP server configured for language: {language}")
    return LspServerConfig(language=language, command=command, root_path=base)


class LspClient:
    def __init__(self, config: LspServerConfig) -> None:
        self.config = config
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._next_id = 1

    def start(self) -> None:
        if self._process:
            return
        self._process = subprocess.Popen(
            self.config.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._initialize()

    def _send(self, payload: Dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise RuntimeError("LSP process not started")
        self._process.stdin.write(encode_message(payload))
        self._process.stdin.flush()

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return self._read_response(request_id)

    def _read_response(self, request_id: int) -> Dict[str, Any]:
        if not self._process or not self._process.stdout:
            raise RuntimeError("LSP process not started")
        while True:
            payload = decode_message(self._process.stdout)
            if not payload:
                continue
            if payload.get("id") == request_id:
                return payload

    def _initialize(self) -> None:
        params = {
            "processId": os.getpid(),
            "rootUri": self.config.root_path.as_uri(),
            "capabilities": {},
            "initializationOptions": self.config.initialization_options,
        }
        self._request("initialize", params)
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    def open_document(self, uri: str, language_id: str, text: str) -> None:
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": 1,
                "text": text,
            }
        }
        self._send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": params})

    def hover(self, uri: str, line: int, character: int) -> Dict[str, Any]:
        params = {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}}
        return self._request("textDocument/hover", params)

    def signature_help(self, uri: str, line: int, character: int) -> Dict[str, Any]:
        params = {"textDocument": {"uri": uri}, "position": {"line": line, "character": character}}
        return self._request("textDocument/signatureHelp", params)

    def shutdown(self) -> None:
        if not self._process:
            return
        try:
            self._request("shutdown", {})
            self._send({"jsonrpc": "2.0", "method": "exit", "params": {}})
        finally:
            self._process.terminate()
            self._process = None

    def __enter__(self) -> "LspClient":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()
