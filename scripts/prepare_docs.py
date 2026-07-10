#!/usr/bin/env python3
"""Prepare paper-style documentation tables and figures from committed data.

This script is deliberately read-only with respect to SCF/profile generation. It
reads committed CSV/JSON/YAML outputs, writes reusable Markdown table fragments
under ``docs/tables/``, writes compact SVG diagnostics under ``docs/figures/``,
and refreshes marked auto blocks in curated documentation pages.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TABLES = DOCS / "tables"
FIGURES = DOCS / "figures"

STATE_CSV = ROOT / "data" / "states" / "curated" / "atom_states_v2.csv"
PROFILE_CONFIG = ROOT / "data" / "profile_datasets.yaml"
QA_SUMMARY = ROOT / "data" / "qa" / "qa_summary.csv"
BASIS_SENSITIVITY_ROOT = ROOT / "data" / "qa" / "basis_sensitivity"
BASIS_SENSITIVITY = BASIS_SENSITIVITY_ROOT / "basis_sensitivity.csv"
BASIS_SENSITIVITY_SUMMARY = BASIS_SENSITIVITY_ROOT / "basis_sensitivity_summary.csv"
BASIS_SENSITIVITY_OUTLIERS = BASIS_SENSITIVITY_ROOT / "basis_sensitivity_outliers.csv"
PRIMARY_COMPARISON_DIR = ROOT / "data" / "qa" / "basis_comparisons" / "x2c-QZVPall__dyall-v4z"
PRIMARY_COMPARISON = PRIMARY_COMPARISON_DIR / "basis_comparison.csv"
PRIMARY_COMPARISON_SUMMARY = PRIMARY_COMPARISON_DIR / "basis_comparison_summary.csv"
PRIMARY_COMPARISON_OUTLIERS = PRIMARY_COMPARISON_DIR / "basis_comparison_outliers.csv"
PRIMARY_COMPARISON_DISTRIBUTIONS = (
    PRIMARY_COMPARISON_DIR / "basis_comparison_metric_distributions.csv"
)

AUTO_PATTERN = re.compile(
    r"<!-- BEGIN AUTO:(?P<kind>table|figure):(?P<name>[A-Za-z0-9_\-]+) -->"
    r".*?"
    r"<!-- END AUTO:(?P=kind):(?P=name) -->",
    re.S,
)

ROLE_ORDER = [
    "reference",
    "reference_uncertain",
    "bound_experimental",
    "bound_provisional",
    "diagnostic_theory",
    "formal_monoanion",
    "formal_multianion",
]

TABLE_FILES = {
    "dataset_inventory": "dataset_inventory.md",
    "state_counts_by_charge": "state_counts_by_charge.md",
    "state_counts_by_role": "state_counts_by_role.md",
    "generated_rows_by_charge": "generated_rows_by_charge.md",
    "generated_rows_by_role": "generated_rows_by_role.md",
    "qa_validation_summary": "qa_validation_summary.md",
    "linear_dependency_summary": "linear_dependency_summary.md",
    "primary_basis_comparison_summary": "primary_basis_comparison_summary.md",
    "primary_basis_comparison_by_charge": "primary_basis_comparison_by_charge.md",
    "primary_basis_metric_distributions": "primary_basis_metric_distributions.md",
    "primary_basis_outliers": "primary_basis_outliers.md",
    "basis_sensitivity_summary": "basis_sensitivity_summary.md",
    "basis_sensitivity_by_charge": "basis_sensitivity_by_charge.md",
    "basis_sensitivity_by_role": "basis_sensitivity_by_role.md",
    "basis_sensitivity_outliers": "basis_sensitivity_outliers.md",
}

FIGURE_FILES = {
    "comparison_tier_counts": "comparison_tier_counts.svg",
    "relative_l1_by_charge": "relative_l1_by_charge.svg",
}

DOC_PAGES = [
    DOCS / "results.md",
]


@dataclass(frozen=True)
class PreparedDocs:
    tables: dict[str, str]
    figures: dict[str, str]
    pages: dict[Path, str]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> Mapping[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def fmt_float(value: str | float | int | None, *, digits: int = 3) -> str:
    if value is None or value == "":
        return "NA"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not math.isfinite(numeric):
        return "NA"
    if numeric == 0:
        return "0"
    if abs(numeric) < 10 ** (-(digits + 1)) or abs(numeric) >= 1e4:
        return f"{numeric:.{digits}e}"
    return f"{numeric:.{digits}f}"


def fmt_int(value: str | int) -> str:
    return str(int(value))


def sort_charge_key(value: str) -> int:
    return int(value)


def fmt_charge(value: str | int) -> str:
    charge = int(value)
    return f"+{charge}" if charge > 0 else str(charge)


def md_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def md_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(md_cell(header) for header in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")
    return "\n".join(lines) + "\n"


def median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else math.nan


def quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - rank) + ordered[hi] * (rank - lo)


def dataset_config_by_id() -> dict[str, Mapping[str, object]]:
    config = read_yaml(PROFILE_CONFIG)
    datasets = config.get("datasets", [])
    return {str(row["dataset_id"]): row for row in datasets if isinstance(row, Mapping)}


def dataset_inventory_table() -> str:
    config = dataset_config_by_id()
    role_labels = {
        "primary_h_rn_all_curated_states": "primary H--Rn",
        "primary_h_lr_all_curated_states": "primary H--Lr",
        "supplemented_h_rn_neutral_and_anion_states": "supplemented H--Rn",
        "augmented_available_dyall_av4z_neutral_and_anion_states": "augmented available intervals",
    }
    rows: list[list[str]] = []
    for dataset_id, cfg in config.items():
        metadata_path = ROOT / "data" / "profiles" / dataset_id / "metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        role = str(cfg.get("role", ""))
        rows.append(
            [
                f"`{dataset_id}`",
                f"`{metadata['basis_id']}`",
                role_labels.get(role, role.replace("_", " ")),
                str(cfg.get("coverage_label", "")),
                str(len(metadata.get("states", []))),
                str(count_csv_rows(ROOT / "data" / "qa" / dataset_id / "qa.csv")),
            ]
        )
    return md_table(
        ["dataset ID", "basis", "branch role", "state scope", "profile rows", "QA rows"],
        rows,
    )


def state_tables() -> tuple[str, str]:
    states = read_csv(STATE_CSV)
    by_charge = Counter(row["charge"] for row in states)
    by_role = Counter(row["state_role"] for row in states)
    charge_rows = [
        [fmt_charge(charge), by_charge[charge]] for charge in sorted(by_charge, key=sort_charge_key)
    ]
    role_rows = [[role, by_role[role]] for role in ROLE_ORDER if by_role[role]]
    return md_table(["charge", "curated states"], charge_rows), md_table(
        ["state role", "curated states"], role_rows
    )


def generated_row_tables() -> tuple[str, str]:
    generated: list[dict[str, str]] = []
    for radii_path in sorted((ROOT / "data" / "radii").glob("pbe0_*/radii.csv")):
        generated.extend(read_csv(radii_path))
    by_charge = Counter(row["charge"] for row in generated)
    by_role = Counter(row["state_role"] for row in generated)
    charge_rows = [
        [fmt_charge(charge), by_charge[charge]] for charge in sorted(by_charge, key=sort_charge_key)
    ]
    role_rows = [[role, by_role[role]] for role in ROLE_ORDER if by_role[role]]
    return md_table(["charge", "generated dataset-state rows"], charge_rows), md_table(
        ["state role", "generated dataset-state rows"], role_rows
    )


def qa_validation_summary_table() -> str:
    rows = []
    for row in read_csv(QA_SUMMARY):
        rows.append(
            [
                f"`{row['dataset_id']}`",
                f"`{row['basis_id']}`",
                row["state_count"],
                row["failed_count"],
                fmt_float(row["max_abs_electron_count_error_qa"], digits=2),
                fmt_float(row["max_rel_angular_sigma"], digits=2),
                row["linear_dependency_warning_count"],
            ]
        )
    return md_table(
        [
            "dataset ID",
            "basis",
            "rows",
            "failed rows",
            "max |ΔN|",
            "max angular σ/ρ",
            "linear-dependency warnings",
        ],
        rows,
    )


def linear_dependency_summary_table() -> str:
    rows = read_csv(QA_SUMMARY)
    table_rows = []
    total = 0
    for row in rows:
        state_count = int(row["state_count"])
        ld = int(row["linear_dependency_warning_count"])
        total += ld
        fraction = ld / state_count if state_count else 0
        table_rows.append(
            [
                f"`{row['basis_id']}`",
                state_count,
                ld,
                fmt_float(100 * fraction, digits=1) + "%",
            ]
        )
    table_rows.append(["**all datasets**", sum(int(r["state_count"]) for r in rows), total, ""])
    return md_table(["basis", "QA rows", "LD-warning rows", "fraction"], table_rows)


def summary_table(path: Path, *, kind: str) -> str:
    data = read_csv(path)
    rows = []
    for row in data:
        if kind == "primary":
            pair = f"`{row['left_basis_id']}` → `{row['right_basis_id']}`"
            failed_key = "integrity_fail_count"
            low_key = "low_comparison_count"
            moderate_key = "moderate_comparison_count"
            high_key = "high_comparison_count"
        else:
            pair = f"`{row['base_basis_id']}` → `{row['diffuse_basis_id']}`"
            failed_key = "release_gate_fail_count"
            low_key = "low_sensitivity_count"
            moderate_key = "moderate_sensitivity_count"
            high_key = "high_sensitivity_count"
        rows.append(
            [
                pair,
                row["common_state_count"],
                row[failed_key],
                row[low_key],
                row[moderate_key],
                row[high_key],
                row["outlier_count"],
                fmt_float(row["max_relative_l1_delta"], digits=3),
                fmt_float(row["max_abs_cumulative_delta_electrons"], digits=3),
                fmt_float(row["max_abs_cutoff_radius_delta_angstrom"], digits=3),
            ]
        )
    return md_table(
        [
            "comparison",
            "matched states",
            "integrity/validation failures",
            "low",
            "moderate",
            "high",
            "outliers",
            "max relative L1",
            "max sup |ΔN(r)| / e",
            "max |ΔR_cut| / Å",
        ],
        rows,
    )


def grouped_metric_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    pair_label: str,
    tier_key: str,
    group_key: str,
) -> list[list[str]]:
    groups: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row[group_key]].append(row)
    table_rows = []
    for group in sorted(groups, key=sort_charge_key if group_key == "charge" else str):
        group_rows = groups[group]
        rel = [abs(float(row["relative_radial_distribution_l1_delta"])) for row in group_rows]
        cum = [abs(float(row["max_abs_cumulative_delta_electrons"])) for row in group_rows]
        cut = [abs(float(row["max_abs_cutoff_radius_delta_angstrom"])) for row in group_rows]
        tier_counts = Counter(row[tier_key] for row in group_rows)
        table_rows.append(
            [
                pair_label,
                fmt_charge(group) if group_key == "charge" else group,
                len(group_rows),
                tier_counts.get("low", 0),
                tier_counts.get("moderate", 0),
                tier_counts.get("high", 0),
                fmt_float(median(rel), digits=4),
                fmt_float(quantile(rel, 0.95), digits=4),
                fmt_float(max(rel), digits=4),
                fmt_float(max(cum), digits=4),
                fmt_float(max(cut), digits=4),
            ]
        )
    return table_rows


def primary_by_charge_table() -> str:
    rows = grouped_metric_rows(
        read_csv(PRIMARY_COMPARISON),
        pair_label="`x2c-QZVPall` → `dyall-v4z`",
        tier_key="comparison_tier",
        group_key="charge",
    )
    return md_table(
        [
            "comparison",
            "charge",
            "n",
            "low",
            "moderate",
            "high",
            "median rel. L1",
            "p95 rel. L1",
            "max rel. L1",
            "max sup |ΔN(r)| / e",
            "max |ΔR_cut| / Å",
        ],
        rows,
    )


def basis_sensitivity_by_charge_table() -> str:
    all_rows = []
    for pair_dir, label in [
        (
            BASIS_SENSITIVITY_ROOT / "dyall-v4z" / "basis_sensitivity.csv",
            "`dyall-v4z` → `dyall-av4z`",
        ),
        (
            BASIS_SENSITIVITY_ROOT / "x2c-QZVPall" / "basis_sensitivity.csv",
            "`x2c-QZVPall` → `x2c-QZVPall-s`",
        ),
    ]:
        all_rows.extend(
            grouped_metric_rows(
                read_csv(pair_dir),
                pair_label=label,
                tier_key="sensitivity_tier",
                group_key="charge",
            )
        )
    return md_table(
        [
            "comparison",
            "charge",
            "n",
            "low",
            "moderate",
            "high",
            "median rel. L1",
            "p95 rel. L1",
            "max rel. L1",
            "max sup |ΔN(r)| / e",
            "max |ΔR_cut| / Å",
        ],
        all_rows,
    )


def basis_sensitivity_by_role_table() -> str:
    rows = read_csv(BASIS_SENSITIVITY)
    grouped: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        label = f"`{row['base_basis_id']}` → `{row['diffuse_basis_id']}`"
        grouped[(label, row["state_role"])].append(row)
    table_rows = []
    for (label, role), group_rows in sorted(
        grouped.items(), key=lambda item: (item[0][0], ROLE_ORDER.index(item[0][1]))
    ):
        rel = [abs(float(row["relative_radial_distribution_l1_delta"])) for row in group_rows]
        tier_counts = Counter(row["sensitivity_tier"] for row in group_rows)
        table_rows.append(
            [
                label,
                role,
                len(group_rows),
                tier_counts.get("low", 0),
                tier_counts.get("moderate", 0),
                tier_counts.get("high", 0),
                fmt_float(median(rel), digits=4),
                fmt_float(max(rel), digits=4),
            ]
        )
    return md_table(
        [
            "comparison",
            "state role",
            "n",
            "low",
            "moderate",
            "high",
            "median rel. L1",
            "max rel. L1",
        ],
        table_rows,
    )


def primary_metric_distributions_table() -> str:
    data = read_csv(PRIMARY_COMPARISON)
    metrics = [
        ("relative_radial_distribution_l1_delta", "relative L1", False),
        ("max_abs_cumulative_delta_electrons", "sup |ΔN(r)| / e", False),
        ("mean_abs_radial_shift_angstrom", "mean |radial shift| / Å", False),
        ("max_abs_cutoff_radius_delta_angstrom", "max |ΔR_cut| / Å", False),
        ("abs_delta_tail_electrons_gt_5_bohr", "|Δ tail N(r>5 bohr)| / e", False),
        ("abs_delta_tail_electrons_gt_10_bohr", "|Δ tail N(r>10 bohr)| / e", False),
        ("abs_delta_tail_electrons_gt_15_bohr", "|Δ tail N(r>15 bohr)| / e", False),
        ("abs_delta_tail_electrons_gt_20_bohr", "|Δ tail N(r>20 bohr)| / e", False),
    ]
    table_rows = []
    for column, label, signed in metrics:
        values = [float(row[column]) for row in data if row.get(column) not in {None, ""}]
        if not signed:
            values = [abs(value) for value in values]
        table_rows.append(
            [
                label,
                len(values),
                fmt_float(quantile(values, 0.50), digits=4),
                fmt_float(quantile(values, 0.90), digits=4),
                fmt_float(quantile(values, 0.95), digits=4),
                fmt_float(quantile(values, 0.99), digits=4),
                fmt_float(max(values), digits=4),
            ]
        )
    return md_table(["metric", "n", "p50", "p90", "p95", "p99", "max"], table_rows)


def outlier_table(path: Path, *, kind: str) -> str:
    rows = read_csv(path)
    if not rows:
        return "No outlier rows are present in the current artifact.\n"
    table_rows = []
    for row in rows:
        tier = row["comparison_tier"] if kind == "primary" else row["sensitivity_tier"]
        flags = row["comparison_flags"] if kind == "primary" else row["sensitivity_flags"]
        table_rows.append(
            [
                f"`{row['state_id']}`",
                row["symbol"],
                row["charge"],
                row["state_role"],
                tier,
                fmt_float(row["relative_radial_distribution_l1_delta"], digits=4),
                fmt_float(row["max_abs_cumulative_delta_electrons"], digits=4),
                fmt_float(row["max_abs_cutoff_radius_delta_angstrom"], digits=4),
                flags,
            ]
        )
    return md_table(
        [
            "state ID",
            "element",
            "charge",
            "state role",
            "tier",
            "rel. L1",
            "sup |ΔN(r)| / e",
            "max |ΔR_cut| / Å",
            "flags",
        ],
        table_rows,
    )


def svg_text(x: float, y: float, text: str, *, size: int = 12, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="sans-serif" '
        f'font-size="{size}" text-anchor="{anchor}">{escape(text)}</text>'
    )


def svg_open(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
    )


def comparison_tier_counts_svg() -> str:
    summary = read_csv(PRIMARY_COMPARISON_SUMMARY) + read_csv(BASIS_SENSITIVITY_SUMMARY)
    bars = []
    for row in summary:
        if "left_basis_id" in row:
            label = "x2c-QZVPall → dyall-v4z"
            low = int(row["low_comparison_count"])
            moderate = int(row["moderate_comparison_count"])
            high = int(row["high_comparison_count"])
        else:
            label = f"{row['base_basis_id']} → {row['diffuse_basis_id']}"
            low = int(row["low_sensitivity_count"])
            moderate = int(row["moderate_sensitivity_count"])
            high = int(row["high_sensitivity_count"])
        bars.append((label, low, moderate, high))
    width = 760
    height = 260
    left = 220
    bar_width = 450
    top = 58
    row_h = 54
    max_total = max(sum(counts) for _, *counts in bars)
    parts = [
        svg_open(width, height),
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(width / 2, 26, "Comparison-tier counts in the current data layer", size=15),
        svg_text(left + 18, 48, "low", size=11, anchor="start"),
        svg_text(left + 94, 48, "moderate", size=11, anchor="start"),
        svg_text(left + 197, 48, "high", size=11, anchor="start"),
        '<rect x="220" y="39" width="12" height="12" fill="#d9d9d9" stroke="#333"/>',
        '<rect x="296" y="39" width="12" height="12" fill="#a6a6a6" stroke="#333"/>',
        '<rect x="399" y="39" width="12" height="12" fill="#595959" stroke="#333"/>',
    ]
    for i, (label, low, moderate, high) in enumerate(bars):
        y = top + i * row_h
        total = low + moderate + high
        parts.append(svg_text(left - 10, y + 20, label, size=12, anchor="end"))
        x = left
        for count, shade in [(low, "#d9d9d9"), (moderate, "#a6a6a6"), (high, "#595959")]:
            segment = bar_width * count / max_total if max_total else 0
            if segment > 0:
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{segment:.1f}" height="26" '
                    f'fill="{shade}" stroke="#333"/>'
                )
                if segment >= 22:
                    parts.append(svg_text(x + segment / 2, y + 18, str(count), size=11))
            x += segment
        parts.append(svg_text(left + bar_width + 12, y + 18, f"n={total}", size=11, anchor="start"))
    parts.append(
        f'<line x1="{left}" y1="{height - 38}" '
        f'x2="{left + bar_width}" y2="{height - 38}" stroke="#333"/>'
    )
    parts.append(svg_text(left, height - 18, "0", size=10))
    parts.append(svg_text(left + bar_width, height - 18, str(max_total), size=10))
    parts.append("</svg>\n")
    return "\n".join(parts)


def relative_l1_by_charge_svg() -> str:
    series = []
    primary_rows = read_csv(PRIMARY_COMPARISON)
    series.append(("x2c-QZVPall → dyall-v4z", primary_rows, "comparison_tier"))
    series.append(
        (
            "dyall-v4z → dyall-av4z",
            read_csv(BASIS_SENSITIVITY_ROOT / "dyall-v4z" / "basis_sensitivity.csv"),
            "sensitivity_tier",
        )
    )
    series.append(
        (
            "x2c-QZVPall → x2c-QZVPall-s",
            read_csv(BASIS_SENSITIVITY_ROOT / "x2c-QZVPall" / "basis_sensitivity.csv"),
            "sensitivity_tier",
        )
    )
    charges = sorted({row["charge"] for _, rows, _ in series for row in rows}, key=sort_charge_key)
    values: dict[tuple[str, str], float] = {}
    max_value = 0.0
    for label, rows, _ in series:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            grouped[row["charge"]].append(abs(float(row["relative_radial_distribution_l1_delta"])))
        for charge in charges:
            val = quantile(grouped[charge], 0.95) if grouped[charge] else 0.0
            values[(label, charge)] = val
            max_value = max(max_value, val)
    max_axis = max(0.02, max_value * 1.12)
    width = 820
    height = 360
    left = 72
    bottom = 304
    plot_w = 690
    plot_h = 230
    top = bottom - plot_h
    group_w = plot_w / len(charges)
    bar_w = group_w / 4.2
    shades = ["#d9d9d9", "#8c8c8c", "#f2f2f2"]
    parts = [
        svg_open(width, height),
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(
            width / 2, 26, "p95 relative radial-distribution L1 difference by charge", size=15
        ),
        f'<line x1="{left}" y1="{bottom}" x2="{left + plot_w}" y2="{bottom}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#333"/>',
    ]
    for tick in [0, max_axis / 2, max_axis]:
        y = bottom - tick / max_axis * plot_h
        parts.append(f'<line x1="{left - 4}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="#333"/>')
        parts.append(svg_text(left - 8, y + 4, fmt_float(tick, digits=3), size=10, anchor="end"))
    for ci, charge in enumerate(charges):
        cx = left + ci * group_w + group_w / 2
        parts.append(svg_text(cx, bottom + 20, charge, size=11))
        for si, (label, _, _) in enumerate(series):
            x = cx - 1.5 * bar_w + si * bar_w
            value = values[(label, charge)]
            h = value / max_axis * plot_h
            parts.append(
                f'<rect x="{x:.1f}" y="{bottom - h:.1f}" width="{bar_w * 0.82:.1f}" '
                f'height="{h:.1f}" fill="{shades[si]}" stroke="#333"/>'
            )
    parts.append(svg_text(left + plot_w / 2, height - 14, "charge", size=12))
    y_axis_label_x = 22.0
    y_axis_label_y = top + plot_h / 2
    parts.append(
        f'<text x="{y_axis_label_x:.1f}" y="{y_axis_label_y:.1f}" '
        'font-family="sans-serif" font-size="12" text-anchor="middle" '
        f'transform="rotate(-90 {y_axis_label_x:.1f} {y_axis_label_y:.1f})">'
        'p95 rel. L1</text>'
    )
    legend_x = 116
    legend_y = 48
    for i, (label, _, _) in enumerate(series):
        y = legend_y + 18 * i
        parts.append(
            f'<rect x="{legend_x}" y="{y - 10}" width="12" height="12" '
            f'fill="{shades[i]}" stroke="#333"/>'
        )
        parts.append(svg_text(legend_x + 18, y, label, size=10, anchor="start"))
    parts.append("</svg>\n")
    return "\n".join(parts)


def markdown_figure(filename: str, alt: str) -> str:
    return f"![{alt}](figures/{filename})\n"


def build_tables() -> dict[str, str]:
    state_charge, state_role = state_tables()
    generated_charge, generated_role = generated_row_tables()
    return {
        "dataset_inventory": dataset_inventory_table(),
        "state_counts_by_charge": state_charge,
        "state_counts_by_role": state_role,
        "generated_rows_by_charge": generated_charge,
        "generated_rows_by_role": generated_role,
        "qa_validation_summary": qa_validation_summary_table(),
        "linear_dependency_summary": linear_dependency_summary_table(),
        "primary_basis_comparison_summary": summary_table(
            PRIMARY_COMPARISON_SUMMARY, kind="primary"
        ),
        "primary_basis_comparison_by_charge": primary_by_charge_table(),
        "primary_basis_metric_distributions": primary_metric_distributions_table(),
        "primary_basis_outliers": outlier_table(PRIMARY_COMPARISON_OUTLIERS, kind="primary"),
        "basis_sensitivity_summary": summary_table(BASIS_SENSITIVITY_SUMMARY, kind="sensitivity"),
        "basis_sensitivity_by_charge": basis_sensitivity_by_charge_table(),
        "basis_sensitivity_by_role": basis_sensitivity_by_role_table(),
        "basis_sensitivity_outliers": outlier_table(BASIS_SENSITIVITY_OUTLIERS, kind="sensitivity"),
    }


def build_figures() -> dict[str, str]:
    return {
        "comparison_tier_counts": comparison_tier_counts_svg(),
        "relative_l1_by_charge": relative_l1_by_charge_svg(),
    }


def render_auto_block(
    kind: str, name: str, tables: Mapping[str, str], figures: Mapping[str, str]
) -> str:
    if kind == "table":
        if name not in TABLE_FILES:
            raise KeyError(f"unknown table auto block: {name}")
        body = tables[name].strip()
    elif kind == "figure":
        if name not in FIGURE_FILES:
            raise KeyError(f"unknown figure auto block: {name}")
        body = markdown_figure(FIGURE_FILES[name], name.replace("_", " ")).strip()
    else:  # pragma: no cover - regex constrains this branch
        raise KeyError(kind)
    return f"<!-- BEGIN AUTO:{kind}:{name} -->\n{body}\n<!-- END AUTO:{kind}:{name} -->"


def refresh_page(path: Path, tables: Mapping[str, str], figures: Mapping[str, str]) -> str:
    text = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        return render_auto_block(match.group("kind"), match.group("name"), tables, figures)

    return AUTO_PATTERN.sub(replace, text)


def build_prepared_docs() -> PreparedDocs:
    tables = build_tables()
    figures = build_figures()
    pages = {page: refresh_page(page, tables, figures) for page in DOC_PAGES if page.exists()}
    return PreparedDocs(tables=tables, figures=figures, pages=pages)


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def check_file(path: Path, expected: str) -> str | None:
    if not path.exists():
        return f"missing: {path.relative_to(ROOT)}"
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return f"stale: {path.relative_to(ROOT)}"
    return None


def write_docs(prepared: PreparedDocs) -> list[Path]:
    changed: list[Path] = []
    for name, content in prepared.tables.items():
        path = TABLES / TABLE_FILES[name]
        if write_if_changed(path, content):
            changed.append(path)
    for name, content in prepared.figures.items():
        path = FIGURES / FIGURE_FILES[name]
        if write_if_changed(path, content):
            changed.append(path)
    for path, content in prepared.pages.items():
        if write_if_changed(path, content):
            changed.append(path)
    return changed


def check_docs(prepared: PreparedDocs) -> list[str]:
    issues: list[str] = []
    for name, content in prepared.tables.items():
        issue = check_file(TABLES / TABLE_FILES[name], content)
        if issue:
            issues.append(issue)
    for name, content in prepared.figures.items():
        issue = check_file(FIGURES / FIGURE_FILES[name], content)
        if issue:
            issues.append(issue)
    for path, content in prepared.pages.items():
        issue = check_file(path, content)
        if issue:
            issues.append(issue)
    return issues


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write", action="store_true", help="write docs/tables, docs/figures, and auto blocks"
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify docs/tables, docs/figures, and auto blocks are current",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    prepared = build_prepared_docs()
    if args.write:
        changed = write_docs(prepared)
        if changed:
            print("updated documentation derived outputs:")
            for path in changed:
                print(f"  {path.relative_to(ROOT)}")
        else:
            print("documentation derived outputs are already current")
        return 0
    issues = check_docs(prepared)
    if issues:
        print("documentation derived outputs are stale:", file=sys.stderr)
        for issue in issues:
            print(f"  {issue}", file=sys.stderr)
        print("run: python scripts/prepare_docs.py --write", file=sys.stderr)
        return 1
    print("documentation derived outputs are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
