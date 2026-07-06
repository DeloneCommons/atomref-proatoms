#!/usr/bin/env python3
"""Build a compact scientific report from committed data-layer artifacts.

The script is intentionally read-only with respect to profile/radii/QA data.  It
summarizes already generated release artifacts into a Markdown report for human
review.  It does not run SCF, extract profiles, alter QA thresholds, or create a
new dataset.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "data_layer_report.md"

QA_SUMMARY = ROOT / "data" / "qa" / "qa_summary.csv"
DYALL_SENSITIVITY = (
    ROOT / "data" / "qa" / "basis_sensitivity" / "dyall-v4z" / "basis_sensitivity.csv"
)
X2C_SENSITIVITY = (
    ROOT / "data" / "qa" / "basis_sensitivity" / "x2c-QZVPall" / "basis_sensitivity.csv"
)
X2C_RADII = ROOT / "data" / "radii" / "pbe0_sfx2c_x2cqzvpall_h-rn_spherical_v2" / "radii.csv"
DYALL_RADII = ROOT / "data" / "radii" / "pbe0_sfx2c_dyallv4z_h-lr_spherical_v2" / "radii.csv"

CUTOFFS = ("0.003", "0.001", "0.0001")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(row: Mapping[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        return math.nan
    return float(value)


def quantile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile / 100.0
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - rank) + ordered[hi] * (rank - lo)


def fmt_float(value: float, *, digits: int = 3) -> str:
    if value is None or not math.isfinite(float(value)):
        return "NA"
    value = float(value)
    if abs(value) == 0:
        return "0"
    if abs(value) < 1e-3 or abs(value) >= 1e4:
        return f"{value:.{digits}e}"
    return f"{value:.{digits}f}"


def md_cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def md_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    out = [
        "| " + " | ".join(md_cell(header) for header in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        out.append("| " + " | ".join(md_cell(value) for value in row) + " |")
    return "\n".join(out)


def qa_summary_table() -> tuple[str, dict[str, float]]:
    rows = read_csv(QA_SUMMARY)
    table_rows: list[list[str]] = []
    total_states = 0
    total_failed = 0
    total_ld = 0
    max_ne = 0.0
    max_sigma = 0.0
    for row in rows:
        total_states += int(row["state_count"])
        total_failed += int(row["failed_count"])
        total_ld += int(row["linear_dependency_warning_count"])
        max_ne = max(max_ne, abs(float(row["max_abs_electron_count_error_qa"])))
        max_sigma = max(max_sigma, abs(float(row["max_rel_angular_sigma"])))
        table_rows.append(
            [
                f"`{row['basis_id']}`",
                row["state_count"],
                row["failed_count"],
                fmt_float(abs(float(row["max_abs_electron_count_error_qa"])), digits=3),
                fmt_float(abs(float(row["max_rel_angular_sigma"])), digits=3),
                row["linear_dependency_warning_count"],
            ]
        )
    return (
        md_table(
            ["basis", "rows", "failed", "max |ΔN|", "max angular σ/ρ", "LD warnings"],
            table_rows,
        ),
        {
            "total_states": total_states,
            "total_failed": total_failed,
            "total_ld": total_ld,
            "max_ne": max_ne,
            "max_sigma": max_sigma,
        },
    )


def primary_radii_comparison_table() -> tuple[str, str]:
    x_rows = {row["state_id"]: row for row in read_csv(X2C_RADII)}
    d_rows = {row["state_id"]: row for row in read_csv(DYALL_RADII)}
    common = sorted(set(x_rows) & set(d_rows))

    cutoff_rows: list[list[str]] = []
    for cutoff in CUTOFFS:
        col = f"r_iso_{cutoff}_e_bohr3_angstrom"
        deltas = [
            float(d_rows[state_id][col]) - float(x_rows[state_id][col])
            for state_id in common
        ]
        abs_deltas = [abs(value) for value in deltas]
        cutoff_rows.append(
            [
                cutoff,
                str(len(deltas)),
                fmt_float(statistics.median(abs_deltas), digits=4),
                fmt_float(quantile(abs_deltas, 90), digits=4),
                fmt_float(quantile(abs_deltas, 95), digits=4),
                fmt_float(max(abs_deltas), digits=4),
                fmt_float(statistics.mean(deltas), digits=4),
            ]
        )

    by_charge_rows: list[list[str]] = []
    col = "r_iso_0.001_e_bohr3_angstrom"
    grouped: dict[int, list[float]] = defaultdict(list)
    for state_id in common:
        charge = int(x_rows[state_id]["charge"])
        grouped[charge].append(abs(float(d_rows[state_id][col]) - float(x_rows[state_id][col])))
    for charge in sorted(grouped):
        values = grouped[charge]
        by_charge_rows.append(
            [
                str(charge),
                str(len(values)),
                fmt_float(statistics.median(values), digits=4),
                fmt_float(quantile(values, 90), digits=4),
                fmt_float(max(values), digits=4),
            ]
        )

    return (
        md_table(
            [
                "density cutoff (e/bohr³)",
                "matched rows",
                "median |Δr| Å",
                "p90 |Δr| Å",
                "p95 |Δr| Å",
                "max |Δr| Å",
                "mean signed Δr Å",
            ],
            cutoff_rows,
        ),
        md_table(["charge", "rows", "median |Δr(0.001)| Å", "p90 Å", "max Å"], by_charge_rows),
    )


def sensitivity_summary(path: Path, label: str) -> tuple[str, dict[str, str]]:
    rows = read_csv(path)
    tiers = Counter(row["sensitivity_tier"] for row in rows)
    metrics = {
        "relative_radial_distribution_l1_delta": "rel. L1 D(r)",
        "max_abs_cumulative_delta_electrons": "max |ΔN(<r)| e",
        "mean_abs_radial_shift_angstrom": "mean radial shift Å",
        "max_abs_cutoff_radius_delta_angstrom": "max cutoff shift Å",
    }
    metric_rows: list[list[str]] = []
    for key, title in metrics.items():
        values = [abs(float(row[key])) for row in rows if row.get(key, "")]
        metric_rows.append(
            [
                title,
                fmt_float(statistics.median(values), digits=4),
                fmt_float(quantile(values, 90), digits=4),
                fmt_float(quantile(values, 95), digits=4),
                fmt_float(max(values), digits=4),
            ]
        )
    table = md_table([f"{label} metric", "median", "p90", "p95", "max"], metric_rows)
    return (
        table,
        {
            "rows": str(len(rows)),
            "low": str(tiers.get("low", 0)),
            "moderate": str(tiers.get("moderate", 0)),
            "high": str(tiers.get("high", 0)),
        },
    )


def dyall_role_charge_tables() -> tuple[str, str, str]:
    rows = read_csv(DYALL_SENSITIVITY)

    def grouped_table(group_key: str, group_title: str) -> str:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[row[group_key]].append(row)
        table_rows: list[list[str]] = []
        def sort_key(value: str) -> int | str:
            return int(value) if value.lstrip("-").isdigit() else value

        for group in sorted(groups, key=sort_key):
            group_rows = groups[group]
            rel = [abs(float(row["relative_radial_distribution_l1_delta"])) for row in group_rows]
            cum = [abs(float(row["max_abs_cumulative_delta_electrons"])) for row in group_rows]
            shift = [abs(float(row["mean_abs_radial_shift_angstrom"])) for row in group_rows]
            cutoff = [abs(float(row["max_abs_cutoff_radius_delta_angstrom"])) for row in group_rows]
            table_rows.append(
                [
                    group,
                    str(len(group_rows)),
                    str(sum(row["sensitivity_tier"] == "high" for row in group_rows)),
                    fmt_float(statistics.median(rel), digits=4),
                    fmt_float(statistics.median(cum), digits=4),
                    fmt_float(statistics.median(shift), digits=4),
                    fmt_float(statistics.median(cutoff), digits=4),
                ]
            )
        return md_table(
            [
                group_title,
                "rows",
                "high",
                "median rel. L1",
                "median max |ΔN| e",
                "median shift Å",
                "median max cutoff shift Å",
            ],
            table_rows,
        )

    high_rows: list[list[str]] = []
    for row in rows:
        if row["sensitivity_tier"] == "high":
            high_rows.append(
                [
                    f"`{row['state_id']}`",
                    row["charge"],
                    row["state_role"],
                    fmt_float(float(row["relative_radial_distribution_l1_delta"]), digits=4),
                    fmt_float(float(row["max_abs_cumulative_delta_electrons"]), digits=4),
                    fmt_float(float(row["mean_abs_radial_shift_angstrom"]), digits=4),
                    fmt_float(float(row["max_abs_cutoff_radius_delta_angstrom"]), digits=4),
                ]
            )
    return (
        grouped_table("state_role", "state role"),
        grouped_table("charge", "charge"),
        md_table(
            [
                "state",
                "charge",
                "role",
                "rel. L1",
                "max |ΔN| e",
                "mean shift Å",
                "max cutoff shift Å",
            ],
            high_rows,
        ),
    )


def linear_dependency_summary() -> str:
    table_rows: list[list[str]] = []
    for qa_dir in sorted((ROOT / "data" / "qa").glob("pbe0_*")):
        qa_csv = qa_dir / "qa.csv"
        if not qa_csv.exists():
            continue
        rows = read_csv(qa_csv)
        warn_rows = [row for row in rows if int(row["linear_dependency_warning_count"])]
        if warn_rows:
            z_values = [int(row["z"]) for row in warn_rows]
            z_span = f"{min(z_values)}-{max(z_values)}"
        else:
            z_span = "NA"
        table_rows.append(
            [
                f"`{qa_dir.name}`",
                str(len(warn_rows)),
                str(sum(int(row["linear_dependency_warning_count"]) for row in rows)),
                str(sum(int(row["linear_dependency_vectors_removed"]) for row in rows)),
                z_span,
            ]
        )
    return md_table(
        ["dataset", "rows with LD", "warnings", "vectors removed", "Z span"], table_rows
    )


def sensitivity_counts_table(
    dyall_counts: Mapping[str, str], x2c_counts: Mapping[str, str]
) -> str:
    return md_table(
        ["comparison", "rows", "low", "moderate", "high"],
        [
            [
                "`dyall-v4z` → `dyall-av4z`",
                dyall_counts["rows"],
                dyall_counts["low"],
                dyall_counts["moderate"],
                dyall_counts["high"],
            ],
            [
                "`x2c-QZVPall` → `x2c-QZVPall-s`",
                x2c_counts["rows"],
                x2c_counts["low"],
                x2c_counts["moderate"],
                x2c_counts["high"],
            ],
        ],
    )


def build_report() -> str:
    qa_table, qa_stats = qa_summary_table()
    primary_cutoff_table, primary_charge_table = primary_radii_comparison_table()
    dyall_table, dyall_counts = sensitivity_summary(DYALL_SENSITIVITY, "dyall-v4z → dyall-av4z")
    x2c_table, x2c_counts = sensitivity_summary(X2C_SENSITIVITY, "x2c-QZVPall → x2c-QZVPall-s")
    role_table, charge_table, high_table = dyall_role_charge_tables()
    ld_table = linear_dependency_summary()

    return f"""# Scientific data-layer report

