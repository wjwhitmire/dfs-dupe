"""Lineup Dupe Check: heuristic duplicate-lineup estimator for NFL Classic DFS contests."""

from .core import (
    DEFAULT_CORR,
    DEFAULT_DECAY,
    SALARY_CAP,
    LineupError,
    Player,
    analyze,
    assign_slots,
    base_probability,
    binomial_pmf_list,
    dupe_probability,
    expected_first_payout,
    poisson_pmf_list,
    salary_factor,
    tie_split,
    validate_lineup,
    validate_prizes,
)
from .examples import EXAMPLE_FIELD, EXAMPLE_PRIZES, EXAMPLES

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_CORR",
    "DEFAULT_DECAY",
    "SALARY_CAP",
    "EXAMPLES",
    "EXAMPLE_FIELD",
    "EXAMPLE_PRIZES",
    "LineupError",
    "Player",
    "analyze",
    "assign_slots",
    "base_probability",
    "binomial_pmf_list",
    "dupe_probability",
    "expected_first_payout",
    "poisson_pmf_list",
    "salary_factor",
    "tie_split",
    "validate_lineup",
    "validate_prizes",
]
