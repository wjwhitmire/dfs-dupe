"""Core math for the lineup duplication estimator.

Heuristic model, not a measurement:

    p0 = prod_i (ownership_i / 100)            over the 9 rostered players
    s  = exp(-remaining_salary / decay)         salary-left-on-table discount
    c  = chalk correlation multiplier           stacking raises duplication
    p  = min(1, p0 * s * c)                     chance one opponent entry equals yours
    E  = (N - 1) * p                            expected opponents holding your lineup
    P(unique) = (1 - p) ** (N - 1)
    k ~ Binomial(N - 1, p)                      number of opponents holding your lineup

Every function here is pure and mirrors the JavaScript core in web/app.html.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

SALARY_CAP = 50_000
DEFAULT_DECAY = 1_500.0
DEFAULT_CORR = 1.0
CORR_MIN = 0.5
CORR_MAX = 5.0
MAX_FIELD = 10_000_000
DIST_BINS = 10  # bins k = 0..9 exact, plus one "10+" tail bin

POSITIONS = ("QB", "RB", "WR", "TE", "DST")
POSITION_ALIASES = {
    "QB": "QB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "DST": "DST",
    "D/ST": "DST",
    "DEF": "DST",
    "D": "DST",
}


class LineupError(ValueError):
    """Raised when a lineup or contest input is invalid.

    ``code`` is a short machine-readable tag shared with the JavaScript core.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Player:
    name: str
    position: str
    ownership: float  # percent, 0 < x <= 100
    salary: float


def normalize_position(pos: str) -> str:
    key = str(pos).strip().upper().replace(" ", "")
    if key not in POSITION_ALIASES:
        raise LineupError(
            "position",
            f"Unknown position '{pos}'. Use QB, RB, WR, TE or DST (FLEX is a slot, "
            "so list the player's real position: RB, WR or TE).",
        )
    return POSITION_ALIASES[key]


def _finite(x: float) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_lineup(players: Sequence[Player], cap: float = SALARY_CAP) -> list[Player]:
    """Check a DraftKings-style NFL Classic roster.

    Slots: QB, RB, RB, WR, WR, WR, TE, FLEX (RB/WR/TE), DST. Returns players with
    normalized positions. Raises LineupError on the first problem found.
    """
    if len(players) != 9:
        raise LineupError("count", f"A Classic lineup has exactly 9 players; got {len(players)}.")
    out: list[Player] = []
    seen: set[str] = set()
    for i, pl in enumerate(players, start=1):
        name = str(pl.name).strip()
        if not name:
            raise LineupError("name", f"Player {i} has no name.")
        if name.lower() in seen:
            raise LineupError("duplicate", f"'{name}' appears more than once.")
        seen.add(name.lower())
        pos = normalize_position(pl.position)
        if not _finite(pl.ownership) or not (0 < pl.ownership <= 100):
            raise LineupError(
                "ownership",
                f"{name}: ownership must be a number above 0 and at most 100 (got {pl.ownership}).",
            )
        if not _finite(pl.salary) or pl.salary <= 0:
            raise LineupError("salary", f"{name}: salary must be a positive number (got {pl.salary}).")
        out.append(Player(name, pos, float(pl.ownership), float(pl.salary)))

    counts = {p: 0 for p in POSITIONS}
    for pl in out:
        counts[pl.position] += 1
    flex_pool = counts["RB"] + counts["WR"] + counts["TE"]
    ok = (
        counts["QB"] == 1
        and counts["DST"] == 1
        and counts["RB"] >= 2
        and counts["WR"] >= 3
        and counts["TE"] >= 1
        and flex_pool == 7
    )
    if not ok:
        raise LineupError(
            "position",
            "Positions must fill QB, RB, RB, WR, WR, WR, TE, FLEX (RB/WR/TE), DST. Got "
            + ", ".join(f"{p} x{counts[p]}" for p in POSITIONS)
            + ".",
        )
    total = sum(pl.salary for pl in out)
    if total > cap:
        raise LineupError("cap", f"Total salary {total:,.0f} is over the {cap:,.0f} cap.")
    return out


