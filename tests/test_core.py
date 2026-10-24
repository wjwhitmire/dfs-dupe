import math

import pytest

from dfs_dupe import (
    EXAMPLE_FIELD,
    EXAMPLE_PRIZES,
    EXAMPLES,
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


def lineup(owns=None, salaries=None, positions=None):
    positions = positions or ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"]
    owns = owns or [10.0] * 9
    salaries = salaries or [5556] * 8 + [5552]  # exactly 50,000
    return [Player(f"P{i}", positions[i], owns[i], salaries[i]) for i in range(9)]


def brute_binom(n, p, k):
    return math.comb(n, k) * p**k * (1 - p) ** (n - k)


# ---- p0 product ----

def test_p0_product_simple():
    assert base_probability([10] * 9) == pytest.approx(1e-9, rel=1e-12)


def test_p0_product_mixed():
    owns = [18, 38, 26, 31, 24, 29, 21, 35, 16]
    expected = 1.0
    for o in owns:
        expected *= o / 100
    assert base_probability(owns) == pytest.approx(expected, rel=1e-12)


def test_p0_all_100_is_one():
    assert base_probability([100] * 9) == pytest.approx(1.0)


def test_p0_order_invariant():
    owns = [18, 38, 26, 31, 24, 29, 21, 35, 16]
    assert base_probability(owns) == pytest.approx(base_probability(list(reversed(owns))), rel=1e-14)


def test_p0_does_not_depend_on_flex_slot():
    # Same 9 players, FLEX RB vs listing order changed: lineups are sets, so p is identical.
    a = lineup(owns=[18, 38, 26, 31, 24, 29, 21, 35, 16])
    b = [a[0], a[7], a[2], a[3], a[4], a[5], a[6], a[1], a[8]]
    ra = analyze(a, 1000)
    rb = analyze(b, 1000)
    assert ra["p"] == pytest.approx(rb["p"], rel=1e-14)


# ---- salary factor ----

def test_salary_factor_zero_remaining():
    assert salary_factor(0) == 1.0


def test_salary_factor_one_decay():
    assert salary_factor(1500) == pytest.approx(math.exp(-1))


def test_salary_factor_custom_decay():
    assert salary_factor(600, 300) == pytest.approx(math.exp(-2))


def test_salary_factor_negative_remaining_clamped():
    assert salary_factor(-200) == 1.0


def test_salary_factor_bad_decay():
    with pytest.raises(LineupError):
        salary_factor(100, 0)


def test_analyze_uses_remaining_salary():
    r = analyze(lineup(salaries=[5000] * 9), 100)  # 45,000 used, 5,000 left
    assert r["remaining"] == 5000
    assert r["salary_factor"] == pytest.approx(math.exp(-5000 / 1500))
    assert r["p"] == pytest.approx(1e-9 * math.exp(-5000 / 1500))


def test_p_capped_at_one():
    assert dupe_probability(0.5, 1.0, 5.0) == 1.0


# ---- binomial / poisson ----

@pytest.mark.parametrize("n,p", [(10, 0.3), (50, 0.02), (1, 0.5), (149_999, 4.2e-6), (200, 0.9)])
def test_binomial_pmf_sums_to_one(n, p):
    pmf = binomial_pmf_list(n, p, n)
    assert math.fsum(pmf) == pytest.approx(1.0, abs=1e-12)


def test_binomial_matches_closed_form():
    pmf = binomial_pmf_list(20, 0.15, 20)
    for k in range(21):
        assert pmf[k] == pytest.approx(brute_binom(20, 0.15, k), rel=1e-10)


def test_binomial_edge_cases():
    assert binomial_pmf_list(0, 0.4, 3) == [1.0, 0.0, 0.0, 0.0]
    assert binomial_pmf_list(5, 0.0, 3) == [1.0, 0.0, 0.0, 0.0]
    assert binomial_pmf_list(2, 1.0, 3) == [0.0, 0.0, 1.0, 0.0]


def test_poisson_sums_to_one():
    assert math.fsum(poisson_pmf_list(3.7, 80)) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("lam", [0.05, 0.6, 2.0, 6.0])
def test_poisson_close_for_large_n(lam):
    n = 1_000_000
    b = binomial_pmf_list(n, lam / n, 30)
    q = poisson_pmf_list(lam, 30)
    # Le Cam: total variation <= n p^2 = lam^2 / n
    tv = 0.5 * sum(abs(x - y) for x, y in zip(b, q))
    assert tv <= lam**2 / n + 1e-12
    assert max(abs(x - y) for x, y in zip(b, q)) < 1e-5


def test_analyze_bins_sum_to_one_and_close():
    r = analyze(EXAMPLES["chalk"], EXAMPLE_FIELD, EXAMPLE_PRIZES)
    assert len(r["binomial"]) == 11
    assert math.fsum(r["binomial"]) == pytest.approx(1.0, abs=1e-12)
    assert math.fsum(r["poisson"]) == pytest.approx(1.0, abs=1e-12)
    assert r["max_abs_diff"] < 1e-5
    assert r["binomial"][0] == pytest.approx(r["p_unique"], rel=1e-12)


def test_expected_and_unique():
    r = analyze(lineup(), 1001)
    p = 1e-9
    assert r["expected_dupes"] == pytest.approx(1000 * p)
    assert r["p_unique"] == pytest.approx((1 - p) ** 1000, rel=1e-12)


# ---- tie split payout ----

def test_tie_split_basic():
    prizes = [100, 50, 25, 15, 10]
    assert tie_split(prizes, 1) == 100
    assert tie_split(prizes, 2) == 75
    assert tie_split(prizes, 3) == pytest.approx(175 / 3)
    assert tie_split(prizes, 5) == 40


def test_tie_split_beyond_table_uses_last_prize():
    assert tie_split([100, 50, 10], 5) == pytest.approx((100 + 50 + 10 + 10 + 10) / 5)


def test_expected_first_payout_matches_direct_sum():
    prizes = [100_000, 50_000, 25_000, 15_000, 10_000]
    for n, p in [(30, 0.05), (12, 0.4), (149_999, 4.22e-6), (149_999, 3e-5), (4, 0.9)]:
        pmf = binomial_pmf_list(n, p, n)
        direct = math.fsum(pmf[k] * tie_split(prizes, k + 1) for k in range(n + 1))
        assert expected_first_payout(n, p, prizes) == pytest.approx(direct, rel=1e-10)


def test_expected_first_payout_hand_case():
    # n = 1 opponent, p = 0.5: half the time solo (100), half split 1st+2nd (75).
    assert expected_first_payout(1, 0.5, [100, 50]) == pytest.approx(87.5)


def test_expected_first_payout_no_dupes():
    assert expected_first_payout(1000, 0.0, [100, 50]) == 100
    assert expected_first_payout(0, 0.3, [100, 50]) == 100


def test_expected_first_payout_certain_dupes():
    assert expected_first_payout(2, 1.0, [90, 60, 30]) == 60


def test_single_prize_flat():
    assert expected_first_payout(500, 0.01, [100]) == pytest.approx(100)


# ---- validation ----

def test_valid_examples():
    for players in EXAMPLES.values():
        validate_lineup(players)


def test_wrong_count():
    with pytest.raises(LineupError) as e:
        validate_lineup(lineup()[:8])
    assert e.value.code == "count"


def test_two_qbs():
    pos = ["QB", "QB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"]
    with pytest.raises(LineupError) as e:
        validate_lineup(lineup(positions=pos))
    assert e.value.code == "position"


def test_flex_cannot_be_qb_or_dst():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST", "DST"]
    with pytest.raises(LineupError):
        validate_lineup(lineup(positions=pos))


def test_flex_te_ok_and_slots():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "DST"]
    out = validate_lineup(lineup(positions=pos))
    assert assign_slots(out) == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]


