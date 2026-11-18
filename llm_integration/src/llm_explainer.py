
import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, APIStatusError


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

INPUT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "data"
    / "processed"
    / "mined_patterns.json"
)

PROMPT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "prompts"
    / "explanation_prompt.txt"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "output"
    / "explanations.json"
)

# LLM configuration
MODEL = "qwen/qwen3.8-27b"

MAX_PATTERNS = 3
MAX_EVIDENCE = 5
MAX_COMPLETION_TOKENS = 500

GENERATION_TEMPERATURE = 0

# Provenance configuration
PROMPT_VERSION = "1.0"
SAMPLING_STRATEGY = "distributed_evidence_sampling"


# --------------------------------------------------
# EVIDENCE SAMPLING
# --------------------------------------------------

def select_evidence_sample(evidence, limit):
    """
    Select a small sample distributed across the
    complete evidence list.

    Original evidence is not modified.
    """

    if len(evidence) <= limit:
        return evidence

    if limit <= 0:
        return []

    if limit == 1:
        return [evidence[0]]

    indices = [
        round(i * (len(evidence) - 1) / (limit - 1))
        for i in range(limit)
    ]

    return [evidence[i] for i in indices]


# --------------------------------------------------
# OUTPUT SAVING
# --------------------------------------------------

def save_results(results):
    """
    Save results after each successful explanation.
    """

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False
        )


# --------------------------------------------------
# PROMPT GENERATION
# --------------------------------------------------

def build_prompt(
    prompt_template,
    item,
    evidence_sample
):
    """
    Insert pattern information and sampled evidence
    into the explanation prompt.
    """

    prompt = prompt_template.replace(
        "{pattern}",
        item["pattern"]
    )

    prompt = prompt.replace(
        "{reported_support}",
        str(item["reported_support"])
    )

    prompt = prompt.replace(
        "{evidence_sample_count}",
        str(len(evidence_sample))
    )

    prompt = prompt.replace(
        "{total_evidence_count}",
        str(len(item["evidence"]))
    )

    prompt = prompt.replace(
        "{evidence_json}",
        json.dumps(
            evidence_sample,
            ensure_ascii=False,
            indent=2
        )
    )

    return prompt


# --------------------------------------------------
# PROVENANCE GENERATION
# --------------------------------------------------

def generate_provenance(
    prompt_template,
    evidence_sample
):
    """
    Record the configuration and source information
    used to generate an explanation.
    """

    prompt_hash = hashlib.sha256(
        prompt_template.encode("utf-8")
    ).hexdigest()

    return {
        "model": MODEL,

        "prompt_version": PROMPT_VERSION,

        "prompt_sha256": prompt_hash,

        "generation_timestamp_utc": (
            datetime.now(timezone.utc).isoformat()
        ),

        "sampling_strategy": SAMPLING_STRATEGY,

        "max_evidence": MAX_EVIDENCE,

        "actual_evidence_sample_count": len(
            evidence_sample
        ),

        "temperature": GENERATION_TEMPERATURE,

        "max_completion_tokens": MAX_COMPLETION_TOKENS
    }


# --------------------------------------------------
# MAIN EXPLANATION PIPELINE
# --------------------------------------------------

def main():

    # Load API key
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found in .env"
        )

    # Load mined patterns
    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        patterns = json.load(file)

    # Load explanation prompt
    with PROMPT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        prompt_template = file.read()

    # Select patterns
    items_to_explain = patterns[:MAX_PATTERNS]

    if not items_to_explain:
        print("No patterns found.")
        return

    # Initialize Groq
    client = Groq(api_key=api_key)

    results = []

    total_prompt_tokens = 0
    total_completion_tokens = 0

    print("=" * 50)
    print("HYPERON MINER - LLM EXPLANATION")
    print("=" * 50)

    print("Patterns selected:", len(items_to_explain))
    print("Maximum evidence per pattern:", MAX_EVIDENCE)
    print("Model:", MODEL)
    print("Prompt version:", PROMPT_VERSION)

    # Process patterns
    for index, item in enumerate(
        items_to_explain,
        start=1
    ):

        print("\n" + "-" * 50)

        print(
            f"Processing pattern {index}/"
            f"{len(items_to_explain)}"
        )

        # Select evidence sample
        evidence_sample = select_evidence_sample(
            item["evidence"],
            MAX_EVIDENCE
        )

        print(
            "Reported support:",
            item["reported_support"]
        )

        print(
            "Total evidence records:",
            len(item["evidence"])
        )

        print(
            "Evidence records sent:",
            len(evidence_sample)
        )

        # Build complete prompt
        prompt = build_prompt(
            prompt_template,
            item,
            evidence_sample
        )

        # Generate provenance metadata
        provenance = generate_provenance(
            prompt,
            evidence_sample
        )

        # Call Groq API
        try:

            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=GENERATION_TEMPERATURE,
                max_tokens=MAX_COMPLETION_TOKENS
            )

        except APIStatusError as error:

            print("\nGroq API error:")
            print(error)

            print(
                "Processing stopped. "
                "Previously saved results are preserved."
            )

            break

        except Exception as error:

            print("\nUnexpected error:")
            print(error)

            print(
                "Processing stopped. "
                "Previously saved results are preserved."
            )

            break

        # Extract explanation
        explanation = (
            response.choices[0].message.content or ""
        ).strip()

        if not explanation:
            print(
                "Empty explanation received. "
                "Skipping result."
            )
            continue

        # Store result with provenance
        result = {
            "pattern": item["pattern"],

            "reported_support": item["reported_support"],

            "total_evidence_count": len(
                item["evidence"]
            ),

            "evidence_sample_count": len(
                evidence_sample
            ),

            "evidence_sample": evidence_sample,

            "explanation": explanation,

            "provenance": provenance
        }

        results.append(result)

        # Track token usage
        if response.usage:

            total_prompt_tokens += (
                response.usage.prompt_tokens
            )

            total_completion_tokens += (
                response.usage.completion_tokens
            )

        # Save after every successful request
        save_results(results)

        print("\nExplanation generated successfully.")

        if response.usage:

            print(
                "Prompt tokens:",
                response.usage.prompt_tokens
            )

            print(
                "Completion tokens:",
                response.usage.completion_tokens
            )

        print("Provenance metadata recorded.")
        print("Result saved.")

    # Final summary
    print("\n" + "=" * 50)
    print("PROCESSING SUMMARY")
    print("=" * 50)

    print("Patterns selected:", len(items_to_explain))
    print("Patterns explained:", len(results))

    print(
        "Total prompt tokens:",
        total_prompt_tokens
    )

    print(
        "Total completion tokens:",
        total_completion_tokens
    )

    print(
        "Total tokens:",
        total_prompt_tokens + total_completion_tokens
    )

    print("\nOutput file:")
    print(OUTPUT_FILE)

    print("=" * 50)


if __name__ == "__main__":
    main()
