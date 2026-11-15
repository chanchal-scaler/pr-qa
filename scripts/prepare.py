"""Turn the /qa comment + repo config into the inputs the agent needs.

Usage: prepare.py <config.json> <out_dir>
Env:   COMMENT_BODY (the PR comment), QA_JWT_SECRET (only for auth.strategy jwt_hs256)

Writes <out_dir>/context.json and <out_dir>/tokens.json.
On a user-facing problem, writes <out_dir>/error.txt and exits 1.
"""

import base64
import fnmatch
import hashlib
import hmac
import json
import os
import secrets
import shlex
import sys
import time
from urllib.parse import urlparse


class UserError(Exception):
    pass


def parse_comment(body):
    """'/qa staging fe=https://x focus="admin export"' -> (env_name, {key: value})."""
    try:
        words = shlex.split(body.strip())
    except ValueError as exc:
        raise UserError(f"Could not parse the comment: {exc}") from exc
    env_name, options = None, {}
    for word in words[1:]:
        if "=" in word:
            key, value = word.split("=", 1)
            options[key.strip().lower()] = value.strip()
        elif env_name is None:
            env_name = word
    return env_name, options


def check_url(name, url, allowed_hosts):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UserError(f"`{name}` must be an https URL, got `{url}`.")
    if not any(fnmatch.fnmatch(parsed.hostname, pattern) for pattern in allowed_hosts):
        raise UserError(
            f"`{name}` host `{parsed.hostname}` is not in `allowed_hosts` in .github/pr-qa.yml."
        )
    return url.rstrip("/")


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def mint_hs256(claims, secret):
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url(signature)}"


def mint_tokens(auth):
    if not auth:
        return {}
    if auth.get("strategy") != "jwt_hs256":
        raise UserError(f"Unsupported auth.strategy `{auth.get('strategy')}` (supported: jwt_hs256).")
    secret = os.environ.get("QA_JWT_SECRET")
    if not secret:
        raise UserError("auth.strategy is jwt_hs256 but the `QA_JWT_SECRET` secret is not set.")
    now = int(time.time())
    lifetime = int(auth.get("lifetime_minutes", 120)) * 60
    tokens = {}
    for role, user in (auth.get("roles") or {}).items():
        claims = {**user, "iat": now, "exp": now + lifetime, "jti": secrets.token_hex(8)}
        if auth.get("audience"):
            claims["aud"] = auth["audience"]
        tokens[role] = {"email": user.get("email"), "token": mint_hs256(claims, secret)}
    return tokens


def build(config, comment_body):
    allowed_hosts = config.get("allowed_hosts") or []
    if not allowed_hosts:
        raise UserError("`allowed_hosts` is missing in .github/pr-qa.yml.")

    env_name, options = parse_comment(comment_body)
    urls = {}
    if env_name:
        environments = config.get("environments") or {}
        if env_name not in environments:
            known = ", ".join(sorted(environments)) or "none configured"
            raise UserError(f"Unknown environment `{env_name}` (known: {known}).")
        urls.update(environments[env_name])
    for option, key in (("api", "api_url"), ("fe", "fe_url")):
        if option in options:
            urls[key] = options[option]
    if not urls.get("api_url") and not urls.get("fe_url"):
        raise UserError(
            "Tell me where the PR is deployed: `/qa <environment>` or "
            "`/qa api=<url> fe=<url>` (one of the two URLs is enough)."
        )

    context = {
        "environment": env_name,
        "api_url": check_url("api", urls["api_url"], allowed_hosts) if urls.get("api_url") else None,
        "fe_url": check_url("fe", urls["fe_url"], allowed_hosts) if urls.get("fe_url") else None,
        "allowed_hosts": allowed_hosts,
        "focus": options.get("focus"),
        "fe_auth": config.get("fe_auth"),
        "version_url": config.get("version_url"),
        "logs": config.get("logs"),
        "no_touch": config.get("no_touch") or [],
        "notes": config.get("notes"),
    }
    return context, mint_tokens(config.get("auth"))


def main():
    config_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    try:
        with open(config_path) as handle:
            config = json.load(handle) or {}
        context, tokens = build(config, os.environ.get("COMMENT_BODY", ""))
    except UserError as exc:
        with open(os.path.join(out_dir, "error.txt"), "w") as handle:
            handle.write(str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 1
    with open(os.path.join(out_dir, "context.json"), "w") as handle:
        json.dump(context, handle, indent=2)
    with open(os.path.join(out_dir, "tokens.json"), "w") as handle:
        json.dump(tokens, handle, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
