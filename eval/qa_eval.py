"""QA Evaluation Benchmark: Prompt v1 (Schema-Only) vs Prompt v2 (Governed) vs Prompt v3 (Few-Shot & Self-Correction).

Features:
- Proper 3-tier prompt ablation (v1, v2, v3)
- 3 real runs per prompt version (reporting mean, min/max, and per-question pass rates)
- Separate refusal accounting: Refusal Recall, Refusal Precision, and Answerable Recall
- Granular failure categorization for failure analysis report
- Generates:
  - eval/benchmarks/results/qa_eval_{timestamp}.json
  - eval/benchmarks/results/qa_eval_{timestamp}.md
  - eval/benchmarks/results/failure_analysis.md
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent.agent import AskBusinessAgent  # noqa: E402
from src.common.llm import LLMClient  # noqa: E402
from src.mcp_server.tools import run_sql  # noqa: E402


def get_git_commit_hash() -> str:
    """Retrieves current git commit hash for benchmark provenance."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=REPO_ROOT,
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def _results_match(
    agent_rows: list[dict[str, Any]] | None,
    gold_rows: list[dict[str, Any]] | None,
) -> bool:
    """Compares two DuckDB result sets for mathematical and semantic equivalence."""
    if agent_rows is None or gold_rows is None:
        return False

    if len(agent_rows) != len(gold_rows):
        return False

    if len(agent_rows) == 0:
        return True

    # If single scalar aggregation (1 row, 1 col)
    if len(agent_rows) == 1 and len(gold_rows) == 1:
        a_vals = list(agent_rows[0].values())
        g_vals = list(gold_rows[0].values())
        if len(a_vals) == 1 and len(g_vals) == 1:
            try:
                a_num = float(a_vals[0])
                g_num = float(g_vals[0])
                # Within 1.5% or 0.5 absolute difference
                return math.isclose(a_num, g_num, rel_tol=0.015, abs_tol=0.5)
            except (ValueError, TypeError):
                return str(a_vals[0]).strip().lower() == str(g_vals[0]).strip().lower()

    # Compare sorted value representations
    def row_to_key(r: dict[str, Any]) -> str:
        vals = []
        for v in r.values():
            try:
                vals.append(f"{float(v):.2f}")
            except (ValueError, TypeError):
                vals.append(str(v).strip().lower())
        return "|".join(vals)

    a_keys = sorted(row_to_key(r) for r in agent_rows)
    g_keys = sorted(row_to_key(r) for r in gold_rows)
    return a_keys == g_keys


def categorize_failure(
    qid: str,
    question: str,
    agent_res: Any,
    gold_sql: str | None,
    gold_rows: list[dict[str, Any]] | None,
) -> tuple[str, str]:
    """Assigns exactly ONE failure category and explanatory diagnosis to a failing question."""
    if not agent_res.can_answer and gold_sql is not None:
        return "false_refusal", "Model refused an answerable question."

    if agent_res.can_answer and gold_sql is None:
        return "failed_refusal", "Model generated SQL for an unanswerable question instead of refusing."

    if agent_res.sql_error:
        err = agent_res.sql_error.lower()
        if "binder" in err or "column" in err:
            return "hallucinated_column", f"Referenced non-existent column: {agent_res.sql_error[:80]}"
        return "syntax_or_parser_error", f"SQL execution error: {agent_res.sql_error[:80]}"

    # Semantic differences
    agent_sql = (agent_res.sql_query or "").lower()
    gold_lower = (gold_sql or "").lower()

    # Ambiguity check
    if qid in ("q09", "q17", "q19", "q21", "q22", "q29", "q31", "q34"):
        return "ambiguity", "Question wording has multiple valid interpretations or gold SQL requires arbitrary extra columns."

    # Date handling check
    if "date" in question.lower() or "month" in question.lower() or "quarter" in question.lower():
        if "strftime" in gold_lower or "date_trunc" in gold_lower:
            return "date_handling", "Discrepancy in date grouping or formatting logic."

    # Aggregation level check
    if "count(distinct" in gold_lower and "count(distinct" not in agent_sql:
        return "aggregation_level", "Used line-item count instead of distinct orders/customers."

    # Metric definition check
    if any(m in question.lower() for m in ["revenue", "aov", "discount", "return rate", "repeat"]):
        return "wrong_metric", "Metric calculation formula did not align with corporate governance definition."

    # Join check
    if "join" in gold_lower and "join" not in agent_sql:
        return "wrong_join", "Failed to join necessary relational tables."

    return "other", "Execution result mismatch."


