
import json
import re
from pathlib import Path


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

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


# --------------------------------------------------
# METTA EXPRESSION PARSER
# --------------------------------------------------

def parse_metta(expression):
    """
    Parse a simple MeTTa S-expression into nested lists.
    """

    tokens = re.findall(r"\(|\)|[^\s()]+", expression)

    stack = []
    current = []

    for token in tokens:

        if token == "(":

            new_list = []
            current.append(new_list)
            stack.append(current)
            current = new_list

        elif token == ")":

            if not stack:
                raise ValueError(
                    "Unbalanced closing parenthesis."
                )

            current = stack.pop()

        else:
            current.append(token)

    if stack:
        raise ValueError(
            "Unbalanced opening parenthesis."
        )

    if len(current) != 1:
        raise ValueError(
            "Invalid MeTTa expression."
        )

    return current[0]


# --------------------------------------------------
# PATTERN MATCHING AND VARIABLE UNIFICATION
# --------------------------------------------------

def unify_pattern(pattern, evidence, bindings=None):
    """
    Check whether evidence matches a pattern.

    Repeated variables must have consistent bindings.

    Different variables may have identical values.
    """

    if bindings is None:
        bindings = {}

    # Handle symbols and variables.
    if isinstance(pattern, str):

        # Recognize miner-style variables such as $_0.
        if pattern.startswith("$_"):

            if pattern in bindings:

                return (
                    bindings[pattern] == evidence,
                    bindings
                )

            bindings[pattern] = evidence

            return True, bindings

        # Fixed symbols must match exactly.
        return pattern == evidence, bindings

    # Expressions must have matching structures.
    if not isinstance(evidence, list):
        return False, bindings

    if len(pattern) != len(evidence):
        return False, bindings

    for pattern_part, evidence_part in zip(
        pattern,
        evidence
    ):

        valid, bindings = unify_pattern(
            pattern_part,
            evidence_part,
            bindings
        )

        if not valid:
            return False, bindings

    return True, bindings


# --------------------------------------------------
# VARIABLE-BINDING ANALYSIS
# --------------------------------------------------

def inspect_variable_bindings(
    pattern_text,
    evidence_sample
):
    """
    Inspect positions where one predicate contains
    a variable and the corresponding predicate
    contains a fixed symbol.

    Report when the variable binds to that symbol
    in the supplied evidence sample.
    """

    observations = []

    try:
        pattern = parse_metta(pattern_text)

    except ValueError:
        return observations

    # This analysis currently handles two-predicate
    # conjunction patterns.
    if (
        not isinstance(pattern, list)
        or len(pattern) != 3
        or pattern[0] != ","
    ):
        return observations

    left = pattern[1]
    right = pattern[2]

    if (
        not isinstance(left, list)
        or not isinstance(right, list)
        or len(left) != len(right)
    ):
        return observations

    # Examine corresponding argument positions.
    for position in range(1, len(left)):

        left_arg = left[position]
        right_arg = right[position]

        variable = None
        fixed_symbol = None

        if (
            isinstance(left_arg, str)
            and left_arg.startswith("$_")
            and isinstance(right_arg, str)
            and not right_arg.startswith("$_")
        ):

            variable = left_arg
            fixed_symbol = right_arg

        elif (
            isinstance(right_arg, str)
            and right_arg.startswith("$_")
            and isinstance(left_arg, str)
            and not left_arg.startswith("$_")
        ):

            variable = right_arg
            fixed_symbol = left_arg

        if variable is None:
            continue

        matching_count = 0

        for evidence_text in evidence_sample:

            try:

                evidence = parse_metta(evidence_text)

                valid, bindings = unify_pattern(
                    pattern,
                    evidence
                )

                if (
                    valid
                    and bindings.get(variable) == fixed_symbol
                ):
                    matching_count += 1

            except ValueError:
                continue

        if matching_count:

            observations.append(
                f"{variable} binds to {fixed_symbol} "
                f"in {matching_count} sampled record(s)."
            )

    return observations


# --------------------------------------------------
# EXPLANATION VALIDATION
# --------------------------------------------------

