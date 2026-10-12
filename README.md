# AI-Assisted Compiler Frontend

A compiler for a tiny statically-typed language that detects lexical, syntax, and semantic errors, then uses a locally-hosted Large Language Model to suggest and verify repairs.

The LLM is treated as an untrusted suggestion engine — every fix it produces is re-verified by the deterministic compiler before being shown to the user. If a fix fails, the compiler's feedback is fed back to the LLM in a self-healing repair loop (up to 3 attempts).

---

## Features

- **Lexer** — tokenizes source code, detects illegal characters, unterminated strings, and malformed numbers
- **Recursive-descent parser** — builds an AST, detects syntax errors with line/column precision, and uses panic-mode recovery to report multiple errors
- **Semantic analyzer** — symbol-table-driven type and scope checking (undeclared variables, redeclarations, type mismatches, invalid conditions)
- **Structured error records** — instead of raw compiler output, errors are formatted with type, location, source context, and symbol table
- **Local LLM integration** — uses [Ollama](https://ollama.com) with `qwen2.5-coder:3b`, no cloud APIs, no keys, no rate limits
- **Self-healing repair loop** — failed fixes are re-submitted to the LLM with compiler feedback, up to 3 attempts
- **Deterministic verification** — every LLM fix is re-run through lexer → parser → semantic analyzer; only verified fixes are accepted

---

## Requirements

- **Python 3.10+**
- **[Ollama](https://ollama.com)** installed and running
- ~3 GB of free RAM/VRAM (for the 3B model)

---

## Setup

### 1. Install Ollama

Download and install from https://ollama.com/download

### 2. Pull the model

```bash
ollama pull qwen2.5-coder:3b
