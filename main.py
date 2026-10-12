import sys
from pathlib import Path

from lexer import lex, LexError
from parser import Parser, ParseError
from semantic import SemanticAnalyzer, SemanticError
from errors import build_error_record
from repair_loop import self_healing_repair


def compile_source(source: str) -> dict:
    """Run the full pipeline. On error, trigger self-healing repair."""
    try:
        tokens = lex(source)
        ast = Parser(tokens).parse()
        SemanticAnalyzer().analyze(ast)
        return {"status": "ok"}
    except (LexError, ParseError, SemanticError) as e:
        record = build_error_record(e, source, {})

    result = self_healing_repair(source, record, max_attempts=3)

    if result.success:
        return {"status": "fixed", "result": result, "original_error": record}
    return {"status": "failed", "result": result, "original_error": record}


def _print_attempts(result):
    for a in result.attempts:
        if a.verify_passed:
            print(f"  Attempt {a.attempt_num}: PASS")
        else:
            print(
                f"  Attempt {a.attempt_num}: FAIL "
                f"({a.verify_error_type}: {a.verify_error})"
            )


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <file.lang>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    source = path.read_text(encoding="utf-8")

    print("=" * 40)
    print(f"Compiling: {path.name}")
    print("=" * 40)

    outcome = compile_source(source)

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


if __name__ == "__main__":
    main()