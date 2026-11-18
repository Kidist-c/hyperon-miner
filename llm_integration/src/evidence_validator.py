
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "data"
    / "processed"
    / "mined_patterns.json"
)


def validate_patterns(patterns):
    errors = []

    if not isinstance(patterns, list):
        return ["Input must contain a JSON list of patterns."]

    for index, item in enumerate(patterns):
        record = index + 1

        if not isinstance(item, dict):
            errors.append(f"Record {record}: Invalid record format.")
            continue

        required_fields = [
            "pattern",
            "reported_support",
            "evidence"
        ]

        missing = [
            field for field in required_fields
            if field not in item
        ]

        if missing:
            errors.append(
                f"Record {record}: Missing fields: {missing}"
            )
            continue

        if not isinstance(item["pattern"], str):
            errors.append(
                f"Record {record}: Pattern must be a string."
            )

        support = item["reported_support"]
        evidence = item["evidence"]

        if (
            not isinstance(support, int)
            or isinstance(support, bool)
            or support < 0
        ):
            errors.append(
                f"Record {record}: Invalid reported support."
            )
            continue

        if not isinstance(evidence, list):
            errors.append(
                f"Record {record}: Evidence must be a list."
            )
            continue

        if not all(isinstance(match, str) for match in evidence):
            errors.append(
                f"Record {record}: Evidence contains invalid entries."
            )
            continue

        actual_count = len(evidence)

        if support != actual_count:
            errors.append(
                f"Record {record}: Support mismatch "
                f"(reported={support}, evidence={actual_count})."
            )

    return errors


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as file:
        patterns = json.load(file)

    errors = validate_patterns(patterns)

    print(f"Patterns checked: {len(patterns)}")

    if errors:
        print(f"Validation errors: {len(errors)}")

        for error in errors:
            print(f"ERROR: {error}")

        print("Validation failed.")
    else:
        print("Validation errors: 0")
        print("Validation passed.")


if __name__ == "__main__":
    main()
