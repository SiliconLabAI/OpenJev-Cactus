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
    # Jev: choice=dict, score=list (ordered), noul=optional dict
    criteria: Optional[Union[Dict[str, Any], List[Any]]] = None


class SystemOneRequest(BaseModel):
    model: str = "needle"
    state: Union[str, Dict, List]
    questions: Dict[str, SystemOneQuestion]
    independent: Optional[bool] = None  # ignored; accepted for Jev-compatible clients


def _criteria_levels(criteria: Optional[Union[Dict, List]]) -> List[str]:
    """Normalize Jev list or dict criteria into ordered string levels."""
    if criteria is None:
        return ["0", "1", "2"]
    if isinstance(criteria, list):
        out = []
        for i, item in enumerate(criteria):
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                # structured level → stable label
                out.append(str(item.get("meaning") or item.get("label") or i))
            else:
                out.append(str(item))
        return out or ["0", "1", "2"]
    if isinstance(criteria, dict):
        return [str(k) for k in criteria.keys()]
    return ["0", "1", "2"]


def _choice_options(criteria: Optional[Union[Dict, List]]) -> List[str]:
    if not criteria:
        return ["yes", "no"]
    if isinstance(criteria, dict):
        return [str(k) for k in criteria.keys()]
    if isinstance(criteria, list):
        return [str(x) if not isinstance(x, dict) else str(x.get("label", i))
                for i, x in enumerate(criteria)]
    return ["yes", "no"]


def _soft_probs(winner: Optional[str], options: List[str], peak: float = 0.85) -> Dict[str, float]:
    """Approximate a distribution peaked on the winner (Needle has no real soft probs)."""
    if not options:
        return {}
    if winner is None or str(winner) not in [str(o) for o in options]:
        # uniform
        p = 1.0 / len(options)
        return {str(o): round(p, 4) for o in options}
    rest = options
    n = len(rest)
    if n == 1:
        return {str(winner): 1.0}
    other = (1.0 - peak) / (n - 1)
    probs = {str(o): round(other, 4) for o in rest}
    probs[str(winner)] = round(peak, 4)
    # fix rounding drift
    s = sum(probs.values())
    if abs(s - 1.0) > 1e-6:
        probs[str(winner)] = round(probs[str(winner)] + (1.0 - s), 4)
    return probs


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
    Accepts Jev payloads (score criteria as list, choice as dict).
    Returns Jev-shaped answers (soft probabilities approximated).
    """
    properties: Dict[str, Any] = {}
    required: List[str] = []
    # Keep level order for score → numeric index
    score_legends: Dict[str, Dict[str, str]] = {}
    choice_options_map: Dict[str, List[str]] = {}

    for qid, q in req.questions.items():
        if q.type == "noul":
            properties[qid] = {
                "type": "boolean",
                "description": q.instructions,  # keep short
            }
        elif q.type == "choice":
            options = _choice_options(q.criteria)
            choice_options_map[qid] = options
            properties[qid] = {
                "type": "string",
                "enum": options,
                "description": q.instructions,
            }
        elif q.type == "score":
            levels = _criteria_levels(q.criteria)
            # enum labels as returned by extract; legend maps index → label
            score_legends[qid] = {str(i): label for i, label in enumerate(levels)}
            properties[qid] = {
                "type": "string",
                "enum": levels,
                "description": q.instructions,
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

    if isinstance(req.state, (dict, list)):
        state_text = json.dumps(req.state, ensure_ascii=False)
    else:
        state_text = str(req.state)

    try:
        extracted = needle.extract(state_text, schema, strict=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Needle extract error: {e!r}")

    if extracted is None:
        raise HTTPException(status_code=422, detail="Could not extract answers from state")

    if hasattr(extracted, "model_dump"):
        extracted = extracted.model_dump()
    elif not isinstance(extracted, dict):
        extracted = dict(extracted) if extracted else {}

    answers: Dict[str, Any] = {}
    for qid, q in req.questions.items():
        value = extracted.get(qid)

        if q.type == "noul":
            # Soft-ish noul: peak toward yes/no instead of hard 0/1 only
            yes = bool(value)
            noul = 0.9 if yes else 0.1
            answers[qid] = {
                "type": "noul",
                "noul": noul,
            }

        elif q.type == "choice":
            options = choice_options_map.get(qid, [])
            winner = str(value) if value is not None else None
            probs = _soft_probs(winner, options, peak=0.85)
            conf = probs.get(winner, 0.0) if winner else 0.0
            answers[qid] = {
                "type": "choice",
                "choice": winner,
                "confidence": conf,
                "probabilities": probs,
            }

        elif q.type == "score":
            legend = score_legends.get(qid, {})
            levels = list(legend.values())
            # value is the label string from enum
            label = str(value) if value is not None else (levels[0] if levels else "0")
            # map label → index
            try:
                idx = levels.index(label)
            except ValueError:
                # maybe model returned index as string
                try:
                    idx = int(label)
                    label = legend.get(str(idx), label)
                except (TypeError, ValueError):
                    idx = 0
                    label = levels[0] if levels else "0"

            probs = _soft_probs(label, levels, peak=0.8)
            # Jev score = probability-weighted mean of indices
            index_probs = {}
            score_val = 0.0
            for i, lvl in enumerate(levels):
                p = probs.get(str(lvl), 0.0)
                index_probs[str(i)] = p
                score_val += i * p

            answers[qid] = {
                "type": "score",
                "score": round(score_val, 4),
                "confidence": index_probs.get(str(idx), 0.0),
                "legend": legend,
                "probabilities": index_probs,
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
