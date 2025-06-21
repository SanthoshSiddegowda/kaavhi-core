# Kaavhi AI Code Review Backend

[![Protected by Gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/gitleaks/gitleaks)

This repository contains the open-source core of [Kaavhi](https://kaavhi.com/), an AI-powered code review assistant. Our mission is to help developers write better, safer, and cleaner code without sacrificing control or data privacy.

As part of our commitment to transparency and trust, our core review logic is open source. You can inspect the code to verify that we never store your code and handle your data securely.

## How It Works

The backend provides a single API endpoint that accepts a code diff and returns a structured JSON object containing AI-generated review comments.

1.  **Receive Diff**: The API receives a code diff as a string.
2.  **AI Analysis**: The diff is sent to Google's Gemini 2.5 Pro model with a detailed prompt instructing it to act as an expert code reviewer.
3.  **Return JSON**: The model's response is parsed and returned as a structured JSON array of review comments.

## Getting Started

### Prerequisites

*   Python 3.9+
*   A [Gemini API Key](https://ai.google.dev/gemini-api/docs/api-key)

### Installation

1.  **Clone the repository:**
    ```sh
    git clone git@github.com:SanthoshSiddegowda/kaavhi-core.git
    cd kaavhi-core
    ```

2.  **Create a virtual environment and install dependencies:**
    ```sh
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Set up your environment variables:**
    Create a `.env` file in the project root and add your Gemini API key:
    ```
    GEMINI_API_KEY="your-gemini-api-key"
    ```

### Running the Server

Use `uvicorn` to run the FastAPI server locally:

```sh
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`.

## API Usage

### Endpoint: `/review/diff`

*   **Method**: `POST`
*   **Body**:

    ```json
    {
      "diff": "--- a/file.js\n+++ b/file.js\n@@ -1,3 +1,3 @@\n- const oldVar = 1;\n+ const newVar = 2;"
    }
    ```

*   **Success Response (200 OK)**:

    A JSON object containing an array of review comments.
    ```json
    {
      "comments": [
        {
          "id": "1",
          "type": "suggestion",
          "severity": "low",
          "line": 3,
          "code": "+ const newVar = 2;",
          "comment": "Variable name changed, ensure this is updated across all usages.",
          "suggestion": "N/A",
          "confidence": 90,
          "filePath": "b/file.js"
        }
      ]
    }
    ```

## Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to get started.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Project Structure

- `app/` - Main application code
  - `main.py` - FastAPI app and routes
  - `__init__.py` - Makes app a package
- `requirements.txt` - Python dependencies

## API
- `GET /` - Health check endpoint, returns `{ "status": "ok" }` 