def test_missing_te():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "WR", "RB", "DST"]
    with pytest.raises(LineupError):
        validate_lineup(lineup(positions=pos))


def test_flex_position_label_rejected():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    with pytest.raises(LineupError) as e:
        validate_lineup(lineup(positions=pos))
    assert e.value.code == "position"


def test_dst_aliases():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "D/ST"]
    out = validate_lineup(lineup(positions=pos))
    assert out[-1].position == "DST"


def test_over_cap():
    with pytest.raises(LineupError) as e:
        validate_lineup(lineup(salaries=[5600] * 9))
    assert e.value.code == "cap"


def test_exactly_cap_ok():
    s = [5556] * 8 + [50_000 - 5556 * 8]
    validate_lineup(lineup(salaries=s))


@pytest.mark.parametrize("bad", [0, -1, 100.01, float("nan"), float("inf")])
def test_ownership_range(bad):
    owns = [10.0] * 8 + [bad]
    with pytest.raises(LineupError) as e:
        validate_lineup(lineup(owns=owns))
    assert e.value.code == "ownership"


def test_duplicate_player():
    pl = lineup()
    pl[1] = Player("P0", "RB", 10, 5500)
    with pytest.raises(LineupError) as e:
        validate_lineup(pl)
    assert e.value.code == "duplicate"


