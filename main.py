"""
Needle FastAPI wrapper
----------------------
OpenAI-compatible /v1/chat/completions + Jev-style /v1/systemone
Uses the official cactus-needle Python package.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union, Literal

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

import needle

app = FastAPI(
    title="Needle API",
    description="OpenAI-compatible tool calling + System One style decisions powered by Needle",
    version="1.0.0",
)

# Allow the React / TanStack frontend (and curl) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_agent(tools: Optional[List[Any]] = None, weights: Optional[str] = None):
    """Create a Needle agent. Tools can be OpenAI-style or raw schemas."""
    return needle.Needle(tools=tools or [], weights=weights)


def openai_tools_to_needle(tools: Optional[List[Dict]]) -> List[Dict]:
    """
    Accept both:
      - OpenAI style: {"type": "function", "function": {"name": ..., "parameters": ...}}
      - Needle raw:   {"name": ..., "parameters": ...}
    """
    if not tools:
        return []
    result = []
    for t in tools:
        if "function" in t:
            fn = t["function"]
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        else:
            result.append(t)
    return result


# ---------------------------------------------------------------------------
# OpenAI-compatible models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str = "needle"
    messages: List[ChatMessage]
    tools: Optional[List[Dict]] = None
    temperature: Optional[float] = 0.0
    stream: bool = False
    max_tokens: Optional[int] = 512


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict]
    usage: Dict[str, int]
    needle: Optional[Dict] = None


# ---------------------------------------------------------------------------
# System One models
# ---------------------------------------------------------------------------

class SystemOneQuestion(BaseModel):
    type: Literal["noul", "choice", "score"]
    instructions: str
    criteria: Optional[Dict[str, str]] = None


class SystemOneRequest(BaseModel):
    model: str = "needle"
    state: Union[str, Dict, List]
    questions: Dict[str, SystemOneQuestion]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "needle", "package": "cactus-needle"}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "needle",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "cactus-compute",
            },
            {
                "id": "needle-3",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "cactus-compute",
            },
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    req: ChatCompletionRequest,
    authorization: Optional[str] = Header(None),
):
    """
    OpenAI-compatible chat completions focused on tool calling.
    Tools are taken from the request body (not from a tools.json file).
    """
    # Optional simple API key check
    # if authorization and authorization != "Bearer sk-needle":
    #     raise HTTPException(status_code=401, detail="Invalid API key")

    # Last user message
    user_msg = None
    for m in reversed(req.messages):
        if m.role == "user" and m.content:
            user_msg = m.content
            break

    if not user_msg:
        raise HTTPException(status_code=400, detail="No user message found")

    tools = openai_tools_to_needle(req.tools)

    try:
        agent = make_agent(tools=tools)
        result = agent.complete(user_msg, max_new_tokens=req.max_tokens or 512)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Needle error: {str(e)}")

    function_calls = result.get("function_calls") or []
    tool_calls = []
    for call in function_calls:
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": call["name"],
                "arguments": json.dumps(call.get("arguments", {})),
            },
        })

    message = {
        "role": "assistant",
        "content": None if tool_calls else (result.get("reasoning") or ""),
        "tool_calls": tool_calls or None,
    }

    response = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "needle": {
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "suppressed_calls": result.get("suppressed_calls"),
            "validation": result.get("validation"),
            "prefill_tps": result.get("prefill_tps"),
            "decode_tps": result.get("decode_tps"),
            "peak_ram_mb": result.get("peak_ram_mb"),
        },
    }

    if req.stream:
        def event_stream():
            yield f"data: {json.dumps(response)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return response


@app.post("/v1/systemone")
async def systemone(req: SystemOneRequest):
    """
    Jev-style System One endpoint.
    Maps each question to a constrained extraction field via Needle.
    """
    # properties = {}
    # required = []

    # for qid, q in req.questions.items():
    #     if q.type == "noul":
    #         properties[qid] = {
    #             "type": "boolean",
    #             "description": q.instructions,
    #         }
    #     elif q.type == "choice":
    #         options = list(q.criteria.keys()) if q.criteria else ["yes", "no"]
    #         properties[qid] = {
    #             "type": "string",
    #             "enum": options,
    #             "description": q.instructions,
    #         }
    #     elif q.type == "score":
    #         levels = list(q.criteria.keys()) if q.criteria else ["0", "1", "2"]
    #         properties[qid] = {
    #             "type": "integer",
    #             "minimum": 0,
    #             "maximum": max(len(levels) - 1, 0),
    #             "description": q.instructions,
    #         }
    #     required.append(qid)

    
    properties = {}
    required = []

    for qid, q in req.questions.items():
        if q.type == "noul":
            properties[qid] = {
                "type": "boolean",
                "description": q.instructions,
            }
        elif q.type == "choice":
            options = list(q.criteria.keys()) if q.criteria else ["yes", "no"]
            # Put criteria text into description so the model can ground choices
            crit = "; ".join(f"{k}={v}" for k, v in (q.criteria or {}).items())
            properties[qid] = {
                "type": "string",
                "enum": options,
                "description": f"{q.instructions}",
                #"description": f"{q.instructions}. Options: {crit}",
            }
        elif q.type == "score":
            levels = list(q.criteria.keys()) if q.criteria else ["0", "1", "2"]
            # Use string enum of the criteria keys (more reliable than bare int)
            crit = "; ".join(f"{k}={v}" for k, v in (q.criteria or {}).items())
            properties[qid] = {
                "type": "string",
                "enum": levels,
                "description": f"{q.instructions}. Levels: {crit}",
            }
        required.append(qid)

    schema = {
        "name": "decision",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }    

    schema = {
        "name": "decision",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }

    if isinstance(req.state, (dict, list)):
        state_text = json.dumps(req.state, ensure_ascii=False, strict=False)
    else:
        state_text = str(req.state)

    try:
        extracted = needle.extract(state_text, schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Needle extract error: {str(e)}")

    if extracted is None:
        raise HTTPException(status_code=422, detail="Could not extract answers from state")

    # Normalize to dict
    if hasattr(extracted, "model_dump"):
        extracted = extracted.model_dump()
    elif not isinstance(extracted, dict):
        extracted = dict(extracted) if extracted else {}

    answers = {}
    for qid, q in req.questions.items():
        value = extracted.get(qid)

        if q.type == "noul":
            answers[qid] = {
                "type": "noul",
                "noul": float(bool(value)),
            }
        elif q.type == "choice":
            answers[qid] = {
                "type": "choice",
                "choice": value,
                "confidence": 0.9,
                "probabilities": {str(value): 0.9} if value is not None else {},
            }
        # elif q.type == "score":
        #     answers[qid] = {
        #         "type": "score",
        #         "score": float(value) if value is not None else 0.0,
        #         "confidence": 0.9,
        #     }
        elif q.type == "score":
            # value is now a string key like "1"
            try:
                score_val = float(value)
            except (TypeError, ValueError):
                score_val = 0.0
            answers[qid] = {
                "type": "score",
                "score": score_val,
                "choice": value,
                "confidence": 0.9,
            }

    return {
        "model": req.model,
        "answers": answers,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


@app.post("/complete")
async def complete_native_style(body: Dict[str, Any]):
    """
    Simple native-style endpoint for compatibility.
    Body: {"input": "...", "tools": [...] }  (tools optional)
    """
    user_input = body.get("input") or body.get("query") or ""
    if not user_input:
        raise HTTPException(status_code=400, detail="Missing 'input' field")

    tools = openai_tools_to_needle(body.get("tools"))

    try:
        agent = make_agent(tools=tools)
        result = agent.complete(user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
