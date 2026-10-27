import os
import sys

from dotenv import load_dotenv

from ai_beauty_appointment_manager.agent import Agent
from ai_beauty_appointment_manager.conversation import run_conversation


def main():
    load_dotenv()

    diagnostic = (
        "--diagnostic" in sys.argv
        or str(os.getenv("DIAGNOSTIC_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}
    )

    try:
        agent = Agent(diagnostic=diagnostic)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)

    run_conversation(agent, diagnostic=diagnostic)


if __name__ == "__main__":
    main()
