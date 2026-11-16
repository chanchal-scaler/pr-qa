"""Print a short summary of the agent's final result; record its message if it failed.

Usage: summarize.py <agent-result.json> <error-out.txt>

The agent CLI reports failures such as a rejected key or a reached spend cap inside its
JSON result on stdout, so without this the workflow log shows only "exit code 1".
"""

import json
import sys


def load_result(path):
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if isinstance(data, list):  # verbose output is a list of events; the result is the last one
        results = [item for item in data if isinstance(item, dict) and item.get("type") == "result"]
        data = results[-1] if results else None
    return data if isinstance(data, dict) else None


def main():
    result_path, error_path = sys.argv[1], sys.argv[2]
    result = load_result(result_path)
    if result is None:
        failed, message = True, "The agent produced no readable result."
    else:
        failed = bool(result.get("is_error")) or result.get("subtype") not in (None, "success")
        message = str(result.get("result") or result.get("subtype") or "").strip()
        print(f"turns={result.get('num_turns')} cost_usd={result.get('total_cost_usd')} failed={failed}")
    print(message[:1000])
    if failed:
        with open(error_path, "w") as handle:
            handle.write(message[:500] or "The agent stopped without a message.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
