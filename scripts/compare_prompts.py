"""
Run all eval cases against both prompt directories and write a side-by-side
comparison to output/prompt_comparison.txt.

Usage:
    python -m scripts.compare_prompts
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output" / "prompt_comparison.txt"

from app.eval.runner import CASES
from app.agent.graph import run_agent


def run_all(prompts_dir: str) -> list[dict]:
    os.environ["PROMPTS_DIR"] = prompts_dir
    results = []
    for prompt, expected_tool, should_contain, should_not_contain in CASES:
        result = run_agent(prompt)
        tool_ok = result.selected_tool == expected_tool
        results.append({
            "prompt": prompt,
            "expected_tool": expected_tool,
            "tool": result.selected_tool,
            "tool_ok": tool_ok,
            "answer": result.answer,
            "confidence": result.confidence,
        })
    return results


def format_report(poor: list[dict], good: list[dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("PROMPT COMPARISON: poor prompts (prompts/) vs good prompts (prompts_facilitator/)")
    lines.append("=" * 80)

    poor_pass = sum(1 for r in poor if r["tool_ok"])
    good_pass = sum(1 for r in good if r["tool_ok"])
    lines.append(f"\nSCORES  |  poor prompts: {poor_pass}/{len(poor)}  |  good prompts: {good_pass}/{len(good)}\n")

    for i, (p, g) in enumerate(zip(poor, good), 1):
        prompt = p["prompt"]
        expected = p["expected_tool"] or "None (refusal)"
        lines.append("-" * 80)
        lines.append(f"[{i:02d}] {prompt}")
        lines.append(f"     Expected tool : {expected}")
        lines.append("")

        def result_label(r: dict) -> str:
            if r["tool_ok"]:
                return "PASS"
            return f"FAIL (wrong tool: used {r['tool'] or 'None'}, expected {expected})"

        lines.append(f"  POOR PROMPTS [{result_label(p)}]")
        lines.append(f"    Tool   : {p['tool'] or 'None'}")
        lines.append(f"    Answer : {p['answer']}")
        lines.append("")
        lines.append(f"  GOOD PROMPTS [{result_label(g)}]")
        lines.append(f"    Tool   : {g['tool'] or 'None'}")
        lines.append(f"    Answer : {g['answer']}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> None:
    print("Running poor prompts (prompts/)...")
    poor = run_all("prompts")

    print("Running good prompts (prompts_facilitator/)...")
    good = run_all("prompts_facilitator")

    report = format_report(poor, good)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
