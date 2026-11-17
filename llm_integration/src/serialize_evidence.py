
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = PROJECT_ROOT / "llm_integration" / "data" / "raw" / "miner_output.txt"
OUTPUT_FILE = PROJECT_ROOT / "llm_integration" / "data" / "processed" / "mined_patterns.json"


def split_top_level(expression):
    """Split an S-expression into fields, respecting nested parentheses."""
    items = []
    depth = 0
    start = None

    for index, char in enumerate(expression):
        if char.isspace() and depth == 0:
            if start is not None:
                items.append(expression[start:index])
                start = None
            continue

        if start is None:
            start = index

        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

    if start is not None:
        items.append(expression[start:])

    return items


def extract_patterns(input_file):
    patterns = []

    with input_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line.startswith("(CollectedPattern ") or not line.endswith(")"):
                continue

            fields = split_top_level(line[1:-1])

            if len(fields) != 4 or fields[0] != "CollectedPattern":
                continue

            pattern = fields[1]
            support = fields[2]
            matches_expression = fields[3]

            if not support.isdigit():
                continue

            evidence = []
            if matches_expression.startswith("(") and matches_expression.endswith(")"):
                evidence = split_top_level(matches_expression[1:-1])

            patterns.append({
                "pattern": pattern,
                "reported_support": int(support),
                "evidence": evidence,
                "source_line": line_number
            })

    return patterns


def main():
    patterns = extract_patterns(INPUT_FILE)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(patterns, file, indent=4)

    print(f"Extracted patterns: {len(patterns)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
