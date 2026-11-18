
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MINED_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "data"
    / "processed"
    / "mined_patterns.json"
)

EXPLANATIONS_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "output"
    / "explanations.json"
)

REQUIRED_HEADINGS = [
    "### Pattern",
    "### Explanation",
    "### Evidence",
    "### Limitations"
]

MAX_WORDS = 120


def validate_explanations(mined_patterns, explanations):
    errors = []
    warnings = []

    if not isinstance(mined_patterns, list):
        return ["Mined patterns must be a JSON list."], warnings

    if not isinstance(explanations, list):
        return ["Explanations must be a JSON list."], warnings

    # Index original miner records by pattern.
    mined_by_pattern = {
        item["pattern"]: item
        for item in mined_patterns
        if isinstance(item, dict)
        and isinstance(item.get("pattern"), str)
    }

    for index, result in enumerate(explanations):
        record = index + 1

        if not isinstance(result, dict):
            errors.append(
                f"Record {record}: Invalid explanation format."
            )
            continue

        required_fields = [
            "pattern",
            "reported_support",
            "total_evidence_count",
            "evidence_sample_count",
            "evidence_sample",
            "explanation"
        ]

        missing = [
            field for field in required_fields
            if field not in result
        ]

        if missing:
            errors.append(
                f"Record {record}: Missing fields: {missing}"
            )
            continue

        pattern = result["pattern"]

        if pattern not in mined_by_pattern:
            errors.append(
                f"Record {record}: Pattern not found in miner output."
            )
            continue

        original = mined_by_pattern[pattern]

        # Check reported support.
        if result["reported_support"] != original["reported_support"]:
            errors.append(
                f"Record {record}: Reported support does not "
                "match original miner output."
            )

        # Check total evidence count.
        if result["total_evidence_count"] != len(original["evidence"]):
            errors.append(
                f"Record {record}: Total evidence count mismatch."
            )

        # Check evidence sample type.
        sample = result["evidence_sample"]

        if not isinstance(sample, list):
            errors.append(
                f"Record {record}: Evidence sample must be a list."
            )
            continue

        # Check sample count.
        if result["evidence_sample_count"] != len(sample):
            errors.append(
                f"Record {record}: Evidence sample count mismatch."
            )

        # Check that sampled records exist in original evidence.
        original_evidence = set(original["evidence"])

        for evidence in sample:
            if evidence not in original_evidence:
                errors.append(
                    f"Record {record}: Evidence sample contains "
                    "a record absent from original miner evidence."
                )
                break

        # Check explanation type.
        explanation = result["explanation"]

        if not isinstance(explanation, str):
            errors.append(
                f"Record {record}: Explanation must be a string."
            )
            continue

        # Check required headings.
        for heading in REQUIRED_HEADINGS:
            if heading not in explanation:
                errors.append(
                    f"Record {record}: Missing heading {heading}."
                )

        # Check word count.
        word_count = len(explanation.split())

        if word_count > MAX_WORDS:
            warnings.append(
                f"Record {record}: Explanation contains "
                f"{word_count} words (limit: {MAX_WORDS})."
            )

    return errors, warnings


def main():
    with MINED_FILE.open("r", encoding="utf-8") as file:
        mined_patterns = json.load(file)

    with EXPLANATIONS_FILE.open("r", encoding="utf-8") as file:
        explanations = json.load(file)

    errors, warnings = validate_explanations(
        mined_patterns,
        explanations
    )

    print("=" * 45)
    print("LLM EXPLANATION VALIDATION")
    print("=" * 45)

    print("Explanations checked:", len(explanations))
    print("Validation errors:", len(errors))
    print("Warnings:", len(warnings))

    for error in errors:
        print("ERROR:", error)

    for warning in warnings:
        print("WARNING:", warning)

    if errors:
        print("\nValidation failed.")
    else:
        print("\nStructural validation passed.")

    print("=" * 45)


if __name__ == "__main__":
    main()
