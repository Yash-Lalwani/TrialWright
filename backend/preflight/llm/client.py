import asyncio
import json
import os
import time
from contextvars import ContextVar

from pydantic import BaseModel, ValidationError

from preflight.llm import cache

current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)

_client = None
_semaphore = asyncio.Semaphore(int(os.getenv("LLM_CONCURRENCY", "8")))


class LLMCacheMiss(RuntimeError):
    pass


def model() -> str:
    return os.getenv("PREFLIGHT_MODEL", "deepseek/deepseek-v4-flash-20260731")


def mode() -> str:
    return os.getenv("LLM_MODE", "replay")


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
            max_retries=3,
            timeout=120,
        )
    return _client


def _log(step: str, tokens_in: int, tokens_out: int, latency_s: float, cost_usd: float, cache_hit: bool):
    from preflight.db import LLMCall, session

    with session() as s:
        s.add(LLMCall(run_id=current_run_id.get(), step=step, model=model(), tokens_in=tokens_in,
                      tokens_out=tokens_out, latency_s=latency_s, cost_usd=cost_usd, cache_hit=cache_hit))
        s.commit()


async def _call(step: str, system: str, user: str, temperature: float,
                schema: type[BaseModel] | None = None) -> str:
    schema_name = schema.__name__ if schema else "text"
    k = cache.key(model(), system, user, schema_name)
    if mode() != "live" and (hit := cache.get(k)):
        _log(step, hit["tokens_in"], hit["tokens_out"], 0.0, 0.0, cache_hit=True)
        return hit["content"]
    if mode() == "replay":
        raise LLMCacheMiss(f"No cached LLM response for step '{step}' (key {k}). Run with LLM_MODE=record.")

    kwargs = {}
    if schema and os.getenv("LLM_JSON_SCHEMA", "false") == "true":
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema.model_json_schema(), "strict": False},
        }
    elif schema:
        kwargs["response_format"] = {"type": "json_object"}

    start = time.monotonic()
    async with _semaphore:
        resp = await _get_client().chat.completions.create(
            model=model(),
            temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            extra_body={"usage": {"include": True}, "provider": {"data_collection": "deny"}},
            **kwargs,
        )
    latency = time.monotonic() - start
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    tokens_in, tokens_out = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
    cost = float(getattr(usage, "cost", 0) or 0)

    if mode() == "record":
        cache.put(k, {"step": step, "model": model(), "content": content,
                      "tokens_in": tokens_in, "tokens_out": tokens_out})
    _log(step, tokens_in, tokens_out, latency, cost, cache_hit=False)
    return content


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def json_system(system: str, schema: type[BaseModel]) -> str:
    return (f"{system}\n\nRespond with only a JSON object matching this JSON schema:\n"
            f"{json.dumps(schema.model_json_schema())}")


async def complete_json(step: str, system: str, user: str,
                        schema: type[BaseModel], temperature: float = 0) -> BaseModel:
    system = json_system(system, schema)
    content = await _call(step, system, user, temperature, schema)
    try:
        return schema.model_validate_json(_strip_fences(content))
    except ValidationError as e:
        retry_user = (f"{user}\n\nYour previous answer was invalid:\n{content}\n\n"
                      f"Validation errors:\n{e}\n\nReturn corrected JSON only.")
        content = await _call(step, system, retry_user, temperature, schema)
        return schema.model_validate_json(_strip_fences(content))


async def complete_text(step: str, system: str, user: str, temperature: float = 0.2) -> str:
    return await _call(step, system, user, temperature)
