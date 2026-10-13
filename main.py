import sys
import time
from pathlib import Path

from lexer import lex, LexError
from parser import Parser, ParseError
from semantic import SemanticAnalyzer, SemanticError
from errors import build_error_record
from repair_loop import self_healing_repair


def compile_source(source: str, log_trace: bool = False) -> dict:
    """Run the full pipeline. On error, trigger self-healing repair."""
    try:
        tokens = lex(source)
        ast = Parser(tokens).parse()
        SemanticAnalyzer().analyze(ast)
        return {"status": "ok"}
    except (LexError, ParseError, SemanticError) as e:
        record = build_error_record(e, source, {})

    t0 = time.time()
    result = self_healing_repair(source, record, max_attempts=3)
    elapsed = time.time() - t0

    return {
        "status": "fixed" if result.success else "failed",
        "result": result,
        "original_error": record,
        "elapsed": elapsed,
    }


def _print_attempts(result):
    for a in result.attempts:
        if a.verify_passed:
            print(f"  Attempt {a.attempt_num}: PASS")
        else:
            print(
                f"  Attempt {a.attempt_num}: FAIL "
                f"({a.verify_error_type}: {a.verify_error})"
            )


def _display_outcome(outcome: dict, source_name: str) -> None:
    print("=" * 40)
    print(f"Compiling: {source_name}")
    print("=" * 40)

    if outcome["status"] == "ok":
        print("\u2713 Compiled successfully. No errors detected.")
        return

    record = outcome["original_error"]
    print(f"\nOriginal error [{record.error_type}]: {record.message}")
    print(f"  Line {record.line}, Column {record.column}")

    result = outcome["result"]

    if outcome["status"] == "fixed":
        print("\nRepair attempts:")
        _print_attempts(result)
        print(f"\n\u2713 Fixed in {result.total_attempts} attempt(s).")
        print(f"Explanation: {result.final_explanation}")
        print("\nFixed code:")
        print(result.final_fixed_code)
    else:
        print("\nRepair attempts:")
        _print_attempts(result)
        print(
            f"\n\u2717 Could not produce a verified fix after "
            f"{result.total_attempts} attempts."
        )
    print()


def _run_file(path_str: str) -> None:
    path = Path(path_str)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
    source = path.read_text(encoding="utf-8")
    outcome = compile_source(source)
    _display_outcome(outcome, path.name)


def _run_interactive() -> None:
    print("Interactive mode. Type code, then a blank line to submit.")
    print("Type 'quit' on its own line to exit.\n")
    while True:
        try:
            lines = []
            while True:
                prompt = "> " if not lines else "... "
                line = input(prompt)
                if line.strip() == "quit" and not lines:
                    print("Bye.")
                    return
                if line == "":
                    break
                lines.append(line)
            if not lines:
                continue
            source = "\n".join(lines)
            outcome = compile_source(source)
            _display_outcome(outcome, "interactive input")
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            return


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ("-i", "--interactive"):
        _run_interactive()
        return
    if len(sys.argv) != 2:
        print("Usage: python main.py <file.lang>")
        print("       python main.py -i     (interactive mode)")
        sys.exit(1)
    _run_file(sys.argv[1])


if __name__ == "__main__":
    main()