# Kaavhi AI Code Review Backend

[![Protected by Gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/gitleaks/gitleaks)
[![Tests](https://github.com/SanthoshSiddegowda/kaavhi-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SanthoshSiddegowda/kaavhi-core/actions/workflows/tests.yml)

This repository contains the open-source core of [Kaavhi](https://kaavhi.com/), an AI-powered code review assistant. Our mission is to help developers write better, safer, and cleaner code without sacrificing control or data privacy.

As part of our commitment to transparency and trust, our core review logic is open source. You can inspect the code to verify that we never store your code and handle your data securely.

## How It Works

1. **Receive diff**: The API accepts a unified diff as an **uploaded file** (`multipart/form-data`).
2. **AI analysis**: The diff is sent to **Google Gemini** using the official [`google-genai`](https://googleapis.github.io/python-genai/) SDK (async). The model returns **structured JSON** constrained by Pydantic schemas: an **AI Pull Request Summary** plus **line-level comments**.
3. **Return JSON**: The response includes `summary` (overview, key changes, review focus) and `comments` (issues and suggestions with severity, confidence, and code suggestions).

The review model is set by the `GEMINI_MODEL` environment variable (see `app/config/app.py`); it defaults to `gemini-3.5-flash-lite`. Set it in `.env` to match your API access — no code change needed.

If `NVIDIA_API_KEY` is configured, NVIDIA (qwen) is used as a **fallback** when Gemini fails or returns nothing usable. Gemini is always tried first.

Beyond review, the service also exposes regression-origin detection (`/detect-origin`), Bitbucket cross-repo PR linking (`/pr/cross-repo`), and a Bugzilla regression query (`/bugzilla/regression-bugs`).

## Getting Started

### Prerequisites

- Python 3.9+
- A [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key)

### Installation

1. **Clone the repository:**

   ```sh
   git clone git@github.com:SanthoshSiddegowda/kaavhi-core.git
   cd kaavhi-core
   ```

2. **Create a virtual environment and install dependencies:**

   ```sh
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file in the project root:

   ```env
   # Required
   GEMINI_API_KEY="your-gemini-api-key"

   # Optional — review model (default: gemini-3.5-flash-lite)
   GEMINI_MODEL="gemini-3.5-flash-lite"

   # Optional — NVIDIA fallback, used only when Gemini fails
   NVIDIA_API_KEY=""
   NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"
   NVIDIA_MODEL="qwen/qwen3.5-397b-a17b"

   # Optional — required only for /bugzilla/regression-bugs
   BUGZILLA_API_KEY=""
   ```

### Running the Server

```sh
uvicorn app.main:app --reload
```

The server listens at `http://localhost:8000`.

## API Usage

### `POST /review/diff`

Accepts a **file** field containing the diff text (not a JSON body).

| Item | Value |
|------|--------|
| Method | `POST` |
| Content-Type | `multipart/form-data` |
| Field | `file` — the `.diff` / patch file |

**Example (curl):**

```sh
curl -X POST "http://localhost:8000/review/diff" \
  -F "file=@./my-changes.diff"
```

**Success response (`200 OK`)**

```json
{
  "comments": [
    {
      "id": "1",
      "type": "suggestion",
      "severity": "low",
      "line": 3,
      "code": "+ const newVar = 2;",
      "comment": "Variable renamed; ensure all references are updated.",
      "suggestion": "const newVar = 2;",
      "confidence": 90,
      "filePath": "src/file.js"
    }
  ],
  "summary": {
    "overview": "Short plain-language description of what the PR changes and why it matters.",
    "keyChanges": [
      "Renamed a variable in `src/file.js` for clarity."
    ],
    "focus": [
      "Double-check all imports and references to the old name."
    ]
  }
}
```

- **`summary.overview`** — Simple PR-level context for reviewers (especially when there is no PR description).
- **`summary.keyChanges`** — Factual bullets of what changed.
- **`summary.focus`** — Areas worth a deeper review (risk, contracts, tricky logic, etc.).

Each comment’s **`filePath`** should be repo-relative, taken from the `+++ b/path/to/file` header in the diff (the path after `b/`).

### `POST /detect-origin`

Best-effort regression blame: given a bug, the diff that fixed it, and candidate commits that
previously touched the same files, returns the commit most likely to have introduced the regression.

```sh
curl -X POST "http://localhost:8000/detect-origin" \
  -H "Content-Type: application/json" \
  -d '{
        "bug_summary": "Totals round down on the invoice page",
        "fix_ref": "https://bitbucket.org/acme/billing/pull-requests/42",
        "fix_diff": "--- a/billing.py\n+++ b/billing.py\n-    return int(total)\n+    return round(total, 2)\n",
        "candidate_commits": [
          {"hash": "9f2c1ab", "author": "dev@acme.com", "date": "2026-02-11", "message": "speed up totals", "files": ["billing.py"]}
        ]
      }'
```

Returns `introduced_commit`, `introduced_by`, `confidence` (0–100), `reasoning`, `cause_summary`,
and `fix_summary`. Every field is best-effort and comes back empty when the signal is too weak.

### `POST /pr/cross-repo`

Finds every open PR sharing the source branch of `pr_url` across the workspace and cross-links the
group by appending `🔗 Cross-repo PR: <url>` to each title. Idempotent — urls already present are
not appended again.

```sh
curl -X POST "http://localhost:8000/pr/cross-repo" \
  -H "Content-Type: application/json" \
  -d '{
        "pr_url": "https://bitbucket.org/acme/billing/pull-requests/42",
        "bitbucket_token": "your-bitbucket-access-token",
        "dry_run": true
      }'
```

`dry_run` **defaults to `true`** so a caller that omits it cannot rewrite PR titles by accident.
Pass `false` to apply. The response lists each group member with its `old_title`, `new_title`,
`changed`, and `updated`.

### `POST /bugzilla/regression-bugs`

Queries Bugzilla for regression bugs in a version over a date range. Requires `BUGZILLA_API_KEY`.

```sh
curl -X POST "http://localhost:8000/bugzilla/regression-bugs" \
  -H "Content-Type: application/json" \
  -d '{"version": "24.10", "chfieldfrom": "2026-01-01", "chfieldto": "2026-03-31"}'
```

### `GET /`

Health check — returns `{ "status": "ok" }`.

### `GET /ip`

Returns the server's outbound IP (via `api.ipify.org`) — useful for allowlisting Kaavhi with a
self-hosted Bitbucket or Bugzilla instance.

## CORS

Custom CORS middleware allows:

- `http://localhost` and `http://127.0.0.1` on any port (local frontend)
- `https://` and `http://` origins on `kaavhi.com` and its subdomains
- `https://` origins on `bitbucket.org` and its subdomains

See `app/middleware/cors.py` to adjust allowed origins.

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Project structure

- `app/main.py` — FastAPI app, CORS, router mount
- `app/api/v1/` — endpoints: `review.py`, `detect_origin.py`, `pr.py`, `bugzilla.py`
- `app/integrations/gemini.py` — Gemini client and structured output
- `app/integrations/nvidia.py` — NVIDIA (qwen) fallback provider
- `app/integrations/review_prompt.py` — shared review instructions and diff line annotation
- `app/integrations/bitbucket.py` — Bitbucket API client (cross-repo PR linking)
- `app/models/` — Pydantic models (`ReviewResponse`, `PullRequestSummary`, `ReviewComment`, detect-origin)
- `app/services/` — Review and detect-origin orchestration
- `app/middleware/` — CORS middleware
- `app/config/` — Settings (`GEMINI_API_KEY`, `GEMINI_MODEL`, `NVIDIA_*`, `BUGZILLA_API_KEY`)
- `requirements.txt` — Dependencies (`fastapi`, `google-genai`, `python-multipart`, etc.)
- `tests/` — `pytest` suite

## Releases

See [GitHub Releases](https://github.com/SanthoshSiddegowda/kaavhi-core/releases) for version notes (latest: **v1.3.0** — line-annotated diffs for accurate inline comments, a tighter review prompt, `/detect-origin`, and `/pr/cross-repo`).
