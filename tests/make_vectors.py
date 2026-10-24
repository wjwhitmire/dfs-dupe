"""Generate tests/vectors.json from the Python library. Run: python tests/make_vectors.py"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dfs_dupe import (  # noqa: E402
    EXAMPLE_FIELD,
    EXAMPLE_PRIZES,
    EXAMPLES,
    LineupError,
    Player,
    analyze,
    base_probability,
    binomial_pmf_list,
    expected_first_payout,
    poisson_pmf_list,
    salary_factor,
    tie_split,
)


def pl_dict(players):
    return [{"name": p.name, "position": p.position, "ownership": p.ownership, "salary": p.salary} for p in players]


def flat(owns, salaries=None, positions=None):
    positions = positions or ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"]
    salaries = salaries or [5556] * 8 + [5552]
    return [Player(f"P{i}", positions[i], owns[i], salaries[i]) for i in range(9)]


def main():
    cases = []
    specs = []
    for name, players in EXAMPLES.items():
        for corr in (1.0, 2.5):
            for decay in (1500.0, 600.0):
                specs.append((f"{name} c={corr} d={decay}", players, EXAMPLE_FIELD, EXAMPLE_PRIZES, decay, corr))
    specs += [
        ("small field", EXAMPLES["chalk"], 20, [500, 300, 100], 1500.0, 5.0),
        ("single entry", EXAMPLES["chalk"], 1, [100], 1500.0, 1.0),
        ("all 100", flat([100.0] * 9), 1000, [100, 50, 25], 1500.0, 1.0),
        ("tiny own", flat([0.01] * 9), 150_000, [100, 50], 1500.0, 1.0),
        ("high own", flat([90.0] * 9), 10_000, EXAMPLE_PRIZES, 1500.0, 1.0),
        ("salary left", flat([20.0] * 9, [5000] * 9), 500_000, EXAMPLE_PRIZES, 1500.0, 1.0),
        ("te flex", flat([25.0] * 9, positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "DST"]), 50_000, [1000, 500], 1500.0, 0.5),
    ]
    for label, players, n, prizes, decay, corr in specs:
        r = analyze(players, n, prizes, decay=decay, corr=corr)
        cases.append(
            {
                "label": label,
                "input": {"players": pl_dict(players), "field_size": n, "prizes": list(prizes), "decay": decay, "corr": corr},
                "output": r,
            }
        )
    errors = []
    bad_specs = [
        ("count", flat([10.0] * 9)[:8], 100),
        ("position", flat([10.0] * 9, positions=["QB", "QB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"]), 100),
        ("cap", flat([10.0] * 9, [5600] * 9), 100),
        ("ownership", flat([10.0] * 8 + [0.0]), 100),
        ("ownership", flat([10.0] * 8 + [101.0]), 100),
        ("field", flat([10.0] * 9), 0),
    ]
    for code, players, n in bad_specs:
        try:
            analyze(players, n)
        except LineupError as e:
            assert e.code == code, (code, e.code)
            errors.append({"code": code, "input": {"players": pl_dict(players), "field_size": n}})
        else:
            raise SystemExit(f"expected error {code}")

    prims = {
        "base_probability": [{"in": o, "out": base_probability(o)} for o in ([10] * 9, [18, 38, 26, 31, 24, 29, 21, 35, 16], [0.5] * 9)],
        "salary_factor": [{"in": [r, d], "out": salary_factor(r, d)} for r, d in ((0, 1500), (100, 1500), (1500, 1500), (3200, 1500), (500, 300))],
        "binomial": [{"in": [n, p, 12], "out": binomial_pmf_list(n, p, 12)} for n, p in ((10, 0.3), (149_999, 4.2e-6), (200, 0.05))],
        "poisson": [{"in": [lam, 12], "out": poisson_pmf_list(lam, 12)} for lam in (0.05, 0.63, 4.0)],
        "tie_split": [{"in": [EXAMPLE_PRIZES, g], "out": tie_split(EXAMPLE_PRIZES, g)} for g in (1, 2, 3, 5, 8)],
        "expected_first_payout": [
            {"in": [n, p, EXAMPLE_PRIZES], "out": expected_first_payout(n, p, EXAMPLE_PRIZES)}
            for n, p in ((1, 0.5), (149_999, 4.22e-6), (149_999, 3e-5), (12, 0.4))
        ],
    }
    out = {"tolerance_rel": 1e-9, "tolerance_abs": 1e-15, "cases": cases, "errors": errors, "primitives": prims}
    path = ROOT / "tests" / "vectors.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {path.relative_to(ROOT)}: {len(cases)} cases, {len(errors)} error cases")


if __name__ == "__main__":
    main()