def validate_explanations(
    mined_patterns,
    explanations
):

    errors = []
    warnings = []
    observations = []

    if not isinstance(mined_patterns, list):

        return (
            ["Mined patterns must be a JSON list."],
            warnings,
            observations
        )

    if not isinstance(explanations, list):

        return (
            ["Explanations must be a JSON list."],
            warnings,
            observations
        )

    # Index original miner records by pattern.
    mined_by_pattern = {
        item["pattern"]: item
        for item in mined_patterns
        if (
            isinstance(item, dict)
            and isinstance(item.get("pattern"), str)
        )
    }

    # Process every explanation.
    for index, result in enumerate(
        explanations,
        start=1
    ):

        record = index

        if not isinstance(result, dict):

            errors.append(
                f"Record {record}: Invalid explanation format."
            )

            continue

        # Required output fields.
        required_fields = [
            "pattern",
            "reported_support",
            "total_evidence_count",
            "evidence_sample_count",
            "evidence_sample",
            "explanation"
        ]

        missing = [
            field
            for field in required_fields
            if field not in result
        ]

        if missing:

            errors.append(
                f"Record {record}: Missing fields: {missing}"
            )

            continue

        pattern_text = result["pattern"]

        if not isinstance(pattern_text, str):

            errors.append(
                f"Record {record}: Pattern must be a string."
            )

            continue

        # Find original miner record.
        if pattern_text not in mined_by_pattern:

            errors.append(
                f"Record {record}: Pattern not found "
                "in miner output."
            )

            continue

        original = mined_by_pattern[pattern_text]

        # Check reported support.
        if (
            result["reported_support"]
            != original["reported_support"]
        ):

            errors.append(
                f"Record {record}: Reported support "
                "does not match original miner output."
            )

        # Check total evidence count.
        original_evidence = original["evidence"]

        if not isinstance(original_evidence, list):

            errors.append(
                f"Record {record}: Original evidence "
                "must be a list."
            )

            continue

        if (
            result["total_evidence_count"]
            != len(original_evidence)
        ):

            errors.append(
                f"Record {record}: Total evidence "
                "count mismatch."
            )

        # Check evidence sample.
        sample = result["evidence_sample"]

        if not isinstance(sample, list):

            errors.append(
                f"Record {record}: Evidence sample "
                "must be a list."
            )

            continue

        if (
            result["evidence_sample_count"]
            != len(sample)
        ):

            errors.append(
                f"Record {record}: Evidence sample "
                "count mismatch."
            )

        # Check sampled records against original evidence.
        original_evidence_set = set(original_evidence)

        for evidence_text in sample:

            if not isinstance(evidence_text, str):

                errors.append(
                    f"Record {record}: Evidence sample "
                    "contains a non-string entry."
                )

                break

            if evidence_text not in original_evidence_set:

                errors.append(
                    f"Record {record}: Evidence sample "
                    "contains a record absent from "
                    "original miner evidence."
                )

                break

        # Parse the pattern.
        try:

            parsed_pattern = parse_metta(pattern_text)

        except ValueError as error:

            errors.append(
                f"Record {record}: Invalid pattern: {error}"
            )

            continue

        # Check that each sample matches the pattern.
        for evidence_text in sample:

            try:

                parsed_evidence = parse_metta(evidence_text)

                valid, _ = unify_pattern(
                    parsed_pattern,
                    parsed_evidence
                )

                if not valid:

                    errors.append(
                        f"Record {record}: Evidence sample "
                        "does not match the mined pattern."
                    )

                    break

            except ValueError as error:

                errors.append(
                    f"Record {record}: Invalid evidence "
                    f"expression: {error}"
                )

                break

        # Analyze variable bindings.
        binding_observations = inspect_variable_bindings(
            pattern_text,
            sample
        )

        for observation in binding_observations:

            observations.append(
                f"Record {record}: {observation}"
            )

        # Check explanation.
        explanation = result["explanation"]

        if not isinstance(explanation, str):

            errors.append(
                f"Record {record}: Explanation "
                "must be a string."
            )

            continue

        # Check required headings.
        for heading in REQUIRED_HEADINGS:

            if heading not in explanation:

                errors.append(
                    f"Record {record}: Missing heading "
                    f"{heading}."
                )

        # Word count warning only.
        word_count = len(explanation.split())

        if word_count > MAX_WORDS:

            warnings.append(
                f"Record {record}: Explanation contains "
                f"{word_count} words "
                f"(guideline: {MAX_WORDS})."
            )

    return errors, warnings, observations


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    # Load original miner output.
    with MINED_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        mined_patterns = json.load(file)

    # Load LLM explanations.
    with EXPLANATIONS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        explanations = json.load(file)

    # Run validation.
    errors, warnings, observations = validate_explanations(
        mined_patterns,
        explanations
    )

    # Display results.
    print("=" * 50)
    print("LLM EXPLANATION VALIDATION")
    print("=" * 50)

    print(
        "Explanations checked:",
        len(explanations)
    )

    print(
        "Validation errors:",
        len(errors)
    )

    print(
        "Warnings:",
        len(warnings)
    )

    # Errors.
    for error in errors:
        print("ERROR:", error)

    # Warnings.
    for warning in warnings:
        print("WARNING:", warning)

    # Variable-binding observations.
    print("\nVARIABLE-BINDING OBSERVATIONS")

    if observations:

        for observation in observations:
            print("INFO:", observation)

    else:
        print("No variable-to-fixed-symbol bindings observed.")

    # Final status.
    if errors:

        print("\nValidation failed.")

    else:

        print("\nStructural and evidence validation passed.")

    print("=" * 50)


if __name__ == "__main__":
    main()