def assign_slots(players: Sequence[Player]) -> list[str]:
    """Return a display slot for each player (QB, RB, WR, TE, FLEX, DST).

    Purely cosmetic: duplication math does not depend on slot assignment.
    """
    need = {"RB": 2, "WR": 3, "TE": 1}
    slots = []
    for pl in players:
        if pl.position in need:
            if need[pl.position] > 0:
                need[pl.position] -= 1
                slots.append(pl.position)
            else:
                slots.append("FLEX")
        else:
            slots.append(pl.position)
    return slots


def base_probability(ownerships_pct: Iterable[float]) -> float:
    """p0 = product of ownership fractions, computed in log space."""
    s = 0.0
    for o in ownerships_pct:
        s += math.log(o / 100.0)
    return math.exp(s)


def salary_factor(remaining: float, decay: float = DEFAULT_DECAY) -> float:
    """s = exp(-remaining / decay). remaining below 0 is treated as 0."""
    if not _finite(decay) or decay <= 0:
        raise LineupError("decay", "Salary decay must be a positive number.")
    r = max(0.0, float(remaining))
    return math.exp(-r / decay)


def dupe_probability(p0: float, s: float, c: float) -> float:
    return min(1.0, p0 * s * c)


def binomial_pmf_list(n: int, p: float, kmax: int) -> list[float]:
    """P(K = k) for k = 0..kmax, K ~ Binomial(n, p), via a log-space recurrence.

    log P(0) = n log(1 - p);  log P(k+1) = log P(k) + log(n - k) - log(k + 1) + log(p / (1 - p)).
    """
    out = [0.0] * (kmax + 1)
    if n <= 0 or p <= 0:
        out[0] = 1.0
        return out
    if p >= 1:
        if n <= kmax:
            out[n] = 1.0
        return out
    q = math.log1p(-p)
    lr = math.log(p) - q
    lp = n * q
    for k in range(kmax + 1):
        if k > n:
            break
        out[k] = math.exp(lp)
        if k < n:
            lp += math.log(n - k) - math.log(k + 1) + lr
    return out


def poisson_pmf_list(lam: float, kmax: int) -> list[float]:
    """P(K = k) for k = 0..kmax, K ~ Poisson(lam), log-space recurrence."""
    out = [0.0] * (kmax + 1)
    if lam <= 0:
        out[0] = 1.0
        return out
    ll = math.log(lam)
    lp = -lam
    for k in range(kmax + 1):
        out[k] = math.exp(lp)
        lp += ll - math.log(k + 1)
    return out


def _tail_sum(log_first: float, step, start: int, stop: int, mean: float) -> float:
    """Sum exp(log P(k)) for k = start..stop, walking the log-space recurrence `step`."""
    total = 0.0
    lp = log_first
    k = start
    while k <= stop:
        w = math.exp(lp)
        total += w
        if k >= mean and (w == 0.0 or w <= total * 1e-17):
            break
        lp += step(k)
        k += 1
    return total


def binomial_tail(n: int, p: float, start: int) -> float:
    """P(K >= start), K ~ Binomial(n, p).

    When the tail is large (> 1e-6) it is 1 - sum(head), which is exact to rounding.
    When it is small, 1 - sum(head) is dominated by cancellation error, so the tail
    terms are summed directly (the mean is then small and the terms fall off fast).
    """
    if start <= 0:
        return 1.0
    if n < start or p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    head = binomial_pmf_list(n, p, start - 1)
    t = 1.0 - math.fsum(head)
    if t > 1e-6:
        return t
    q = math.log1p(-p)
    lr = math.log(p) - q
    lp = n * q
    for k in range(start):
        lp += math.log(n - k) - math.log(k + 1) + lr
    return _tail_sum(lp, lambda k: math.log(n - k) - math.log(k + 1) + lr, start, n, n * p)


def poisson_tail(lam: float, start: int) -> float:
    """P(K >= start), K ~ Poisson(lam). Same strategy as binomial_tail."""
    if start <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    head = poisson_pmf_list(lam, start - 1)
    t = 1.0 - math.fsum(head)
    if t > 1e-6:
        return t
    ll = math.log(lam)
    lp = -lam
    for k in range(start):
        lp += ll - math.log(k + 1)
    return _tail_sum(lp, lambda k: ll - math.log(k + 1), start, 10**12, lam)


