# Kaavhi AI Code Review Backend

[![Protected by Gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/gitleaks/gitleaks)
[![Tests](https://github.com/SanthoshSiddegowda/kaavhi-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SanthoshSiddegowda/kaavhi-core/actions/workflows/tests.yml)

This repository contains the open-source core of [Kaavhi](https://kaavhi.com/), an AI-powered code review assistant. Our mission is to help developers write better, safer, and cleaner code without sacrificing control or data privacy.

As part of our commitment to transparency and trust, our core review logic is open source. You can inspect the code to verify that we never store your code and handle your data securely.

## How It Works

1. **Receive diff**: The API accepts a unified diff as an **uploaded file** (`multipart/form-data`).
2. **AI analysis**: The diff is sent to **Google Gemini** using the official [`google-genai`](https://googleapis.github.io/python-genai/) SDK (async). The model returns **structured JSON** constrained by Pydantic schemas: an **AI Pull Request Summary** plus **line-level comments**.
3. **Return JSON**: The response includes `summary` (overview, key changes, review focus) and `comments` (issues and suggestions with severity, confidence, and code suggestions).

Default model id is configured in `app/integrations/gemini.py` (currently `gemini-3-flash-preview`). You can change it there to match your API access.

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
   GEMINI_API_KEY="your-gemini-api-key"
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

### `GET /`

Health check — returns `{ "status": "ok" }`.

## CORS

Custom CORS middleware allows:

- `http://localhost:8080` (local frontend)
- `https://` and `http://` origins on `kaavhi.com` and its subdomains

See `app/middleware/cors.py` to adjust allowed origins.

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Project structure

- `app/main.py` — FastAPI app, CORS, router mount
- `app/api/v1/review.py` — `/review/diff` endpoint
- `app/integrations/gemini.py` — Gemini client, prompt, structured output
- `app/models/review.py` — Pydantic models (`ReviewResponse`, `PullRequestSummary`, `ReviewComment`)
- `app/services/review_service.py` — Review orchestration
- `app/middleware/` — CORS middleware
- `app/config/` — Settings (e.g. `GEMINI_API_KEY`)
- `requirements.txt` — Dependencies (`fastapi`, `google-genai`, `python-multipart`, etc.)
- `tests/` — `pytest` suite

## Releases

See [GitHub Releases](https://github.com/SanthoshSiddegowda/kaavhi-core/releases) for version notes (e.g. **v1.2.0**: summary + focus, structured Gemini output, middleware layout).
