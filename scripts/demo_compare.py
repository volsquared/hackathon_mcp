"""
Run 5 demo prompts against both prompt directories and write results to
output/GPT_out.txt.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output" / "cl_1.txt"

DEMO_PROMPTS = [
    "CUS009's profile says LOW risk but I've heard there was recent fraud activity — what do the transactions show and should I be concerned?",
    "Give me the full picture on CUS015 — I need to make a credit line decision",
    "Look at the full transaction and alert history for CUS017 and CUS018 — which presents more risk right now?",
]


def run_prompt(prompt: str, prompts_dir: str) -> dict:
    os.environ["PROMPTS_DIR"] = prompts_dir
    from app.agent.graph import run_agent
    result = run_agent(prompt)
    return {"tool": result.selected_tool or "None (no tool called)", "answer": result.answer}


def main() -> None:
    lines = []
    lines.append("=" * 80)
    lines.append("DEMO: WEAK vs STRONG PROMPTS — CHAINED FLOWS")
    lines.append("=" * 80)

    for i, prompt in enumerate(DEMO_PROMPTS, 1):
        print(f"[{i}/5] {prompt}")

        print("  running bad prompts...")
        bad = run_prompt(prompt, "prompts")

        print("  running good prompts...")
        good = run_prompt(prompt, "prompts_facilitator")

        lines.append("")
        lines.append(f"[{i}] PROMPT: {prompt}")
        lines.append("")
        lines.append("  BAD PROMPTS")
        lines.append(f"  Tool   : {bad['tool']}")
        lines.append(f"  Answer : {bad['answer']}")
        lines.append("")
        lines.append("  GOOD PROMPTS")
        lines.append(f"  Tool   : {good['tool']}")
        lines.append(f"  Answer : {good['answer']}")
        lines.append("")
        lines.append("-" * 80)

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWritten to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
