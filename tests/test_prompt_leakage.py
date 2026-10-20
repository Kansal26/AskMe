"""Tests ensuring few-shot prompt examples do not duplicate or paraphrase benchmark evaluation questions."""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from src.agent.prompts import PROMPT_V3_FEWSHOT_AND_CORRECTION

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_fewshot_examples_do_not_duplicate_or_paraphrase_eval_questions():
    """Asserts that all worked examples in Prompt v3 have low similarity (< 0.60) to all eval questions."""
    gold_path = REPO_ROOT / "eval" / "benchmarks" / "gold_queries.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_suite = json.load(f)

    # Extract all Question: "..." lines from the prompt
    example_questions = re.findall(r'Question:\s*"([^"]+)"', PROMPT_V3_FEWSHOT_AND_CORRECTION)
    assert len(example_questions) >= 4, f"Expected at least 4 worked examples, found {len(example_questions)}"

    # Compare each example against all 40 gold questions
    SIMILARITY_THRESHOLD = 0.60

    for ex_idx, example_q in enumerate(example_questions, 1):
        for gold_item in gold_suite:
            gold_q = gold_item["question"]
            qid = gold_item["id"]

            similarity = SequenceMatcher(None, example_q.lower(), gold_q.lower()).ratio()

            assert similarity < SIMILARITY_THRESHOLD, (
                f"Prompt Leakage Detected! Example {ex_idx} ('{example_q}') has high similarity "
                f"({similarity:.2f} >= {SIMILARITY_THRESHOLD}) with eval question {qid} ('{gold_q}')"
            )