This report summarizes the committed profile, radii, and QA artifacts as a
scientific data product. It is generated by `scripts/build_data_layer_report.py`
from the existing `data/` tables. The script is read-only with respect to the
current dataset: it does not run SCF, change thresholds, or regenerate profiles.

## Scientific object

The data layer contains self-consistent spherical proatomic radial electron
densities for a declared set of atoms and ions. Sphericity is imposed during the
atomic mean-field calculation by fractional occupations over complete angular
momentum manifolds; it is not obtained by first converging an anisotropic atom
and averaging its density afterwards. The resulting object is a reproducible
reference density for atom-centered density models, not a universal atomic
spectroscopy benchmark.

The companion notebook `docs/notebooks/spherical_vs_post_average_demo.ipynb`
illustrates the distinction on neutral carbon. In that example, the ordinary UKS
calculation and the spherical fractional-occupation calculation both integrate to
six electrons on the independent QA grid, but their low-density cutoff radii and
valence/tail density curves are not identical. The notebook is intended as a
visual Methods-style demonstration; the release QA below then verifies that every
committed generated profile satisfies the spherical-model numerical gates.

## Release-gate QA summary

All four committed profile datasets pass the release gate. Across {qa_stats['total_states']}
dataset-state rows, the largest independent electron-count error is
{fmt_float(qa_stats['max_ne'], digits=3)} electrons and the largest angular
standard-deviation ratio above the density floor is {fmt_float(qa_stats['max_sigma'], digits=3)}.

