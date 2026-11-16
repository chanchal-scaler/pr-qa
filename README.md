# pr-qa

Comment `/qa` on a pull request and an agent tests what the PR claims against the staging
environment where you deployed it, then reports back on the PR.

It reads the PR description and diff, works out the claims, exercises the deployed API and
frontend (with a real browser), looks for bugs around the change, re-checks each finding, and
edits its PR comment with a verdict per claim. Screenshots are attached to the workflow run.

It does not deploy anything. Deploy the PR first, then ask for QA.

## Using it

```
/qa staging                                   # an environment named in the repo config
/qa api=https://<api> fe=https://<frontend>      # or explicit URLs (one is enough)
/qa staging focus="admin-only export"         # optional: what to concentrate on
```

Only people with write access to the repo (owner, member, collaborator) can trigger it.

## Installing it in a repo

1. Copy `examples/caller-workflow.yml` to `.github/workflows/pr-qa.yml`.
2. Add `.github/pr-qa.yml` (see `examples/pr-qa.yml`) and fill in the hosts, the test users and any notes.
3. Merge both to the default branch. Comment-triggered workflows and the config are always read from there, so a PR cannot change the rules it is tested under.
4. Set the secrets (org or repo level):

| Secret | Needed | What it is |
|---|---|---|
| `ANTHROPIC_API_KEY` | one of these two | Console API key; `max_budget_usd` caps spend per run |
| `CLAUDE_CODE_OAUTH_TOKEN` | one of these two | Token from `claude setup-token` (also accepted in `ANTHROPIC_API_KEY`; it is recognised by its `sk-ant-oat` prefix) |
| `QA_JWT_SECRET` | if `auth.strategy: jwt_hs256` | The staging app's JWT signing secret |
| `QA_LOGS_API_KEY` | optional | API key for the log or trace system in the config's `logs` block (for example SigNoz) |
| `QA_LOGS_AWS_ACCESS_KEY_ID`, `QA_LOGS_AWS_SECRET_ACCESS_KEY` | optional | Read-only AWS key, if the logs are in CloudWatch |

A secret or config value left as `replace me` is treated as not filled in: the run stops with a
message naming it (optional log secrets are simply skipped).

## Config reference (`.github/pr-qa.yml`)

| Key | Required | Meaning |
|---|---|---|
| `allowed_hosts` | yes | Host patterns the agent may test. URLs from a comment must be https and match. Never list production. |
| `environments` | no | Named `api_url` / `fe_url` pairs for `/qa <name>`. |
| `auth` | no | Test users per role. `jwt_hs256` mints a short-lived token per role from the claims you list (`sub`, `email`, ...). |
| `fe_auth.cookie` | no | Cookie the frontend reads the access token from. |
| `version_url` | no | Endpoint returning the deployed commit; lets the report confirm it tested the PR head. |
| `logs` | no | Where server logs or traces are and how to query them, passed to the agent as written. |
| `no_touch` | no | Things the agent must not trigger. |
| `notes` | no | Anything else worth knowing about the app. |

## How it is put together

- `.github/workflows/run.yml`: reusable workflow with the permission gate; calls the action.
- `action.yml`: collects the PR and config, mints tokens, runs Claude Code headless with a Playwright browser, posts the report.
- `scripts/prepare.py`: parses the comment, checks URLs against `allowed_hosts`, mints tokens.
- `scripts/summarize.py`: prints the agent's final status in the log and passes its error message to the PR comment when it fails.
- `prompts/qa.md`: the agent's brief and report format.

The agent never runs PR code; it only reads it. It gets ready-made tokens for the configured test
users, not the signing secret, and no GitHub token. The caller workflow passes only the QA
secrets by name, so this workflow never sees a repo's other secrets (deploy keys and the like).

## Before the first run

- Turn off email and WhatsApp sending in the staging config. The agent is told not to trigger them, but staging holds real users' data, so the config is the real guard.
- `run.yml` references the action as `scaler-ai/pr-qa@main`; change it if this repo moves.
- This repo is public so that repos in any organization can use it. Keep internal names, URLs and account details out of it; they belong in each product repo's `.github/pr-qa.yml`.
