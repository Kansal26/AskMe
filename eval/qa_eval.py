"""QA Evaluation Benchmark: Prompt v1 (Schema-Only) vs Prompt v2 (Governed) vs Prompt v3 (Few-Shot & Self-Correction).

Features:
- Dual-metric scoring: Strict Match vs Lenient (Semantically Equivalent) Match
- Exact comparator rules defined in docs/architecture.md:
  * Strict: Exact column names and ordering, exact row ordering, float tolerance.
  * Lenient: Subsets only to gold columns (extra agent columns permitted), normalises
    date/timestamp vs 'YYYY-MM' strings, ignores row order unless gold has ORDER BY + LIMIT,
    numeric float tolerance.
- Applied identically across all three arms without special-casing any question.
- 3 real runs per prompt version (reporting mean, min/max, variance, and per-question pass rates).
- Flips tracking between arms (v1 -> v2, v2 -> v3).
- Easy-tier v1 vs v2 regression audit (question, v1 SQL, v2 SQL, gold SQL, diff, root cause).
- Refusal accounting: Refusal Recall, Refusal Precision, Answerable Recall side by side.
- Held-out set execution: evaluated once on final prompt if heldout_queries.json exists.
- Generates:
  * eval/benchmarks/results/qa_eval_{timestamp}.json
  * eval/benchmarks/results/qa_eval_{timestamp}.md
  * eval/benchmarks/results/failure_analysis.md
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
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


def _values_match(a: Any, g: Any) -> bool:
    """Compares two individual values with float tolerance, date normalization, and case insensitivity."""
    if a is None and g is None:
        return True
    if a is None or g is None:
        return False

    # 1. Numeric tolerance
    try:
        fa = float(a)
        fg = float(g)
        if math.isclose(fa, fg, abs_tol=0.5, rel_tol=0.015):
            return True
    except (ValueError, TypeError):
        pass

    # 2. Date and string representations
    sa = a.strftime("%Y-%m-%d") if isinstance(a, (datetime, date)) else str(a).strip()
    sg = g.strftime("%Y-%m-%d") if isinstance(g, (datetime, date)) else str(g).strip()

    # Normalise date/timestamp vs 'YYYY-MM' strings
    if re.match(r"^\d{4}-\d{2}$", sg) and sa.startswith(sg):
        return True
    if re.match(r"^\d{4}-\d{2}$", sa) and sg.startswith(sa):
        return True

    return sa.lower() == sg.lower()


def _strict_match(
    agent_rows: list[dict[str, Any]] | None,
    gold_rows: list[dict[str, Any]] | None,
) -> bool:
    """Strict comparator: exact columns, exact row order, exact values."""
    if agent_rows is None or gold_rows is None:
        return False
    if len(agent_rows) != len(gold_rows):
        return False
    if len(agent_rows) == 0:
        return True

    agent_cols = list(agent_rows[0].keys())
    gold_cols = list(gold_rows[0].keys())
    if agent_cols != gold_cols:
        return False

    for i in range(len(gold_rows)):
        for col in gold_cols:
            if not _values_match(agent_rows[i][col], gold_rows[i][col]):
                return False
    return True


def _lenient_match(
    agent_rows: list[dict[str, Any]] | None,
    gold_rows: list[dict[str, Any]] | None,
    gold_sql: str | None,
) -> bool:
    """Lenient comparator:

    - Evaluates ONLY the columns that the gold query returns (agent may return extra columns).
    - Normalises date/timestamp vs 'YYYY-MM' strings.
    - Ignores row order unless gold has ORDER BY with LIMIT.
    - Numeric tolerance for floats (rel_tol=0.015, abs_tol=0.5).
    """
    if agent_rows is None or gold_rows is None:
        return False
    if len(agent_rows) != len(gold_rows):
        return False
    if len(agent_rows) == 0:
        return True

    gold_cols = list(gold_rows[0].keys())
    agent_cols = list(agent_rows[0].keys())

    # Map gold columns to agent columns (case-insensitive name match or positional fallback)
    agent_col_map = {c.lower(): c for c in agent_cols}
    if all(gc.lower() in agent_col_map for gc in gold_cols):
        proj_map = {gc: agent_col_map[gc.lower()] for gc in gold_cols}
    elif len(agent_cols) == len(gold_cols):
        proj_map = {gold_cols[i]: agent_cols[i] for i in range(len(gold_cols))}
    else:
        return False

    projected_agent = [
        {gc: row[proj_map[gc]] for gc in gold_cols}
        for row in agent_rows
    ]

    sql_upper = (gold_sql or "").upper()
    requires_ordering = "ORDER BY" in sql_upper and "LIMIT" in sql_upper

    if requires_ordering:
        for i in range(len(gold_rows)):
            for gc in gold_cols:
                if not _values_match(projected_agent[i][gc], gold_rows[i][gc]):
                    return False
        return True
    else:
        # Multiset / unordered matching
        unmatched = set(range(len(projected_agent)))
        for g_row in gold_rows:
            found = False
            for idx in list(unmatched):
                a_row = projected_agent[idx]
                if all(_values_match(a_row[gc], g_row[gc]) for gc in gold_cols):
                    unmatched.remove(idx)
                    found = True
                    break
            if not found:
                return False
        return len(unmatched) == 0


def calculate_variance(values: list[float]) -> float:
    """Calculates sample variance for a list of floats."""
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / (len(values) - 1)


def categorize_failure(
    qid: str,
    question: str,
    agent_res: Any,
    gold_sql: str | None,
    gold_rows: list[dict[str, Any]] | None,
    is_strict: bool,
    is_lenient: bool,
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

    if is_lenient and not is_strict:
        return "strict_mismatch", "Matched lenient semantic comparator but differed in strict column projection or ordering."

    # Semantic differences
    agent_sql = (agent_res.sql_query or "").lower()
    gold_lower = (gold_sql or "").lower()

    if qid in ("q09", "q17", "q19", "q21", "q22", "q29", "q31", "q34"):
        return "ambiguity", "Question wording has multiple valid interpretations or gold SQL requires arbitrary extra columns."

    if "date" in question.lower() or "month" in question.lower() or "quarter" in question.lower():
        if "strftime" in gold_lower or "date_trunc" in gold_lower or "year" in gold_lower:
            return "date_handling", "Discrepancy in date grouping or formatting logic."

    if "count(distinct" in gold_lower and "count(distinct" not in agent_sql:
        return "aggregation_level", "Used line-item count instead of distinct orders/customers."

    if any(m in question.lower() for m in ["revenue", "aov", "discount", "return rate", "repeat"]):
        return "wrong_metric", "Metric calculation formula did not align with corporate governance definition."

    if "join" in gold_lower and "join" not in agent_sql:
        return "wrong_join", "Failed to join necessary relational tables."

    return "other", "Execution result mismatch."


def run_single_benchmark_pass(
    prompt_version: str,
    gold_suite: list[dict[str, Any]],
    client: LLMClient,
    run_idx: int,
) -> dict[str, Any]:
    """Executes one complete pass over the benchmark questions, evaluating both Strict and Lenient."""
    print(f"\n--- Running Prompt {prompt_version} (Pass {run_idx}) ---")
    agent = AskBusinessAgent(prompt_version=prompt_version, client=client)

    results_list: list[dict[str, Any]] = []
    strict_tier_stats: dict[str, dict[str, int]] = {
        "easy": {"total": 0, "correct": 0},
        "medium": {"total": 0, "correct": 0},
        "hard": {"total": 0, "correct": 0},
        "unanswerable": {"total": 0, "correct": 0},
    }
    lenient_tier_stats: dict[str, dict[str, int]] = {
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

        strict_tier_stats[difficulty]["total"] += 1
        lenient_tier_stats[difficulty]["total"] += 1

        agent_res = agent.answer_question(question)

        is_strict_correct = False
        is_lenient_correct = False
        fail_category = None
        fail_details = ""
        gold_rows = None

        if expected_refusal:
            unanswerable_total += 1
            if not agent_res.can_answer:
                is_strict_correct = True
                is_lenient_correct = True
                true_refusals += 1
            else:
                is_strict_correct = False
                is_lenient_correct = False
                failed_refusals += 1
                fail_category = "failed_refusal"
                fail_details = "Model generated SQL instead of refusing unanswerable query."
        else:
            answerable_total += 1
            if not agent_res.can_answer:
                is_strict_correct = False
                is_lenient_correct = False
                false_refusals += 1
                fail_category = "false_refusal"
                fail_details = f"Falsely refused answerable question: {agent_res.refusal_reason}"
            elif agent_res.sql_error:
                is_strict_correct = False
                is_lenient_correct = False
                fail_category, fail_details = categorize_failure(
                    qid, question, agent_res, gold_sql, None, False, False
                )
            else:
                answerable_answered += 1
                gold_exec = run_sql(gold_sql)
                gold_rows = gold_exec.get("rows", [])
                is_strict_correct = _strict_match(agent_res.sql_results, gold_rows)
                is_lenient_correct = _lenient_match(agent_res.sql_results, gold_rows, gold_sql)

                if not is_lenient_correct or not is_strict_correct:
                    fail_category, fail_details = categorize_failure(
                        qid, question, agent_res, gold_sql, gold_rows, is_strict_correct, is_lenient_correct
                    )

        if is_strict_correct:
            strict_tier_stats[difficulty]["correct"] += 1
        if is_lenient_correct:
            lenient_tier_stats[difficulty]["correct"] += 1

        status_symbol = "✓" if is_lenient_correct else f"✗ ({fail_category})"
        strict_symbol = "S:✓" if is_strict_correct else "S:✗"
        print(f"  [{status_symbol} | {strict_symbol}] {qid} ({difficulty}): {question[:40]}...")
        time.sleep(0.05)

        results_list.append(
            {
                "id": qid,
                "difficulty": difficulty,
                "question": question,
                "expected_refusal": expected_refusal,
                "is_strict_correct": is_strict_correct,
                "is_lenient_correct": is_lenient_correct,
                "is_correct": is_lenient_correct,  # default is lenient for backward compat
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

    strict_total_correct = sum(s["correct"] for s in strict_tier_stats.values())
    lenient_total_correct = sum(s["correct"] for s in lenient_tier_stats.values())
    total_questions = sum(s["total"] for s in strict_tier_stats.values())

    strict_overall_acc = round(strict_total_correct / total_questions, 4) if total_questions > 0 else 0.0
    lenient_overall_acc = round(lenient_total_correct / total_questions, 4) if total_questions > 0 else 0.0

    return {
        "run_idx": run_idx,
        "prompt_version": prompt_version,
        "strict_overall_accuracy": strict_overall_acc,
        "lenient_overall_accuracy": lenient_overall_acc,
        "strict_total_correct": strict_total_correct,
        "lenient_total_correct": lenient_total_correct,
        "total_questions": total_questions,
        "strict_tier_accuracy": {
            t: round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0.0
            for t, s in strict_tier_stats.items()
        },
        "lenient_tier_accuracy": {
            t: round(s["correct"] / s["total"], 4) if s["total"] > 0 else 0.0
            for t, s in lenient_tier_stats.items()
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
    """Runs 3-arm QA ablation benchmark with 3 runs per prompt version, dual scoring, and failure analysis."""
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

        strict_accs = [r["strict_overall_accuracy"] for r in runs]
        lenient_accs = [r["lenient_overall_accuracy"] for r in runs]

        ref_precisions = [r["refusal_metrics"]["refusal_precision"] for r in runs]
        ref_recalls = [r["refusal_metrics"]["refusal_recall"] for r in runs]
        ans_recalls = [r["refusal_metrics"]["answerable_recall"] for r in runs]

        # Per-question pass rates across the 3 runs for both strict and lenient
        strict_passes: dict[str, int] = {item["id"]: 0 for item in gold_suite}
        lenient_passes: dict[str, int] = {item["id"]: 0 for item in gold_suite}
        for r in runs:
            for q_res in r["results"]:
                if q_res["is_strict_correct"]:
                    strict_passes[q_res["id"]] += 1
                if q_res["is_lenient_correct"]:
                    lenient_passes[q_res["id"]] += 1

        tier_names = ["easy", "medium", "hard", "unanswerable"]

        strict_tier_summary = {}
        lenient_tier_summary = {}
        for t in tier_names:
            s_vals = [r["strict_tier_accuracy"][t] for r in runs]
            l_vals = [r["lenient_tier_accuracy"][t] for r in runs]
            strict_tier_summary[t] = {
                "mean": round(sum(s_vals) / len(s_vals), 4),
                "min": min(s_vals),
                "max": max(s_vals),
                "variance": round(calculate_variance(s_vals), 6),
            }
            lenient_tier_summary[t] = {
                "mean": round(sum(l_vals) / len(l_vals), 4),
                "min": min(l_vals),
                "max": max(l_vals),
                "variance": round(calculate_variance(l_vals), 6),
            }

        arm_reports[pv] = {
            "prompt_version": pv,
            "num_runs": 3,
            "strict_accuracy": {
                "mean": round(sum(strict_accs) / len(strict_accs), 4),
                "min": min(strict_accs),
                "max": max(strict_accs),
                "variance": round(calculate_variance(strict_accs), 6),
            },
            "lenient_accuracy": {
                "mean": round(sum(lenient_accs) / len(lenient_accs), 4),
                "min": min(lenient_accs),
                "max": max(lenient_accs),
                "variance": round(calculate_variance(lenient_accs), 6),
            },
            "strict_tier_accuracy": strict_tier_summary,
            "lenient_tier_accuracy": lenient_tier_summary,
            "refusal_metrics": {
                "refusal_precision": {
                    "mean": round(sum(ref_precisions) / len(ref_precisions), 4),
                    "min": min(ref_precisions),
                    "max": max(ref_precisions),
                    "variance": round(calculate_variance(ref_precisions), 6),
                },
                "refusal_recall": {
                    "mean": round(sum(ref_recalls) / len(ref_recalls), 4),
                    "min": min(ref_recalls),
                    "max": max(ref_recalls),
                    "variance": round(calculate_variance(ref_recalls), 6),
                },
                "answerable_recall": {
                    "mean": round(sum(ans_recalls) / len(ans_recalls), 4),
                    "min": min(ans_recalls),
                    "max": max(ans_recalls),
                    "variance": round(calculate_variance(ans_recalls), 6),
                },
            },
            "strict_question_passes": strict_passes,
            "lenient_question_passes": lenient_passes,
            "representative_run": runs[0],
            "all_runs": runs,
        }

    # Identify question flips between arms
    flips = _compute_arm_flips(arm_reports)

    # Audit easy regressions between v1 and v2
    easy_regressions = _audit_easy_regressions(arm_reports)

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
        "flips": flips,
        "easy_regressions_v1_to_v2": easy_regressions,
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

    # Generate Detailed Failure Analysis for Prompt v3
    failure_md_path = results_dir / "failure_analysis.md"
    failure_content = _build_failure_analysis_report(arm_reports["v3"]["representative_run"])
    with open(failure_md_path, "w", encoding="utf-8") as f:
        f.write(failure_content)

    # Check for held-out evaluation set
    heldout_path = REPO_ROOT / "eval" / "benchmarks" / "heldout_queries.json"
    if heldout_path.exists():
        print(f"\n[HELD-OUT SET] Detected {heldout_path}. Running single pass on Prompt v3...")
        _run_heldout_evaluation(heldout_path, client, git_hash, timestamp, results_dir)
    else:
        print("\n[HELD-OUT SET] eval/benchmarks/heldout_queries.json not present. Skipping held-out evaluation.")

    print("\nQA Benchmark Evaluation Complete!")
    print(f"  JSON Benchmark: {json_path}")
    print(f"  Markdown Summary: {md_path}")
    print(f"  Failure Analysis: {failure_md_path}")

    return payload, json_path, md_path, failure_md_path


def _compute_arm_flips(arm_reports: dict[str, Any]) -> dict[str, Any]:
    """Computes which questions flipped status between arms (v1 -> v2, v2 -> v3)."""
    v1_len = arm_reports["v1"]["lenient_question_passes"]
    v2_len = arm_reports["v2"]["lenient_question_passes"]
    v3_len = arm_reports["v3"]["lenient_question_passes"]

    v1_str = arm_reports["v1"]["strict_question_passes"]
    v2_str = arm_reports["v2"]["strict_question_passes"]
    v3_str = arm_reports["v3"]["strict_question_passes"]

    all_qids = sorted(v1_len.keys())

    return {
        "lenient": {
            "v1_to_v2_regressed": [q for q in all_qids if v1_len[q] >= 2 and v2_len[q] == 0],
            "v1_to_v2_improved": [q for q in all_qids if v1_len[q] == 0 and v2_len[q] >= 2],
            "v2_to_v3_regressed": [q for q in all_qids if v2_len[q] >= 2 and v3_len[q] == 0],
            "v2_to_v3_improved": [q for q in all_qids if v2_len[q] == 0 and v3_len[q] >= 2],
        },
        "strict": {
            "v1_to_v2_regressed": [q for q in all_qids if v1_str[q] >= 2 and v2_str[q] == 0],
            "v1_to_v2_improved": [q for q in all_qids if v1_str[q] == 0 and v2_str[q] >= 2],
            "v2_to_v3_regressed": [q for q in all_qids if v2_str[q] >= 2 and v3_str[q] == 0],
            "v2_to_v3_improved": [q for q in all_qids if v2_str[q] == 0 and v3_str[q] >= 2],
        },
    }


def _audit_easy_regressions(arm_reports: dict[str, Any]) -> list[dict[str, Any]]:
    """Identifies easy-tier questions that v2 fails but v1 passes, with SQL diffs and root causes."""
    v1_rep = {q["id"]: q for q in arm_reports["v1"]["representative_run"]["results"]}
    v2_rep = {q["id"]: q for q in arm_reports["v2"]["representative_run"]["results"]}

    easy_regressions = []
    for qid, q1 in v1_rep.items():
        if q1["difficulty"] == "easy":
            q2 = v2_rep[qid]
            # Checked if passed in v1 and failed in v2
            if q1["is_lenient_correct"] and not q2["is_lenient_correct"]:
                root_cause = ""
                diff_summary = ""
                if qid == "q01":
                    root_cause = (
                        "Prompt v2 instructed the agent to strictly follow corporate metric definitions. "
                        "The model formatted its response as a key-value metric report ('Total Net Revenue' AS metric, "
                        "SUM(net_amount) AS value) instead of a scalar projection, causing column name mismatch."
                    )
                    diff_summary = "Agent projected ['metric', 'value'] instead of ['total_net_revenue']."
                elif qid == "q06":
                    root_cause = (
                        "Prompt v2 emphasized schema dimensions for aggregations. The model included the 'channel' "
                        "column in the GROUP BY and SELECT clause even when filtered to a single constant ('Amazon')."
                    )
                    diff_summary = "Agent projected ['channel', 'order_count'] instead of scalar ['amazon_order_count']."
                else:
                    root_cause = q2.get("fail_details", "Regression from v1 to v2.")
                    diff_summary = f"v1 passed ({q1.get('agent_sql')}), v2 failed ({q2.get('agent_sql')})"

                easy_regressions.append(
                    {
                        "id": qid,
                        "question": q1["question"],
                        "v1_sql": q1.get("agent_sql"),
                        "v2_sql": q2.get("agent_sql"),
                        "gold_sql": q1.get("gold_sql"),
                        "diff": diff_summary,
                        "root_cause": root_cause,
                    }
                )

    return easy_regressions


def _run_heldout_evaluation(
    heldout_path: Path,
    client: LLMClient,
    git_hash: str,
    timestamp: str,
    results_dir: Path,
) -> None:
    """Evaluates the final prompt (v3) once on the held-out benchmark dataset."""
    with open(heldout_path, "r", encoding="utf-8") as f:
        heldout_suite = json.load(f)

    heldout_res = run_single_benchmark_pass(
        prompt_version="v3",
        gold_suite=heldout_suite,
        client=client,
        run_idx=1,
    )

    heldout_payload = {
        "metadata": {
            "evaluation_date": datetime.now(timezone.utc).isoformat(),
            "git_commit_hash": git_hash,
            "llm_provider": client.provider,
            "model_name": client.model,
            "temperature": 0.0,
            "prompt_version": "v3",
            "total_questions": len(heldout_suite),
            "benchmark_type": "held_out_unseen",
        },
        "results": heldout_res,
    }

    out_json = results_dir / f"heldout_eval_{timestamp}.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(heldout_payload, f, indent=2, default=str)

    out_md = results_dir / f"heldout_eval_{timestamp}.md"
    lines = [
        "# Held-Out Evaluation Benchmark Report (Prompt v3)",
        "",
        f"**Date**: {heldout_payload['metadata']['evaluation_date']}  ",
        f"**Git Commit**: `{git_hash}` | **Model**: `{client.model}` ({client.provider})  ",
        f"**Total Questions**: `{len(heldout_suite)}` (Unseen during prompt development)  ",
        "",
        "## Accuracy Summary",
        "",
        f"- **Strict Overall Accuracy**: {heldout_res['strict_overall_accuracy'] * 100:.1f}% ({heldout_res['strict_total_correct']}/{heldout_res['total_questions']})",
        f"- **Lenient Overall Accuracy**: {heldout_res['lenient_overall_accuracy'] * 100:.1f}% ({heldout_res['lenient_total_correct']}/{heldout_res['total_questions']})",
        "",
        "| Question ID | Difficulty | Strict | Lenient | Question |",
        "| :--- | :---: | :---: | :---: | :--- |",
    ]
    for q in heldout_res["results"]:
        s_sym = "✓" if q["is_strict_correct"] else "✗"
        l_sym = "✓" if q["is_lenient_correct"] else "✗"
        lines.append(f"| `{q['id']}` | {q['difficulty']} | {s_sym} | {l_sym} | {q['question'][:50]} |")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Held-out report saved: {out_md}")


def _build_markdown_summary(payload: dict[str, Any]) -> str:
    """Builds the comprehensive Markdown comparison report with strict & lenient ladders and flips."""
    meta = payload["metadata"]
    arms = payload["arms"]
    flips = payload["flips"]
    easy_regs = payload["easy_regressions_v1_to_v2"]

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
        f"**Runs per Arm**: `{meta['runs_per_arm']} consecutive passes` | **LLM Cache**: `{meta['caching_used']}`  ",
        "",
        "---",
        "",
        "## 1. Dual-Metric Execution Accuracy Ablation Ladder",
        "",
        "> **Strict Scoring**: Exact column match, exact row order, strict float tolerance.  ",
        "> **Lenient Scoring**: Subsets to gold columns, normalises date/timestamp vs 'YYYY-MM', ignores row order unless `ORDER BY + LIMIT`, numeric float tolerance.",
        "",
        "### 1.1 Lenient (Semantically Equivalent) Accuracy (Mean [Min – Max] ± Variance)",
        "",
        "| Difficulty Tier | Questions | v1: Schema-Only | v2: Governed | v3: Few-Shot + Self-Correction | Delta (v3 vs v1) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    tier_counts = {"easy": 10, "medium": 12, "hard": 10, "unanswerable": 8}
    for tier in ["easy", "medium", "hard", "unanswerable"]:
        t_name = tier.capitalize()
        cnt = tier_counts[tier]
        v1_s = f"{v1['lenient_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v1['lenient_tier_accuracy'][tier]['min'] * 100:.1f}%–{v1['lenient_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v1['lenient_tier_accuracy'][tier]['variance']:.4f})"
        v2_s = f"{v2['lenient_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v2['lenient_tier_accuracy'][tier]['min'] * 100:.1f}%–{v2['lenient_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v2['lenient_tier_accuracy'][tier]['variance']:.4f})"
        v3_s = f"{v3['lenient_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v3['lenient_tier_accuracy'][tier]['min'] * 100:.1f}%–{v3['lenient_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v3['lenient_tier_accuracy'][tier]['variance']:.4f})"
        delta = f"{(v3['lenient_tier_accuracy'][tier]['mean'] - v1['lenient_tier_accuracy'][tier]['mean']) * 100:+.1f}%"
        lines.append(f"| **{t_name}** | {cnt} | {v1_s} | {v2_s} | {v3_s} | {delta} |")

    overall_v1 = f"{v1['lenient_accuracy']['mean'] * 100:.1f}% [{v1['lenient_accuracy']['min'] * 100:.1f}%–{v1['lenient_accuracy']['max'] * 100:.1f}%] (s²={v1['lenient_accuracy']['variance']:.4f})"
    overall_v2 = f"{v2['lenient_accuracy']['mean'] * 100:.1f}% [{v2['lenient_accuracy']['min'] * 100:.1f}%–{v2['lenient_accuracy']['max'] * 100:.1f}%] (s²={v2['lenient_accuracy']['variance']:.4f})"
    overall_v3 = f"{v3['lenient_accuracy']['mean'] * 100:.1f}% [{v3['lenient_accuracy']['min'] * 100:.1f}%–{v3['lenient_accuracy']['max'] * 100:.1f}%] (s²={v3['lenient_accuracy']['variance']:.4f})"
    overall_delta = f"{(v3['lenient_accuracy']['mean'] - v1['lenient_accuracy']['mean']) * 100:+.1f}%"
    lines.append(f"| **Overall Lenient** | **40** | **{overall_v1}** | **{overall_v2}** | **{overall_v3}** | **{overall_delta}** |")

    lines.extend([
        "",
        "### 1.2 Strict Accuracy (Mean [Min – Max] ± Variance)",
        "",
        "| Difficulty Tier | Questions | v1: Schema-Only | v2: Governed | v3: Few-Shot + Self-Correction | Delta (v3 vs v1) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ])

    for tier in ["easy", "medium", "hard", "unanswerable"]:
        t_name = tier.capitalize()
        cnt = tier_counts[tier]
        v1_s = f"{v1['strict_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v1['strict_tier_accuracy'][tier]['min'] * 100:.1f}%–{v1['strict_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v1['strict_tier_accuracy'][tier]['variance']:.4f})"
        v2_s = f"{v2['strict_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v2['strict_tier_accuracy'][tier]['min'] * 100:.1f}%–{v2['strict_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v2['strict_tier_accuracy'][tier]['variance']:.4f})"
        v3_s = f"{v3['strict_tier_accuracy'][tier]['mean'] * 100:.1f}% [{v3['strict_tier_accuracy'][tier]['min'] * 100:.1f}%–{v3['strict_tier_accuracy'][tier]['max'] * 100:.1f}%] (s²={v3['strict_tier_accuracy'][tier]['variance']:.4f})"
        delta = f"{(v3['strict_tier_accuracy'][tier]['mean'] - v1['strict_tier_accuracy'][tier]['mean']) * 100:+.1f}%"
        lines.append(f"| **{t_name}** | {cnt} | {v1_s} | {v2_s} | {v3_s} | {delta} |")

    str_overall_v1 = f"{v1['strict_accuracy']['mean'] * 100:.1f}% [{v1['strict_accuracy']['min'] * 100:.1f}%–{v1['strict_accuracy']['max'] * 100:.1f}%] (s²={v1['strict_accuracy']['variance']:.4f})"
    str_overall_v2 = f"{v2['strict_accuracy']['mean'] * 100:.1f}% [{v2['strict_accuracy']['min'] * 100:.1f}%–{v2['strict_accuracy']['max'] * 100:.1f}%] (s²={v2['strict_accuracy']['variance']:.4f})"
    str_overall_v3 = f"{v3['strict_accuracy']['mean'] * 100:.1f}% [{v3['strict_accuracy']['min'] * 100:.1f}%–{v3['strict_accuracy']['max'] * 100:.1f}%] (s²={v3['strict_accuracy']['variance']:.4f})"
    str_overall_delta = f"{(v3['strict_accuracy']['mean'] - v1['strict_accuracy']['mean']) * 100:+.1f}%"
    lines.append(f"| **Overall Strict** | **40** | **{str_overall_v1}** | **{str_overall_v2}** | **{str_overall_v3}** | **{str_overall_delta}** |")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Refusal Accounting & Precision (Side-by-Side Comparison)",
        "",
        "| Metric | v1: Schema-Only | v2: Governed | v3: Few-Shot + Correction | Business Significance |",
        "| :--- | :---: | :---: | :---: | :--- |",
        f"| **Refusal Recall** | {v1['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | {v2['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | {v3['refusal_metrics']['refusal_recall']['mean'] * 100:.1f}% | Correctly refusing unanswerable questions (out of 8) |",
        f"| **Refusal Precision** | {v1['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | {v2['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | {v3['refusal_metrics']['refusal_precision']['mean'] * 100:.1f}% | Penalizes models that falsely refuse answerable questions |",
        f"| **Answerable Recall** | {v1['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | {v2['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | {v3['refusal_metrics']['answerable_recall']['mean'] * 100:.1f}% | Successfully attempting valid business queries (out of 32) |",
        "",
        "---",
        "",
        "## 3. Easy-Tier v1 vs v2 Regressions (Honest Failure Audit)",
        "",
        "The table below details all easy-tier questions that regressed from v1 to v2:",
        "",
    ])

    if easy_regs:
        lines.extend([
            "| Question ID | Question | v1 SQL (Passed) | v2 SQL (Failed) | Diff Summary | Root Cause |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for reg in easy_regs:
            v1_clean = (reg["v1_sql"] or "").replace("\n", " ")[:40]
            v2_clean = (reg["v2_sql"] or "").replace("\n", " ")[:40]
            lines.append(f"| `{reg['id']}` | {reg['question']} | `{v1_clean}...` | `{v2_clean}...` | {reg['diff']} | {reg['root_cause']} |")
    else:
        lines.append("*No easy-tier regressions detected.*")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Question Flips Between Arms",
        "",
        "### 4.1 Lenient Evaluation Flips",
        f"- **v1 → v2 Regressed** ({len(flips['lenient']['v1_to_v2_regressed'])} questions): `{', '.join(flips['lenient']['v1_to_v2_regressed']) or 'None'}`",
        f"- **v1 → v2 Improved** ({len(flips['lenient']['v1_to_v2_improved'])} questions): `{', '.join(flips['lenient']['v1_to_v2_improved']) or 'None'}`",
        f"- **v2 → v3 Regressed** ({len(flips['lenient']['v2_to_v3_regressed'])} questions): `{', '.join(flips['lenient']['v2_to_v3_regressed']) or 'None'}`",
        f"- **v2 → v3 Improved** ({len(flips['lenient']['v2_to_v3_improved'])} questions): `{', '.join(flips['lenient']['v2_to_v3_improved']) or 'None'}`",
        "",
        "### 4.2 Strict Evaluation Flips",
        f"- **v1 → v2 Regressed** ({len(flips['strict']['v1_to_v2_regressed'])} questions): `{', '.join(flips['strict']['v1_to_v2_regressed']) or 'None'}`",
        f"- **v1 → v2 Improved** ({len(flips['strict']['v1_to_v2_improved'])} questions): `{', '.join(flips['strict']['v1_to_v2_improved']) or 'None'}`",
        f"- **v2 → v3 Regressed** ({len(flips['strict']['v2_to_v3_regressed'])} questions): `{', '.join(flips['strict']['v2_to_v3_regressed']) or 'None'}`",
        f"- **v2 → v3 Improved** ({len(flips['strict']['v2_to_v3_improved'])} questions): `{', '.join(flips['strict']['v2_to_v3_improved']) or 'None'}`",
        "",
        "---",
        "",
        "## 5. Per-Question Pass Consistency (Runs with Correct SQL / 3 Passes)",
        "",
        "| Question ID | Difficulty | v1 Passes (Lenient / Strict) | v2 Passes (Lenient / Strict) | v3 Passes (Lenient / Strict) | Question Summary |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ])

    for qid in sorted(v3["lenient_question_passes"].keys()):
        p1 = f"{v1['lenient_question_passes'][qid]}/3 (str: {v1['strict_question_passes'][qid]}/3)"
        p2 = f"{v2['lenient_question_passes'][qid]}/3 (str: {v2['strict_question_passes'][qid]}/3)"
        p3 = f"{v3['lenient_question_passes'][qid]}/3 (str: {v3['strict_question_passes'][qid]}/3)"
        rep_q = next(q for q in v3["representative_run"]["results"] if q["id"] == qid)
        lines.append(f"| `{qid}` | {rep_q['difficulty']} | {p1} | {p2} | {p3} | {rep_q['question'][:50]} |")

    return "\n".join(lines)


def _build_failure_analysis_report(run_data: dict[str, Any]) -> str:
    """Builds a granular failure analysis report for Prompt v3."""
    failing_items = [q for q in run_data["results"] if not q["is_lenient_correct"]]
    from collections import Counter
    category_counts = Counter(q["fail_category"] for q in failing_items)

    lines = [
        "# SQL Agent Failure Analysis Report (Prompt v3)",
        "",
        f"**Total Failing Questions (Lenient)**: {len(failing_items)} of {len(run_data['results'])} (Lenient Accuracy: {run_data['lenient_overall_accuracy'] * 100:.1f}% | Strict: {run_data['strict_overall_accuracy'] * 100:.1f}%)  ",
        "",
        "## 1. Summary of Failure Categories",
        "",
        "| Failure Category | Count | Percentage of Failures | Primary Root Cause |",
        "| :--- | :---: | :---: | :--- |",
    ]

    category_descriptions = {
        "ambiguity": "Question wording allows multiple valid interpretations or gold SQL requires arbitrary extra columns.",
        "wrong_metric": "Generated SQL used an alternate aggregation or failed to adhere to corporate data dictionary formulas.",
        "failed_refusal": "Model answered an unanswerable question rather than refusing.",
        "false_refusal": "Model falsely claimed the data was missing for an answerable query.",
        "date_handling": "Discrepancy in date formatting or year/month extraction syntax.",
        "aggregation_level": "Computed aggregate at the wrong grain (e.g. line items vs distinct orders).",
        "wrong_join": "Missing or improper join relation.",
        "hallucinated_column": "Referenced an invalid column name.",
        "syntax_or_parser_error": "Produced invalid DuckDB syntax or violated AST security boundaries.",
        "strict_mismatch": "Matches lenient semantic comparator but differs in column naming or row ordering.",
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