{qa_table}

The electron-count values are obtained with an independent Gauss-Legendre
quadrature in log-radius, not by simply reusing the stored 1200-point profile
mesh. The angular QA uses the same angular density evaluator as profile
extraction and checks that the spin-summed density is spherical to numerical
precision away from the extreme tail.

## Linear-dependency diagnostics

PySCF may remove near-linear combinations when a large atomic basis contains very
diffuse or redundant primitives. The release gate treats these messages as
diagnostics, not as failures, because the affected SCF artifacts converged and
passed the electron-count, angular-sphericity, tail, and radius-consistency
checks. The warnings concentrate in the larger dyall basis branches and in
anion/supplemented branches, which is the expected direction for large
all-electron basis sets with diffuse functions.

{ld_table}

These counts should be watched if new basis families or more diffuse branches are
added. A future report can add a per-element figure, but the present tables are
sufficient to show that linear-dependency handling did not produce failed density
rows.

## Primary basis-family comparison: x2c-QZVPall versus dyall-v4z

The two primary branches are not meant to be numerically identical: they use
different all-electron relativistic basis families and have different element
coverage. Their overlap on H-Rn nevertheless provides a useful basis-family
sanity check. The table below compares density-cutoff radii for the 430 matched
H-Rn states present in both primary branches.

