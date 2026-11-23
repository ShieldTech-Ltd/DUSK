"""Materialize a fail-closed sandbox Wrangler config from an immutable image."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IMAGE_PLACEHOLDER = "__DUSK_SANDBOX_IMAGE__"
IMAGE = re.compile(
    r"registry\.cloudflare\.com/[0-9a-f]{32}/dusk-scope-sandbox-runtime@sha256:[0-9a-f]{64}"
)


def materialize(template: Path, output: Path, image: str) -> None:
    if not IMAGE.fullmatch(image):
        raise ValueError("A digest-pinned DUSK image in Cloudflare Registry is required")
    if output.exists():
        raise ValueError("Refusing to overwrite an existing deployment config")
    source = template.read_text(encoding="utf-8")
    if source.count(IMAGE_PLACEHOLDER) != 1:
        raise ValueError("Sandbox template must contain exactly one image token")
    rendered = source.replace(IMAGE_PLACEHOLDER, image)
    config = json.loads(rendered)
    if config.get("workers_dev") is not False or config.get("preview_urls") is not False:
        raise ValueError("Sandbox ingress must remain disabled")
    if config.get("routes") != []:
        raise ValueError("Sandbox routes must remain empty")
    output.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=Path("wrangler.sandbox.template.jsonc"))
    parser.add_argument("--output", type=Path, default=Path("wrangler.sandbox.jsonc"))
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    materialize(args.template, args.output, args.image)
    print("Private sandbox configuration materialized")


if __name__ == "__main__":
    main()