def test_bad_field_and_corr():
    with pytest.raises(LineupError):
        analyze(lineup(), 0)
    with pytest.raises(LineupError):
        analyze(lineup(), 100, corr=6)
    with pytest.raises(LineupError):
        analyze(lineup(), 100, corr=0.4)


def test_prize_validation():
    with pytest.raises(LineupError):
        validate_prizes([])
    with pytest.raises(LineupError):
        validate_prizes([50, 100])
    with pytest.raises(LineupError):
        validate_prizes([100, -1])
    with pytest.raises(LineupError, match="list"):  # review fix: a bare number is not a prize list
        validate_prizes(5)


# ---- extreme ownerships ----

def test_all_100_percent_everyone_duplicates():
    r = analyze(lineup(owns=[100.0] * 9, ), 1000, [100, 50, 25])
    assert r["p"] == 1.0
    assert r["expected_dupes"] == 999
    assert r["p_unique"] == 0.0
    assert r["binomial"][-1] == pytest.approx(1.0)
    assert r["expected_first_payout"] == pytest.approx(tie_split([100, 50, 25], 1000))


def test_tiny_ownership_no_underflow():
    r = analyze(lineup(owns=[0.01] * 9), 150_000, [100, 50])
    assert r["p0"] == pytest.approx(1e-36, rel=1e-9)
    assert r["p0"] > 0
    assert r["p_unique"] == pytest.approx(1.0)
    assert r["expected_first_payout"] == pytest.approx(100)


def test_high_but_not_full_ownership():
    r = analyze(lineup(owns=[90.0] * 9, ), 10_000, EXAMPLE_PRIZES, corr=1.0)
    assert 0 < r["p"] < 1
    assert math.fsum(r["binomial"]) == pytest.approx(1.0, abs=1e-12)
    assert r["binomial"][-1] > 0.99


def test_chalk_more_duplicated_than_contrarian():
    a = analyze(EXAMPLES["chalk"], EXAMPLE_FIELD, EXAMPLE_PRIZES)
    b = analyze(EXAMPLES["contrarian"], EXAMPLE_FIELD, EXAMPLE_PRIZES)
    assert a["expected_dupes"] > 1000 * b["expected_dupes"]
    assert a["expected_first_payout"] < b["expected_first_payout"]


def test_corr_scales_linearly_below_cap():
    a = analyze(EXAMPLES["chalk"], EXAMPLE_FIELD, corr=1.0)
    b = analyze(EXAMPLES["chalk"], EXAMPLE_FIELD, corr=2.5)
    assert b["p"] == pytest.approx(2.5 * a["p"])


def test_tails_match_direct_sums():
    from dfs_dupe.core import binomial_tail, poisson_tail
    for n, p in [(40, 0.2), (149_999, 4.2e-6), (149_999, 3.8e-13), (1000, 0.5)]:
        pmf = binomial_pmf_list(n, p, n)
        direct = math.fsum(pmf[10:])
        assert binomial_tail(n, p, 10) == pytest.approx(direct, rel=1e-9, abs=1e-300)
    for lam in (0.01, 0.63, 8.0):
        pmf = poisson_pmf_list(lam, 400)
        assert poisson_tail(lam, 10) == pytest.approx(math.fsum(pmf[10:]), rel=1e-9, abs=1e-300)


def test_small_tail_not_rounding_noise():
    r = analyze(EXAMPLES["contrarian"], EXAMPLE_FIELD, EXAMPLE_PRIZES)
    assert 0 < r["binomial"][-1] < 1e-60