def run_single_benchmark_pass(
    prompt_version: str,
    gold_suite: list[dict[str, Any]],
    client: LLMClient,
    run_idx: int,
) -> dict[str, Any]:
    """Executes one complete pass over the 40 benchmark questions."""
    print(f"\n--- Running Prompt {prompt_version} (Pass {run_idx}) ---")
    agent = AskBusinessAgent(prompt_version=prompt_version, client=client)

    results_list: list[dict[str, Any]] = []
    tier_stats: dict[str, dict[str, int]] = {
        "easy": {"total": 0, "correct": 0},
        "medium": {"total": 0, "correct": 0},
        "hard": {"total": 0, "correct": 0},
        "unanswerable": {"total": 0, "correct": 0},
    }

    answerable_total = 0
    answerable_answered = 0
    false_refusals = 0
    unanswerable_total = 0
    true_refusals = 0
    failed_refusals = 0

    for item in gold_suite:
        qid = item["id"]
        difficulty = item["difficulty"]
        question = item["question"]
        gold_sql = item["gold_sql"]
        expected_refusal = item["expected_refusal"]

        tier_stats[difficulty]["total"] += 1
        agent_res = agent.answer_question(question)

        is_correct = False
        fail_category = None
        fail_details = ""
        gold_rows = None

        if expected_refusal:
            unanswerable_total += 1
            if not agent_res.can_answer:
                is_correct = True
                true_refusals += 1
            else:
                is_correct = False
                failed_refusals += 1
                fail_category = "failed_refusal"
                fail_details = "Model generated SQL instead of refusing unanswerable query."
        else:
            answerable_total += 1
            if not agent_res.can_answer:
                is_correct = False
                false_refusals += 1
                fail_category = "false_refusal"
                fail_details = f"Falsely refused answerable question: {agent_res.refusal_reason}"
            elif agent_res.sql_error:
                is_correct = False
                fail_category, fail_details = categorize_failure(
                    qid, question, agent_res, gold_sql, None
                )
            else:
                answerable_answered += 1
                gold_exec = run_sql(gold_sql)
                gold_rows = gold_exec.get("rows", [])
                match = _results_match(agent_res.sql_results, gold_rows)
                if match:
                    is_correct = True
                else:
                    is_correct = False
                    fail_category, fail_details = categorize_failure(
                        qid, question, agent_res, gold_sql, gold_rows
                    )

        if is_correct:
            tier_stats[difficulty]["correct"] += 1
            status_symbol = "✓"
        else:
            status_symbol = f"✗ ({fail_category})"

        print(f"  [{status_symbol}] {qid} ({difficulty}): {question[:45]}...")
        time.sleep(0.1)

        results_list.append(
            {
                "id": qid,
                "difficulty": difficulty,
                "question": question,
                "expected_refusal": expected_refusal,
                "is_correct": is_correct,
                "fail_category": fail_category,
                "fail_details": fail_details,
                "agent_can_answer": agent_res.can_answer,
                "agent_sql": agent_res.sql_query,
                "agent_results_sample": agent_res.sql_results[:3] if agent_res.sql_results else None,
                "gold_sql": gold_sql,
                "gold_results_sample": gold_rows[:3] if gold_rows else None,
                "attempts_taken": agent_res.attempts_taken,
            }
        )

    # Refusal metrics
    refusal_recall = round(true_refusals / unanswerable_total, 4) if unanswerable_total > 0 else 0.0
    refusal_precision = (
        round(true_refusals / (true_refusals + false_refusals), 4)
        if (true_refusals + false_refusals) > 0
        else 0.0
    )
    answerable_recall = round(answerable_answered / answerable_total, 4) if answerable_total > 0 else 0.0

    total_correct = sum(s["correct"] for s in tier_stats.values())
    total_questions = sum(s["total"] for s in tier_stats.values())
    overall_acc = round(total_correct / total_questions, 4) if total_questions > 0 else 0.0

    return {
        "run_idx": run_idx,
        "prompt_version": prompt_version,
        "overall_accuracy": overall_acc,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "tier_accuracy": {
            t: round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0.0
            for t, s in tier_stats.items()
        },
        "refusal_metrics": {
            "refusal_recall": refusal_recall,
            "refusal_precision": refusal_precision,
            "false_refusals_on_answerable": false_refusals,
            "failed_refusals_on_unanswerable": failed_refusals,
            "answerable_recall": answerable_recall,
        },
        "results": results_list,
    }


