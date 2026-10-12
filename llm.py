import json
import re

import ollama
from errors import ErrorRecord

_MODEL = "qwen2.5-coder:3b"
_FALLBACK = {"explanation": "LLM returned invalid format", "fixed_code": ""}


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def call_llm(error_record: ErrorRecord) -> dict:
    prompt = f"""You are a compiler error correction assistant.
A programmer wrote code in a small statically-typed language.
Casts use FUNCTION syntax: int(expr), float(expr), bool(expr).
Do NOT use C-style (int)expr. Only int(x), float(x), bool(x) are valid.

ERROR TYPE: {error_record.error_type}
ERROR MESSAGE: {error_record.message}
LINE: {error_record.line}, COLUMN: {error_record.column}

BROKEN CODE:
{error_record.context}

VARIABLES IN SCOPE:
{error_record.symbol_table}

The numbered lines in BROKEN CODE are for reference only.
Do NOT include the line numbers or the '|' character in your fixed_code.

Respond ONLY in this exact JSON format, no extra text:
{{"explanation": "...", "fixed_code": "..."}}

"""
    options = {"temperature": 0.1}
    messages = [{"role": "user", "content": prompt}]

    response = ollama.chat(model=_MODEL, messages=messages, options=options)
    text = response["message"]["content"]

    try:
        data = json.loads(_strip_fences(text))
    except json.JSONDecodeError:
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": "Return ONLY valid JSON, no explanation."})
        response = ollama.chat(model=_MODEL, messages=messages, options=options)
        text = response["message"]["content"]
        try:
            data = json.loads(_strip_fences(text))
        except json.JSONDecodeError:
            return _FALLBACK

    if not (
        isinstance(data, dict)
        and isinstance(data.get("explanation"), str)
        and isinstance(data.get("fixed_code"), str)
    ):
        return _FALLBACK
    return data
