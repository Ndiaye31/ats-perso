import json
import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scheduler import run_scheduled_jobs_once, settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true", help="Run without DB/network side effects.")
    args = parser.parse_args()

    if args.simulate:
        result = {
            "scrape": {"simulated": True},
            "rescore": {"simulated": True},
            "optional_batch": {
                "enabled": settings.scheduler_batch_enabled,
                "simulated": True,
            },
        }
    else:
        result = run_scheduled_jobs_once()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