def validate_prizes(prizes: Sequence[float]) -> list[float]:
    if not isinstance(prizes, (list, tuple)):
        raise LineupError("prizes", "Prizes must be a list of numbers, 1st place first.")
    if len(prizes) == 0:
        raise LineupError("prizes", "Enter at least one prize (first place).")
    out = []
    for i, x in enumerate(prizes, start=1):
        if not _finite(x) or x < 0:
            raise LineupError("prizes", f"Prize for place {i} must be a number of 0 or more.")
        if out and x > out[-1]:
            raise LineupError("prizes", f"Prize for place {i} is larger than place {i - 1}; list prizes from 1st down.")
        out.append(float(x))
    return out


def tie_split(prizes: Sequence[float], group: int) -> float:
    """Average prize when `group` entries tie for first: mean of places 1..group.

    Places beyond the entered table are valued at the last entered prize.
    """
    m = len(prizes)
    if group <= m:
        return math.fsum(prizes[:group]) / group
    return (math.fsum(prizes) + (group - m) * prizes[-1]) / group


def expected_first_payout(n: int, p: float, prizes: Sequence[float]) -> float:
    """E[prize | you finish first] = sum_k P(K = k) * tie_split(prizes, k + 1), K ~ Bin(n, p).

    Closed form, no truncation. With m entered prizes, L = prizes[m-1] and
    D = sum(prizes) - m * L, tie_split(g) = L + D / g for every g >= m, so

        E = sum_{k < m} P(k) * (tie_split(k+1) - L - D/(k+1))
            + L + D * E[1/(K+1)],
        E[1/(K+1)] = (1 - (1-p)^(n+1)) / ((n+1) p)     (standard binomial identity).
    """
    if n <= 0 or p <= 0:
        return tie_split(prizes, 1)
    if p >= 1:
        return tie_split(prizes, n + 1)
    m = len(prizes)
    last = prizes[-1]
    d = math.fsum(prizes) - m * last
    head = binomial_pmf_list(n, p, m - 1)
    corr = math.fsum(head[k] * (tie_split(prizes, k + 1) - last - d / (k + 1)) for k in range(m))
    inv_mean = -math.expm1((n + 1) * math.log1p(-p)) / ((n + 1) * p)
    return corr + last + d * inv_mean


def analyze(
    players: Sequence[Player],
    field_size: int,
    prizes: Sequence[float] | None = None,
    cap: float = SALARY_CAP,
    decay: float = DEFAULT_DECAY,
    corr: float = DEFAULT_CORR,
) -> dict:
    """Run the full estimate. Returns a plain dict (JSON-serializable)."""
    lineup = validate_lineup(players, cap)
    if not isinstance(field_size, int) or isinstance(field_size, bool) or field_size < 1 or field_size > MAX_FIELD:
        raise LineupError("field", f"Field size must be a whole number from 1 to {MAX_FIELD:,}.")
    if not _finite(corr) or corr < CORR_MIN or corr > CORR_MAX:
        raise LineupError("corr", f"Chalk correlation must be between {CORR_MIN} and {CORR_MAX}.")
    prize_list = validate_prizes(prizes if prizes is not None else [1.0])

    total_salary = math.fsum(pl.salary for pl in lineup)
    remaining = cap - total_salary
    p0 = base_probability(pl.ownership for pl in lineup)
    s = salary_factor(remaining, decay)
    p = dupe_probability(p0, s, corr)
    n = field_size - 1
    expected = n * p
    if p >= 1:
        p_unique = 0.0 if n > 0 else 1.0
    else:
        p_unique = math.exp(n * math.log1p(-p))
    binom = binomial_pmf_list(n, p, DIST_BINS - 1) + [binomial_tail(n, p, DIST_BINS)]
    pois = poisson_pmf_list(expected, DIST_BINS - 1) + [poisson_tail(expected, DIST_BINS)]
    max_diff = max(abs(a - b) for a, b in zip(binom, pois))
    solo = prize_list[0]
    exp_first = expected_first_payout(n, p, prize_list)
    return {
        "total_salary": total_salary,
        "remaining": remaining,
        "p0": p0,
        "salary_factor": s,
        "corr": corr,
        "p": p,
        "expected_dupes": expected,
        "p_unique": p_unique,
        "binomial": binom,
        "poisson": pois,
        "max_abs_diff": max_diff,
        "solo_prize": solo,
        "expected_first_payout": exp_first,
        "payout_ratio": exp_first / solo if solo > 0 else 1.0,
        "slots": assign_slots(lineup),
    }
