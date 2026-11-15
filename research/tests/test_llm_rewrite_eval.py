"""Controlled transport tests; no external provider or personal transcript."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "llm_rewrite_eval.py"
SPEC = importlib.util.spec_from_file_location("rewrite_eval", SCRIPT)
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)


class RewriteEvaluationTests(unittest.TestCase):
    def test_normalization_and_empty_reference(self):
        self.assertEqual(
            EVAL.score("Tôi muốn uống nước.", "TÔI muốn uống nước!")["wer"], 0
        )
        silent = EVAL.score("", "xin chào")
        self.assertIsNone(silent["wer"])
        self.assertIsNone(silent["cer"])
        self.assertEqual(silent["silence_insertions"], 2)

    def test_auth_reference_isolation_and_quota_fallback(self):
        received = []
        synthetic_key = "local-test-key-not-a-provider-secret"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append((self.headers.get("Authorization"), body))
                response = (
                    {
                        "model": "controlled-test",
                        "choices": [
                            {
                                "message": {"content": "xin chào"},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    if len(received) == 1
                    else {"error": {"code": "QUOTA_TEST"}}
                )
                self.send_response(200 if len(received) == 1 else 429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                records = [
                    {"id": str(i), "scene": str(i), "raw": "xin chao"} for i in range(3)
                ]
                references = {
                    str(i): "REFERENCE_SENTINEL_NOT_FOR_MODEL" for i in range(3)
                }
                (root / "inputs.json").write_text(json.dumps(records), encoding="utf-8")
                (root / "references.json").write_text(
                    json.dumps(references), encoding="utf-8"
                )
                env = dict(os.environ, VIETLIP_TEST_PROVIDER_KEY=synthetic_key)
                subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--inputs",
                        str(root / "inputs.json"),
                        "--references",
                        str(root / "references.json"),
                        "--output",
                        str(root / "out"),
                        "--models",
                        "controlled-test",
                        "--strategies",
                        "conservative",
                        "--api-key-env",
                        "VIETLIP_TEST_PROVIDER_KEY",
                        "--reasoning-effort",
                        "low",
                        "--endpoint",
                        f"http://127.0.0.1:{server.server_port}/chat/completions",
                    ],
                    check=True,
                    capture_output=True,
                    env=env,
                )
                self.assertEqual(len(received), 2)
                self.assertTrue(
                    all(
                        body["reasoning_effort"] == "low" and "reasoning" not in body
                        for _, body in received
                    )
                )
                self.assertTrue(
                    all(header == "Bearer " + synthetic_key for header, _ in received)
                )
                self.assertTrue(
                    all(
                        "REFERENCE_SENTINEL_NOT_FOR_MODEL" not in json.dumps(body)
                        for _, body in received
                    )
                )
                rows_text = (root / "out/responses.jsonl").read_text(encoding="utf-8")
                self.assertNotIn(synthetic_key, rows_text)
                rows = [json.loads(line) for line in rows_text.splitlines()]
                self.assertEqual(rows[0]["corrected"], "xin chào")
                self.assertEqual(rows[1]["corrected"], "xin chao")
                self.assertEqual(rows[2]["corrected"], "xin chao")
                self.assertTrue(rows[2]["not_submitted"])
                policy = json.loads(
                    (root / "out/RESULTS.json").read_text(encoding="utf-8")
                )["results"][1]
                self.assertEqual(policy["attempted_calls"], 2)
                self.assertEqual(policy["failed_calls"], 1)
                self.assertEqual(policy["not_submitted_calls"], 1)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
