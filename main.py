#!/usr/bin/env python3
"""
Literature Search main entry.

- Without --query: start Flask server.
- With --query: run one-shot literature search via qwen-plus + Google Scholar.
"""

import argparse
import json

from platform.google_scholar import handle_literature_query
from server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Literature Search Service")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host")
    parser.add_argument("--port", type=int, default=5001, help="Server port")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # One-shot literature search mode
    parser.add_argument("--query", type=str, help="User literature search query")
    parser.add_argument("--num", type=int, default=10, help="Max results for Scholar search")
    parser.add_argument("--model", type=str, default="qwen-plus", help="LLM model name")

    args = parser.parse_args()

    if args.query:
        result = handle_literature_query(
            args.query,
            model=args.model,
            num=args.num,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    app = create_app()
    print(f"Service starting at: {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print("Press Ctrl+C to stop")

    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nService stopped")


if __name__ == "__main__":
    main()

