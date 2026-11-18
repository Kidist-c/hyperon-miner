
import json
from pathlib import Path

# Import existing project modules.
import serialize_evidence as serializer
import evidence_validator
import llm_explainer as explainer
import explanation_validator
import claim_reviewer


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MINER_OUTPUT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "data"
    / "raw"
    / "miner_output.txt"
)

MINED_PATTERNS_FILE = (
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

CLAIM_REVIEW_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "output"
    / "claim_review.json"
)


# --------------------------------------------------
# PIPELINE UTILITIES
# --------------------------------------------------

def print_stage(number, title):
    print("\n" + "=" * 60)
    print(f"STAGE {number}: {title}")
    print("=" * 60)


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# --------------------------------------------------
# STAGE 1: SERIALIZE MINER EVIDENCE
# --------------------------------------------------

def run_serialization():

    print_stage(1, "EVIDENCE SERIALIZATION")

    if not MINER_OUTPUT_FILE.exists():
        raise FileNotFoundError(
            f"Miner output not found: {MINER_OUTPUT_FILE}\n"
            "Run the original Hyperon miner first."
        )

    patterns = serializer.extract_patterns(
        MINER_OUTPUT_FILE
    )

    if not patterns:
        raise RuntimeError(
            "No patterns were extracted from miner output."
        )

    save_json(
        MINED_PATTERNS_FILE,
        patterns
    )

    print("Patterns extracted:", len(patterns))
    print("Saved to:", MINED_PATTERNS_FILE)

    return patterns


# --------------------------------------------------
# STAGE 2: VALIDATE MINER EVIDENCE
# --------------------------------------------------

def run_evidence_validation(patterns):

    print_stage(2, "EVIDENCE VALIDATION")

    errors = evidence_validator.validate_patterns(
        patterns
    )

    print("Patterns checked:", len(patterns))
    print("Validation errors:", len(errors))

    if errors:

        for error in errors:
            print("ERROR:", error)

        raise RuntimeError(
            "Evidence validation failed. "
            "LLM processing has been stopped."
        )

    print("Evidence validation passed.")

    return True


# --------------------------------------------------
# STAGE 3: GENERATE LLM EXPLANATIONS
# --------------------------------------------------

def run_explanation_generation(patterns):

    print_stage(3, "LLM EXPLANATION GENERATION")

    # Preserve any previous output in memory.
    previous_output = None

    if EXPLANATIONS_FILE.exists():

        previous_output = EXPLANATIONS_FILE.read_bytes()

        # Prevent an old result from being mistaken
        # for a newly generated explanation.
        EXPLANATIONS_FILE.unlink()

    try:

        explainer.main()

    except Exception:

        # Restore previous output if generation failed
        # before producing a new file.
        if (
            not EXPLANATIONS_FILE.exists()
            and previous_output is not None
        ):
            EXPLANATIONS_FILE.write_bytes(previous_output)

        raise

    if not EXPLANATIONS_FILE.exists():

        if previous_output is not None:
            EXPLANATIONS_FILE.write_bytes(previous_output)

        raise RuntimeError(
            "Explanation generation produced no output."
        )

    explanations = load_json(EXPLANATIONS_FILE)

    expected_count = min(
        len(patterns),
        explainer.MAX_PATTERNS
    )

    if len(explanations) != expected_count:

        raise RuntimeError(
            "Incomplete explanation generation. "
            f"Expected {expected_count}, "
            f"received {len(explanations)}. "
            "Check the Groq API output."
        )

    print("Explanations generated:", len(explanations))
    print("Saved to:", EXPLANATIONS_FILE)

    return explanations


# --------------------------------------------------
# STAGE 4: VALIDATE LLM EXPLANATIONS
# --------------------------------------------------

def run_explanation_validation(
    patterns,
    explanations
):

    print_stage(4, "EXPLANATION VALIDATION")

    errors, warnings, observations = (
        explanation_validator.validate_explanations(
            patterns,
            explanations
        )
    )

    print("Explanations checked:", len(explanations))
    print("Validation errors:", len(errors))
    print("Warnings:", len(warnings))

    for error in errors:
        print("ERROR:", error)

    for warning in warnings:
        print("WARNING:", warning)

    print("\nVARIABLE-BINDING OBSERVATIONS")

    if observations:

        for observation in observations:
            print("INFO:", observation)

    else:
        print("No variable-to-fixed-symbol bindings observed.")

    if errors:

        raise RuntimeError(
            "Explanation validation failed. "
            "Claim review has been stopped."
        )

    print("\nExplanation validation passed.")

    return True


# --------------------------------------------------
# STAGE 5: REVIEW POTENTIALLY RISKY CLAIMS
# --------------------------------------------------

def run_claim_review(explanations):

    print_stage(5, "LLM CLAIM REVIEW")

    review_results = []
    total_findings = 0

    for index, item in enumerate(
        explanations,
        start=1
    ):

        findings = claim_reviewer.review_explanation(
            item.get("explanation", "")
        )

        total_findings += len(findings)

        review_results.append({
            "record": index,
            "pattern": item.get("pattern"),
            "review_status": (
                "Needs human review"
                if findings
                else "No lexical risks detected"
            ),
            "findings": findings
        })

    save_json(
        CLAIM_REVIEW_FILE,
        review_results
    )

    print("Explanations reviewed:", len(explanations))
    print("Potentially risky claims:", total_findings)

    for result in review_results:

        print(
            f"\nRecord {result['record']}: "
            f"{result['review_status']}"
        )

        for finding in result["findings"]:

            print(
                "WARNING:",
                finding["category"]
            )

            print(
                "Sentence:",
                finding.get("sentence", "")
            )

    print("\nClaim review saved to:")
    print(CLAIM_REVIEW_FILE)

    print(
        "\nNote: Lexical findings are review indicators, "
        "not proof of incorrect claims."
    )

    return review_results


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

def main():

    print("\n")
    print("#" * 60)
    print("HYPERON MINER - EVIDENCE-GROUNDED LLM PIPELINE")
    print("#" * 60)

    try:

        # Stage 1
        patterns = run_serialization()

        # Stage 2
        run_evidence_validation(patterns)

        # Stage 3
        explanations = run_explanation_generation(
            patterns
        )

        # Stage 4
        run_explanation_validation(
            patterns,
            explanations
        )

        # Stage 5
        review_results = run_claim_review(
            explanations
        )

        # Final summary
        print("\n")
        print("#" * 60)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("#" * 60)

        print("Mined patterns:", len(patterns))
        print("Generated explanations:", len(explanations))

        print(
            "Claim review records:",
            len(review_results)
        )

        print("\nGenerated files:")
        print(MINED_PATTERNS_FILE)
        print(EXPLANATIONS_FILE)
        print(CLAIM_REVIEW_FILE)

        print("#" * 60)

    except Exception as error:

        print("\n")
        print("#" * 60)
        print("PIPELINE STOPPED")
        print("#" * 60)

        print("Reason:", error)

        print(
            "\nNo later pipeline stages will be executed "
            "after a failed stage."
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