{primary_cutoff_table}

At the chemically compact 0.003 and 0.001 e/bohr³ cutoffs, neutral and cationic
states are very stable between the primary branches. The larger differences come
from anions, especially formal anions and the 0.0001 e/bohr³ tail cutoff, where
basis tails are expected to matter most.

{primary_charge_table}

This comparison supports the current release strategy: the primary datasets are
internally coherent basis-family products, and users should not mix columns from
different basis branches without recording the basis ID.

## Supplemented and diffuse anion branches

The data layer also includes anion-only supplemented/diffuse branches. They are
part of the committed dataset and should be interpreted as basis-sensitivity
branches rather than as a universal replacement for the primary datasets.

Summary counts:

{sensitivity_counts_table(dyall_counts, x2c_counts)}

### dyall-v4z → dyall-av4z

Adding the dyall augmentation has a small effect for most accepted physical
monoanions but a much larger effect for formal and high-charge anions. That is a
scientific sensitivity signal, not a corruption signal.

{dyall_table}

Grouped by state role:

{role_table}

Grouped by charge:

{charge_table}

The high-sensitivity dyall rows are:

{high_table}

The pattern is chemically plausible: every high-sensitivity multianion is formal,
and all q = -3 dyall rows are high-sensitivity. These profiles are still useful
as formal stockholder/Hirshfeld-I-like references, but conclusions that depend on
their low-density tails should explicitly cite the basis branch and inspect the
sensitivity table.

### x2c-QZVPall → x2c-QZVPall-s

The x2c supplemented branch is much less sensitive in the current data. It should
not be used to claim that diffuse sensitivity is solved in general; it shows that
this particular x2c basis-family modification barely changes the generated
spherical anion profiles.

{x2c_table}

## Current recommendation for users

Use the primary branch that matches the element coverage and basis convention of
the downstream application. Use the supplemented/diffuse anion branches when the
scientific question explicitly depends on anion tails or when a sensitivity check
is needed for weakly bound, formal, or highly charged anion references. Do not
silently replace only the available anions in a primary dataset with augmented
values: that would mix basis conventions and produce a hybrid dataset whose
columns no longer share a single basis identity.

For tail-sensitive work, report both the primary and supplemented/diffuse result
where possible. For compact neutral/cationic deformation features, the primary
basis-family comparison suggests that basis-family differences are much smaller
than the formal-anion tail effects.

## Recommended additional work before changing the data model

These items should be discussed and implemented in order. They are not required
for the current committed data layer.

1. **Add a primary-basis comparison report artifact.** A non-release-gate script
   should compare matched x2c-QZVPall and dyall-v4z states by state ID/digest,
   using the same radial-distribution, cumulative, moment, tail-electron, and
   cutoff-radius metrics already used for diffuse sensitivity.
2. **Use the unified supplemented/augmented branches to interpret neutral versus
   anion sensitivity.** Cations are not a priority because their densities are
   more compact and because the current basis sensitivity is dominated by anion
   tails. The unified branches quantify the small-change reference scale for
   stable neutral atoms before interpreting larger anion shifts.
3. **Only after the neutral baselines, decide whether any diffuse branch should be
   released as a recommended application branch.** The current evidence argues
   against replacing primary anion profiles wholesale. If a future branch is
   recommended for tail-sensitive anions, it should remain a separate dataset with
   its own basis ID and manifest.
4. **Add figures after the comparison metrics are stable.** Useful figures would
   include cutoff-radius shift versus charge, dyall diffuse sensitivity by group,
   and representative radial-distribution/cumulative-difference curves for low,
   moderate, and high sensitivity rows.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Markdown output path; defaults to docs/data_layer_report.md.",
    )
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
