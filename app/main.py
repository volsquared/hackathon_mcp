from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.graph import run_agent


def main() -> None:
    while True:
        prompt = input("Ask a banking question (or 'exit'): ").strip()
        if prompt.lower() in {"exit", "quit"}:
            break
        result = run_agent(prompt)
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
