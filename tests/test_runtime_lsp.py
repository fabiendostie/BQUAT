import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.tools import lsp  # noqa: E402


class RuntimeLspTests(unittest.TestCase):
    def test_encode_decode_round_trip(self) -> None:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        data = lsp.encode_message(payload)
        decoded = lsp.decode_message(io.BytesIO(data))
        self.assertEqual(decoded, payload)

    def test_find_pyright_command(self) -> None:
        cmd = lsp.find_lsp_command("python", root=ROOT)
        if not cmd:
            self.skipTest("pyright-langserver not available")
        self.assertIn("pyright-langserver", cmd[0])

    def test_unknown_language(self) -> None:
        with self.assertRaises(ValueError):
            lsp.build_server_config("unknown", root=ROOT)


if __name__ == "__main__":
    unittest.main()
