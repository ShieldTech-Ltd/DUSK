"""Run the real Python policy server behind an owned local Workers test bridge."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import threading
from http.server import HTTPServer
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", default="node")
    parser.add_argument("--vitest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    # These are test-only values in this child process. Never use live secrets.
    os.environ["DUSK_SIGNING_KEY"] = ""
    os.environ["DUSK_ALLOW_EPHEMERAL_KEY"] = "1"
    os.environ["DUSK_SCOPE_CONTEXT_KEY"] = "native-test-context-key-at-least-32-characters"
    spec = importlib.util.spec_from_file_location(
        "native_test_server", root / "workers/dusk-runtime/runtime_server.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the native policy server")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    server = HTTPServer(("127.0.0.1", 0), runtime._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    child_env = {
        **os.environ,
        "DUSK_NATIVE_TEST_URL": f"http://127.0.0.1:{server.server_port}",
        "DUSK_GATEWAY_TOKEN": "native-test-token",
    }
    try:
        return subprocess.run(  # noqa: S603 - trusted CLI paths, argv array, no shell
            [
                args.node,
                args.vitest or str(root / "node_modules/vitest/vitest.mjs"),
                "run",
                "--config",
                "workers/dusk-gateway/vitest.native.config.ts",
            ],
            cwd=root,
            env=child_env,
            timeout=120,
            check=False,
        ).returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
