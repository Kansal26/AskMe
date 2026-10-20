"""CLI driver for Phase 0: Synthetic Data & Ground Truth Generation."""

from __future__ import annotations

import json
from pathlib import Path

from src.data_gen.corrupter import save_messy_and_manifest
from src.data_gen.generator import generate_clean_dataset


def run_phase_0(
    seed: int = 42,
    num_products: int = 150,
    num_orders: int = 20000,
    num_returns: int = 2000,
    num_reviews: int = 3000,
) -> dict[str, Any]:
    """Generates clean synthetic datasets, injects ground-truth corruptions, and writes files."""
    clean_dir = Path("data/clean")
    messy_dir = Path("data/raw_messy")
    gt_dir = Path("data/ground_truth")

    clean_dir.mkdir(parents=True, exist_ok=True)
    messy_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating clean synthetic datasets (seed={seed})...")
    clean_datasets = generate_clean_dataset(
        seed=seed,
        num_products=num_products,
        num_orders=num_orders,
        num_returns=num_returns,
        num_reviews=num_reviews,
    )

    clean_paths = {}
    for name, df in clean_datasets.items():
        # Insert 1-indexed _row_id into clean dataset as well for row-level ground-truth comparison
        df_clean = df.copy()
        if "_row_id" not in df_clean.columns:
            df_clean.insert(0, "_row_id", range(1, len(df_clean) + 1))
        p = clean_dir / f"{name}.csv"
        df_clean.to_csv(p, index=False)
        clean_paths[name] = p
        print(f"  [Clean] {name}: {len(df_clean):,} rows -> {p}")

    print("Injecting corruptions and logging cell-level manifest...")
    messy_paths, manifest_path = save_messy_and_manifest(
        clean_datasets=clean_datasets,
        messy_dir=messy_dir,
        ground_truth_dir=gt_dir,
        seed=seed,
    )

    for name, p in messy_paths.items():
        print(f"  [Messy] {name} -> {p}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Summarize injected corruptions by issue type
    issue_counts: dict[str, int] = {}
    ambiguous_date_count = 0
    duplicate_rows_count = 0

    for item in manifest:
        itype = item["issue_type"]
        issue_counts[itype] = issue_counts.get(itype, 0) + 1
        if itype == "mixed_date_format" and item.get("details", {}).get("is_ambiguous"):
            ambiguous_date_count += 1
        elif itype == "duplicate_row":
            duplicate_rows_count += 1

    summary = {
        "total_manifest_entries": len(manifest),
        "issue_counts": issue_counts,
        "ambiguous_dates_flagged": ambiguous_date_count,
        "duplicate_rows_injected": duplicate_rows_count,
    }

    print("\nCorruption Injection Summary:")
    print(f"  Total Injected Anomalies: {summary['total_manifest_entries']}")
    for k, v in issue_counts.items():
        print(f"    - {k}: {v}")
    print(f"  Ambiguous Dates (requiring flag): {ambiguous_date_count}")
    print(f"  Duplicate Clones (with original_row_id tracking): {duplicate_rows_count}")
    print(f"  Manifest written to: {manifest_path}")

    return summary


if __name__ == "__main__":
    from typing import Any

    run_phase_0()
