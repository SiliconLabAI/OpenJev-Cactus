# Needle FastAPI Backend

OpenAI-compatible + System One style API powered by [cactus-needle](https://github.com/cactus-compute/needle).

Works with the TanStack/React frontend or plain `curl`.

## Features

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/chat/completions` | OpenAI-compatible tool calling |
| `POST /v1/systemone` | Jev-style typed decisions |
| `POST /complete` | Simple native-style endpoint |
| `GET /v1/models` | List models |
| `GET /health` | Health check |

**Tools are passed in the request body** — no `tools.json` file needed.

## Quick Start

```bash
# 1. Create a virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Server listens on **http://localhost:8000**

First request downloads Needle weights automatically (one-time).

## Example: Tool calling

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "needle",
    "messages": [
      {"role": "user", "content": "dim the living room lights to 30"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "set_lights",
          "description": "Control room lights brightness and on/off",
          "parameters": {
            "type": "object",
            "properties": {
              "room": {"type": "string"},
              "brightness": {"type": "integer", "minimum": 0, "maximum": 100},
              "on": {"type": "boolean"}
            },
            "required": ["room"]
          }
        }
      }
    ]
  }' | jq
```

## Example: System One

```bash
curl -s http://localhost:8000/v1/systemone \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Customer was charged twice and is furious",
    "questions": {
      "department": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {
          "billing": "Payments and refunds",
          "technical": "Bugs and outages",
          "sales": "Pricing"
        }
      },
      "urgent": {
        "type": "noul",
        "instructions": "Does this need urgent attention?"
      }
    }
  }' | jq
```

## Connect the React / TanStack app

1. Start this FastAPI server on port 8000
2. Start the React app (`npm run dev`)
3. Vite proxies `/v1` → `http://localhost:8000` automatically

## Important notes

- This server uses the **Python package** (`cactus-needle`), not the native binary on port 8080.
- Tools are supplied **per request** in the JSON body.
- Needle only *proposes* tool calls. Your application must execute the real functions.
- Optional: set `NEEDLE_TELEMETRY=0` to disable telemetry.

## Project layout

```
needle-fastapi-app/
├── main.py              # FastAPI application
├── requirements.txt
└── README.md
```

## Production

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

For higher concurrency consider a process manager (systemd, Docker, etc.).
