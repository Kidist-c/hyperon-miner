
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPLANATIONS_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "output"
    / "explanations.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "llm_integration"
    / "output"
    / "claim_review.json"
)

RISK_RULES = {
    "Causal interpretation": [
        r"\bcauses?\b",
        r"\bbecause of\b",
        r"\bleads? to\b",
        r"\bresults? in\b",
        r"\bdue to\b"
    ],

    "Hierarchy interpretation": [
        r"\bhierarchy\b",
        r"\bsubclass\b",
        r"\bsuperclass\b",
        r"\binherits? from\b",
        r"\bparent class\b",
        r"\bchild class\b"
    ],

    "Unestablished semantic roles": [
        r"\bsubject\b",
        r"\btarget\b",
        r"\bproperty\b",
        r"\bcategory\b",
        r"\bclass membership\b"
    ],

    "Potentially misleading variable claims": [
        r"\bvariables? are distinct values\b",
        r"\bvariables? must be different\b",
        r"\bsecond arguments? (?:always )?differ\b",
        r"\bfirst arguments? (?:always )?differ\b",
        r"\bnecessarily different\b"
    ],

    "Unsupported universal claims": [
        r"\ball matches\b",
        r"\bevery match\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bwithout exception\b"
    ]
}


def is_safe_negated_statement(category, sentence):
    """
    Identify known safe limitation statements that deny
    unsupported semantic interpretations.

    These statements should not be flagged merely because
    they contain words such as 'hierarchy'.
    """

    normalized_sentence = sentence.lower()

    safe_phrases = {
        "Hierarchy interpretation": [
            "no specific semantic direction or hierarchy is implied",
            "no hierarchy is implied",
            "no hierarchy can be inferred",
            "does not imply a hierarchy",
            "cannot infer a hierarchy",
            "no hierarchical meaning is inferred",
            "no hierarchical meaning can be inferred"
        ],

        "Causal interpretation": [
            "no causal relationship is implied",
            "no causal relationship can be inferred",
            "no causal meaning is inferred",
            "no causal meaning can be inferred",
            "does not imply causation",
            "cannot infer causation"
        ]
    }

    phrases = safe_phrases.get(category, [])

    return any(
        phrase in normalized_sentence
        for phrase in phrases
    )


def extract_sentence(text, match):
    """
    Extract the sentence containing a matched phrase.
    """

    start = max(
        text.rfind(".", 0, match.start()),
        text.rfind("\n", 0, match.start())
    ) + 1

    sentence_end = text.find(".", match.end())

    if sentence_end == -1:
        sentence_end = len(text)

    return text[start:sentence_end].strip()


def review_explanation(explanation):
    """
    Scan an explanation for potentially risky claims.

    Findings are heuristic indicators for human review.
    They do not prove that a statement is incorrect.
    """

    findings = []

    if not isinstance(explanation, str):
        return [{
            "category": "Invalid explanation",
            "claim": "Explanation is not a string."
        }]

    for category, patterns in RISK_RULES.items():

        for pattern in patterns:

            matches = re.finditer(
                pattern,
                explanation,
                flags=re.IGNORECASE
            )

            for match in matches:

                sentence = extract_sentence(
                    explanation,
                    match
                )

                # Skip known safe negated statements.
                if is_safe_negated_statement(
                    category,
                    sentence
                ):
                    continue

                findings.append({
                    "category": category,
                    "matched_text": match.group(0),
                    "sentence": sentence
                })

    return findings


def main():

    if not EXPLANATIONS_FILE.exists():
        print("ERROR: Explanations file not found:")
        print(EXPLANATIONS_FILE)
        return

    with EXPLANATIONS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        explanations = json.load(file)

    review_results = []
    total_findings = 0

    for index, item in enumerate(
        explanations,
        start=1
    ):

        explanation = item.get(
            "explanation",
            ""
        )

        findings = review_explanation(
            explanation
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

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            review_results,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("=" * 50)
    print("LLM CLAIM REVIEW")
    print("=" * 50)

    print(
        "Explanations reviewed:",
        len(explanations)
    )

    print(
        "Potentially risky claims:",
        total_findings
    )

    for result in review_results:

        print("\nRecord:", result["record"])

        print(
            "Status:",
            result["review_status"]
        )

        for finding in result["findings"]:

            print(
                "WARNING:",
                finding["category"]
            )

            print(
                "Matched:",
                finding.get("matched_text", "")
            )

            print(
                "Sentence:",
                finding.get("sentence", "")
            )

    print("\nReview saved to:")
    print(OUTPUT_FILE)

    print("=" * 50)

    print(
        "Note: These are heuristic review flags, "
        "not proof of incorrect claims."
    )


if __name__ == "__main__":
    main()
