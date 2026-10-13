"""Runs all benchmark tests through the pipeline and produces metrics."""
import json
import time
from pathlib import Path
from collections import defaultdict

from lexer import lex, LexError
from parser import Parser, ParseError
from semantic import SemanticAnalyzer, SemanticError
from errors import build_error_record
from repair_loop import self_healing_repair


def _try_compile(source: str):
    """Returns None if code compiles cleanly, else the caught exception."""
    try:
        tokens = lex(source)
        ast = Parser(tokens).parse()
        SemanticAnalyzer().analyze(ast)
        return None
    except (LexError, ParseError, SemanticError) as e:
        return e


def run_test(name: str, code: str, category: str) -> dict:
    """Run one test case, return per-test metrics."""
    row = {
        "name": name,
        "category": category,
        "detected": False,
        "attempts": [],           # [True/False] per attempt
        "final_success": False,
        "total_attempts": 0,
        "elapsed": 0.0,
    }

    err = _try_compile(code)
    if err is None:
        row["final_success"] = True
        return row

    row["detected"] = True
    record = build_error_record(err, code, {})

    t0 = time.time()
    result = self_healing_repair(code, record, max_attempts=3)
    row["elapsed"] = time.time() - t0

    for a in result.attempts:
        row["attempts"].append(a.verify_passed)

    row["final_success"] = result.success
    row["total_attempts"] = result.total_attempts
    return row


def main():
    tests_dir = Path("tests")
    expected_file = tests_dir / "expected.json"

    if not expected_file.exists():
        print("tests/expected.json not found. Run make_tests.py first.")
        return

    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    rows = []
    print(f"Running {len(expected)} tests...\n")
    print(f"{'Test':<8} {'Category':<10} {'Detected':<10} "
          f"{'A1':<4} {'A2':<4} {'A3':<4} {'Final':<7} {'Time(s)':<8}")
    print("-" * 70)

    for filename, meta in sorted(expected.items()):
        name = filename.replace(".lang", "")
        code = (tests_dir / filename).read_text(encoding="utf-8")
        category = meta["category"]

        row = run_test(name, code, category)
        rows.append(row)

        a1 = "PASS" if len(row["attempts"]) > 0 and row["attempts"][0] else "-"
        a2 = "PASS" if len(row["attempts"]) > 1 and row["attempts"][1] else "-"
        a3 = "PASS" if len(row["attempts"]) > 2 and row["attempts"][2] else "-"
        if len(row["attempts"]) > 0 and not row["attempts"][0]:
            a1 = "FAIL"
        if len(row["attempts"]) > 1 and not row["attempts"][1]:
            a2 = "FAIL"
        if len(row["attempts"]) > 2 and not row["attempts"][2]:
            a3 = "FAIL"

        final = "FIXED" if row["final_success"] else "FAIL"
        detected = "YES" if row["detected"] else "clean"

        print(f"{name:<8} {category:<10} {detected:<10} "
              f"{a1:<4} {a2:<4} {a3:<4} {final:<7} {row['elapsed']:<8.2f}")

    # ---- Summary metrics ----
    total = len(rows)
    detected_count = sum(1 for r in rows if r["detected"])
    fixed_count = sum(1 for r in rows if r["final_success"] and r["detected"])

    a1_success = sum(
        1 for r in rows if r["attempts"] and r["attempts"][0]
    )
    a1_or_a2 = sum(
        1 for r in rows if any(r["attempts"][:2])
    )
    a1_a2_a3 = sum(
        1 for r in rows if any(r["attempts"][:3])
    )

    avg_attempts = (
        sum(r["total_attempts"] for r in rows if r["final_success"] and r["detected"])
        / max(fixed_count, 1)
    )
    avg_time = sum(r["elapsed"] for r in rows if r["detected"]) / max(detected_count, 1)

    print("\n" + "=" * 70)
    print("SUMMARY METRICS")
    print("=" * 70)
    print(f"Total tests:                    {total}")
    print(f"Errors detected:                {detected_count}")
    print(f"Repairs successful:             {fixed_count}")
    print(f"Overall repair success rate:    {fixed_count / max(detected_count,1) * 100:.1f}%")
    print(f"Attempt-1 success rate:         {a1_success / max(detected_count,1) * 100:.1f}%")
    print(f"Within 2 attempts:              {a1_or_a2 / max(detected_count,1) * 100:.1f}%")
    print(f"Within 3 attempts:              {a1_a2_a3 / max(detected_count,1) * 100:.1f}%")
    print(f"Avg attempts per fixed repair:  {avg_attempts:.2f}")
    print(f"Avg repair latency:             {avg_time:.2f}s")

    # ---- Category breakdown ----
    print("\n" + "=" * 70)
    print("CATEGORY BREAKDOWN")
    print("=" * 70)

    by_cat = defaultdict(lambda: {"total": 0, "fixed": 0, "a1": 0})
    for r in rows:
        if not r["detected"]:
            continue
        c = r["category"]
        by_cat[c]["total"] += 1
        if r["final_success"]:
            by_cat[c]["fixed"] += 1
        if r["attempts"] and r["attempts"][0]:
            by_cat[c]["a1"] += 1

    print(f"{'Category':<12} {'Total':<8} {'Fixed':<8} {'A1 Success':<12} {'Rate':<8}")
    print("-" * 60)
    for cat, s in sorted(by_cat.items()):
        rate = s["fixed"] / max(s["total"], 1) * 100
        a1_rate = s["a1"] / max(s["total"], 1) * 100
        print(f"{cat:<12} {s['total']:<8} {s['fixed']:<8} "
              f"{s['a1']:<12} {rate:.1f}%")

    # ---- Save results to JSON for the report ----
    out = {
        "rows": rows,
        "summary": {
            "total": total,
            "detected": detected_count,
            "fixed": fixed_count,
            "overall_rate": fixed_count / max(detected_count, 1) * 100,
            "a1_rate": a1_success / max(detected_count, 1) * 100,
            "a12_rate": a1_or_a2 / max(detected_count, 1) * 100,
            "a123_rate": a1_a2_a3 / max(detected_count, 1) * 100,
            "avg_attempts": avg_attempts,
            "avg_time": avg_time,
            "by_category": dict(by_cat),
        },
    }
    Path("results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nRaw results saved to results.json")


if __name__ == "__main__":
    main()