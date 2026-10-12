import json
import re
from dataclasses import dataclass

import ollama
from errors import ErrorRecord
from llm import _FALLBACK, _MODEL, _strip_fences
from verifier import verify_fix


@dataclass
class RepairAttempt:
    attempt_num: int
    llm_fixed_code: str
    llm_explanation: str
    verify_passed: bool
    verify_error: str
    verify_error_type: str


@dataclass
class RepairResult:
    success: bool
    final_fixed_code: str
    final_explanation: str
    attempts: list
    total_attempts: int


def _number_source(source: str) -> str:
    lines = source.splitlines()
    return "\n".join(f"  {i + 1} | {line}" for i, line in enumerate(lines))


def build_error_record_from_string(
    message: str, error_type: str, source: str
) -> ErrorRecord:
    return ErrorRecord(
        error_type=error_type,
        message=message,
        line=1,
        column=0,
        source_line="",
        context=_number_source(source),
        symbol_table={},
        grammar_rule="",
    )


def _base_prompt(error: ErrorRecord) -> str:
    return f"""You are a compiler error correction assistant.
A programmer wrote code in a small statically-typed language.
Casts use FUNCTION syntax: int(expr), float(expr), bool(expr).
Do NOT use C-style (int)expr. Only int(x), float(x), bool(x) are valid.

ERROR TYPE: {error.error_type}
ERROR MESSAGE: {error.message}
LINE: {error.line}, COLUMN: {error.column}

BROKEN CODE:
{error.context}

VARIABLES IN SCOPE:
{error.symbol_table}

The numbered lines in BROKEN CODE are for reference only.
Do NOT include the line numbers or the '|' character in your fixed_code.
"""


def build_repair_prompt(
    original_source: str, current_error: ErrorRecord, attempts_history: list
) -> str:
    if not attempts_history:
        return (
            _base_prompt(current_error)
            + """
Respond ONLY in this exact JSON format, no extra text:
{"explanation": "...", "fixed_code": "..."}
"""
        )

    parts = ["PREVIOUS ATTEMPTS"]
    for a in attempts_history:
        parts.append(f"Attempt {a.attempt_num} fixed code: {a.llm_fixed_code}")
        parts.append(
            f"Compiler rejected it: {a.verify_error_type}: {a.verify_error}"
        )
    parts.append("")
    parts.append(_base_prompt(current_error).rstrip())
    parts.append("")
    parts.append(f"ORIGINAL SOURCE:\n{_number_source(original_source)}")
    parts.append(
        """
The previous attempts were WRONG. Fix the ORIGINAL code again,
make sure the compiler will accept it.
Respond ONLY in JSON: {"explanation": "...", "fixed_code": "..."}
"""
    )
    return "\n".join(parts)


def _call_ollama_raw(prompt: str) -> dict:
    messages = [{"role": "user", "content": prompt}]
    response = ollama.chat(
        model=_MODEL, messages=messages, options={"temperature": 0.1}
    )
    text = response["message"]["content"]
    try:
        data = json.loads(_strip_fences(text))
    except json.JSONDecodeError:
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {"role": "user", "content": "Return ONLY valid JSON, no explanation."}
        )
        response = ollama.chat(
            model=_MODEL, messages=messages, options={"temperature": 0.1}
        )
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


def self_healing_repair(
    source: str, initial_error: ErrorRecord, max_attempts: int = 3
) -> RepairResult:
    attempts = []
    current_error = initial_error
    for attempt_num in range(1, max_attempts + 1):
        prompt = build_repair_prompt(source, current_error, attempts)
        data = _call_ollama_raw(prompt)
        fixed_code = data["fixed_code"]
        explanation = data["explanation"]
        if not fixed_code:
            attempts.append(
                RepairAttempt(
                    attempt_num,
                    "",
                    explanation,
                    False,
                    "LLM returned empty fix",
                    "SYNTAX",
                )
            )
            continue
        valid, err_msg, err_type = verify_fix(fixed_code)
        attempts.append(
            RepairAttempt(
                attempt_num, fixed_code, explanation, valid, err_msg, err_type
            )
        )
        if valid:
            return RepairResult(
                True, fixed_code, explanation, attempts, attempt_num
            )
        current_error = build_error_record_from_string(
            err_msg, err_type, fixed_code
        )
    final = attempts[-1].llm_fixed_code if attempts else ""
    return RepairResult(
        False,
        final,
        "All repair attempts failed verification.",
        attempts,
        max_attempts,
    )