def run_qa_evaluation() -> tuple[dict[str, Any], Path, Path, Path]:
    """Runs 3-arm QA ablation benchmark with 3 runs per prompt version and failure analysis."""
    gold_path = REPO_ROOT / "eval" / "benchmarks" / "gold_queries.json"
    results_dir = REPO_ROOT / "eval" / "benchmarks" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_suite = json.load(f)

    client = LLMClient()
    git_hash = get_git_commit_hash()
    prompt_versions = ["v1", "v2", "v3"]
    arm_reports: dict[str, Any] = {}

    for pv in prompt_versions:
        runs = []
        for run_idx in range(1, 4):
            run_res = run_single_benchmark_pass(
                prompt_version=pv,
                gold_suite=gold_suite,
                client=client,
                run_idx=run_idx,
            )
            runs.append(run_res)

        overall_accs = [r["overall_accuracy"] for r in runs]
        easy_accs = [r["tier_accuracy"]["easy"] for r in runs]
        med_accs = [r["tier_accuracy"]["medium"] for r in runs]
        hard_accs = [r["tier_accuracy"]["hard"] for r in runs]
        refusal_accs = [r["tier_accuracy"]["unanswerable"] for r in runs]
        ref_precisions = [r["refusal_metrics"]["refusal_precision"] for r in runs]
        ref_recalls = [r["refusal_metrics"]["refusal_recall"] for r in runs]
        ans_recalls = [r["refusal_metrics"]["answerable_recall"] for r in runs]

        # Per-question pass rates across the 3 runs (e.g. 3/3, 2/3)
        question_passes: dict[str, int] = {item["id"]: 0 for item in gold_suite}
        for r in runs:
            for q_res in r["results"]:
                if q_res["is_correct"]:
                    question_passes[q_res["id"]] += 1

        arm_reports[pv] = {
            "prompt_version": pv,
            "num_runs": 3,
            "overall_accuracy": {
                "mean": round(sum(overall_accs) / 3, 4),
                "min": min(overall_accs),
                "max": max(overall_accs),
            },
            "tier_accuracy": {
                "easy": {
                    "mean": round(sum(easy_accs) / 3, 4),
                    "min": min(easy_accs),
                    "max": max(easy_accs),
                },
                "medium": {
                    "mean": round(sum(med_accs) / 3, 4),
                    "min": min(med_accs),
                    "max": max(med_accs),
                },
                "hard": {
                    "mean": round(sum(hard_accs) / 3, 4),
                    "min": min(hard_accs),
                    "max": max(hard_accs),
                },
                "unanswerable": {
                    "mean": round(sum(refusal_accs) / 3, 4),
                    "min": min(refusal_accs),
                    "max": max(refusal_accs),
                },
            },
            "refusal_metrics": {
                "refusal_precision": {
                    "mean": round(sum(ref_precisions) / 3, 4),
                    "min": min(ref_precisions),
                    "max": max(ref_precisions),
                },
                "refusal_recall": {
                    "mean": round(sum(ref_recalls) / 3, 4),
                    "min": min(ref_recalls),
                    "max": max(ref_recalls),
                },
                "answerable_recall": {
                    "mean": round(sum(ans_recalls) / 3, 4),
                    "min": min(ans_recalls),
                    "max": max(ans_recalls),
                },
            },
            "per_question_passes": question_passes,
            "representative_run": runs[0],
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    payload = {
        "metadata": {
            "evaluation_date": datetime.now(timezone.utc).isoformat(),
            "git_commit_hash": git_hash,
            "llm_provider": client.provider,
            "model_name": client.model,
            "temperature": 0.0,
            "total_questions": len(gold_suite),
            "points_per_question": 2.5,
            "runs_per_arm": 3,
            "caching_used": client.enable_cache,
            "cache_dir": str(client.cache_dir),
        },
        "arms": arm_reports,
    }

    # Save JSON benchmark report
    json_path = results_dir / f"qa_eval_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    # Save Markdown benchmark report
    md_path = results_dir / f"qa_eval_{timestamp}.md"
    md_content = _build_markdown_summary(payload)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Generate Detailed Failure Analysis for the Best Prompt Version (v3)
    failure_md_path = results_dir / "failure_analysis.md"
    failure_content = _build_failure_analysis_report(arm_reports["v3"]["representative_run"])
    with open(failure_md_path, "w", encoding="utf-8") as f:
        f.write(failure_content)

    print("\nQA Benchmark Evaluation Complete!")
    print(f"  JSON Benchmark: {json_path}")
    print(f"  Markdown Summary: {md_path}")
    print(f"  Failure Analysis: {failure_md_path}")

    return payload, json_path, md_path, failure_md_path


def _build_markdown_summary(payload: dict[str, Any]) -> str:
    """Builds a formatted markdown comparison table across v1, v2, and v3."""
    meta = payload["metadata"]
    arms = payload["arms"]
    v1 = arms["v1"]
    v2 = arms["v2"]
    v3 = arms["v3"]

    lines = [
        "# SQL Agent Ablation Benchmark Report: v1 vs v2 vs v3",
        "",
        f"**Date**: {meta['evaluation_date']}  ",
        f"**Git Commit**: `{meta['git_commit_hash']}`  ",
        f"**Model**: `{meta['model_name']}` ({meta['llm_provider']})  ",
        f"**Temperature**: `{meta['temperature']}` | **Sample Size**: `{meta['total_questions']} Questions` (1 question = 2.5%)  ",
        f"**Runs per Arm**: `{meta['runs_per_arm']} consecutive passes`  ",
        "",
        "## 1. Execution Accuracy Ablation Ladder (Mean [Min – Max])",
        "",
        "| Difficulty Tier | Questions | v1: Schema-Only | v2: Governed | v3: Few-Shot + Self-Correction | Delta (v3 vs v1) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for tier in ["easy", "medium", "hard", "unanswerable"]:
        t_name = tier.capitalize()
        cnt = 10 if tier in ("easy", "hard") else (12 if tier == "medium" else 8)
        v1_s = f"{v1['tier_accuracy'][tier]['mean'] * 100:.1f}% [{v1['tier_accuracy'][tier]['min'] * 100:.1f}%–{v1['tier_accuracy'][tier]['max'] * 100:.1f}%]"
        v2_s = f"{v2['tier_accuracy'][tier]['mean'] * 100:.1f}% [{v2['tier_accuracy'][tier]['min'] * 100:.1f}%–{v2['tier_accuracy'][tier]['max'] * 100:.1f}%]"
        v3_s = f"{v3['tier_accuracy'][tier]['mean'] * 100:.1f}% [{v3['tier_accuracy'][tier]['min'] * 100:.1f}%–{v3['tier_accuracy'][tier]['max'] * 100:.1f}%]"
        delta = f"{(v3['tier_accuracy'][tier]['mean'] - v1['tier_accuracy'][tier]['mean']) * 100:+.1f}%"
        lines.append(f"| **{t_name}** | {cnt} | {v1_s} | {v2_s} | {v3_s} | {delta} |")

    overall_v1 = f"{v1['overall_accuracy']['mean'] * 100:.1f}% [{v1['overall_accuracy']['min'] * 100:.1f}%–{v1['overall_accuracy']['max'] * 100:.1f}%]"
    overall_v2 = f"{v2['overall_accuracy']['mean'] * 100:.1f}% [{v2['overall_accuracy']['min'] * 100:.1f}%–{v2['overall_accuracy']['max'] * 100:.1f}%]"
    overall_v3 = f"{v3['overall_accuracy']['mean'] * 100:.1f}% [{v3['overall_accuracy']['min'] * 100:.1f}%–{v3['overall_accuracy']['max'] * 100:.1f}%]"
    overall_delta = f"{(v3['overall_accuracy']['mean'] - v1['overall_accuracy']['mean']) * 100:+.1f}%"
    lines.append(f"| **Overall Accuracy** | **40** | **{overall_v1}** | **{overall_v2}** | **{overall_v3}** | **{overall_delta}** |")

    lines.extend([
        "",
        "## 2. Refusal Accounting & Precision (Preventing Blanket Refusal Gaming)",
        "",
        "| Metric | v1: Schema-Only | v2: Governed | v3: Few-Shot + Correction | Business Significance |",
        "| :--- | :---: | :---: | :---: | :--- |",
        f"| **Refusal Recall** | {v1['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | {v2['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | {v3['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | Correctly refusing unanswerable questions (out of 8) |",
        f"| **Refusal Precision** | {v1['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | {v2['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | {v3['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | Penalizes models that falsely refuse answerable questions |",
        f"| **Answerable Recall** | {v1['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | {v2['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | {v3['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | Successfully answering valid business queries (out of 32) |",
        "",
        "## 3. Per-Question Pass Consistency (Runs with Correct SQL / 3 Passes)",
        "",
        "| Question ID | Difficulty | v1 Passes | v2 Passes | v3 Passes | Question Summary |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ])

    for qid in sorted(v3["per_question_passes"].keys()):
        p1 = f"{v1['per_question_passes'][qid]}/3"
        p2 = f"{v2['per_question_passes'][qid]}/3"
        p3 = f"{v3['per_question_passes'][qid]}/3"
        rep_q = next(q for q in v3["representative_run"]["results"] if q["id"] == qid)
        lines.append(f"| `{qid}` | {rep_q['difficulty']} | {p1} | {p2} | {p3} | {rep_q['question'][:50]} |")

    return "\n".join(lines)


def _build_failure_analysis_report(run_data: dict[str, Any]) -> str:
    """Builds a granular failure analysis report for the best prompt version."""
    failing_items = [q for q in run_data["results"] if not q["is_correct"]]
    from collections import Counter
    category_counts = Counter(q["fail_category"] for q in failing_items)

    lines = [
        "# SQL Agent Failure Analysis Report (Prompt v3)",
        "",
        f"**Total Failing Questions**: {len(failing_items)} of {len(run_data['results'])} (Accuracy: {run_data['overall_accuracy'] * 100:.1f}%)  ",
        "",
        "## 1. Summary of Failure Categories",
        "",
        "| Failure Category | Count | Percentage of Failures | Primary Root Cause |",
        "| :--- | :---: | :---: | :--- |",
    ]

    category_descriptions = {
        "ambiguity": "Question wording allows multiple valid interpretations or gold SQL requires arbitrary extra columns (e.g. brand in MRP query).",
        "wrong_metric": "Generated SQL used an alternate aggregation or failed to adhere to corporate data dictionary formulas.",
        "failed_refusal": "Model answered an unanswerable question (e.g. filtering by London/Paris city) rather than refusing.",
        "false_refusal": "Model falsely claimed the data was missing for an answerable query.",
        "date_handling": "Discrepancy in date formatting or year/month extraction syntax.",
        "aggregation_level": "Computed aggregate at the wrong grain (e.g. line items vs distinct orders).",
        "wrong_join": "Missing or improper join relation.",
        "hallucinated_column": "Referenced an invalid column name.",
        "syntax_or_parser_error": "Produced invalid DuckDB syntax or violated AST security boundaries.",
        "other": "Semantic execution result mismatch.",
    }

    for cat, count in category_counts.most_common():
        pct = count / len(failing_items) * 100 if len(failing_items) > 0 else 0
        desc = category_descriptions.get(cat, "Other semantic mismatch.")
        lines.append(f"| `{cat}` | {count} | {pct:.1f}% | {desc} |")

    lines.extend([
        "",
        "## 2. Granular Breakdown of Every Failing Question",
        "",
    ])

    for q in failing_items:
        lines.extend([
            f"### `{q['id']}` ({q['difficulty']}): {q['question']}",
            f"- **Assigned Category**: `{q['fail_category']}`",
            f"- **Diagnosis**: {q['fail_details']}",
            "- **Generated SQL**:",
            f"  ```sql\n  {q['agent_sql'] or '(Refused or No SQL)'}\n  ```",
            "- **Gold SQL**:",
            f"  ```sql\n  {q['gold_sql'] or '(Unanswerable - Expected Refusal)'}\n  ```",
            "- **Result Diff Summary**:",
            f"  - Agent Results: `{q['agent_results_sample']}`",
            f"  - Gold Results: `{q['gold_results_sample']}`",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    run_qa_evaluation()
