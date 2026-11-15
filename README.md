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
| `CLAUDE_CODE_OAUTH_TOKEN` | one of these two | Token from `claude setup-token` |
| `QA_JWT_SECRET` | if `auth.strategy: jwt_hs256` | The staging app's JWT signing secret |
| `QA_LOGS_AWS_ACCESS_KEY_ID`, `QA_LOGS_AWS_SECRET_ACCESS_KEY` | optional | Read-only key for staging logs |

## Config reference (`.github/pr-qa.yml`)

| Key | Required | Meaning |
|---|---|---|
| `allowed_hosts` | yes | Host patterns the agent may test. URLs from a comment must be https and match. Never list production. |
| `environments` | no | Named `api_url` / `fe_url` pairs for `/qa <name>`. |
| `auth` | no | Test users per role. `jwt_hs256` mints a short-lived token per role from the claims you list (`sub`, `email`, ...). |
| `fe_auth.cookie` | no | Cookie the frontend reads the access token from. |
| `version_url` | no | Endpoint returning the deployed commit; lets the report confirm it tested the PR head. |
| `logs` | no | Where server logs are, passed to the agent as a hint. |
| `no_touch` | no | Things the agent must not trigger. |
| `notes` | no | Anything else worth knowing about the app. |

## How it is put together

- `.github/workflows/run.yml`: reusable workflow with the permission gate; calls the action.
- `action.yml`: collects the PR and config, mints tokens, runs Claude Code headless with a Playwright browser, posts the report.
- `scripts/prepare.py`: parses the comment, checks URLs against `allowed_hosts`, mints tokens.
- `prompts/qa.md`: the agent's brief and report format.

The agent never runs PR code; it only reads it. It gets ready-made tokens for the configured test
users, not the signing secret, and no GitHub token.

## Before the first run

- Turn off email and WhatsApp sending in the staging config. The agent is told not to trigger them, but staging holds real users' data, so the config is the real guard.
- `run.yml` references the action as `chanchal-scaler/pr-qa@main`; change it if this repo moves.
- If your organization restricts which actions may run, allow `chanchal-scaler/pr-qa`.
