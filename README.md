# Lineup Dupe Check

Estimate how many other entries in a DraftKings-style NFL Classic contest are likely to hold your exact lineup, and what a tie does to the first-place prize if that lineup wins.

Live tool: https://wjwhitmire.github.io/dfs-dupe/

The browser tool runs entirely on your device. Nothing you enter is uploaded. The Python library has no runtime dependencies.

Not affiliated with, endorsed by, or connected to any daily fantasy sports operator. Player names in the examples are invented.

This is a **heuristic estimator, not a measurement**. It turns projected ownership into a rough duplicate count. It does not see real contest entries.

## Roster format

DraftKings-style NFL Classic: QB, RB, RB, WR, WR, WR, TE, FLEX, DST; $50,000 cap. FLEX takes an RB, WR or TE. Enter each player's real position (QB, RB, WR, TE, DST; `D/ST` and `DEF` are accepted) and the FLEX slot is filled automatically.

## Quick start

```
pip install -e .[dev]
pytest -q
dfs-dupe examples/chalk.csv --field 150000 --prizes 100000,50000,25000,15000,10000
```

Input file: one row per player with columns `name, position, ownership, salary`. Comma or tab separated, header optional (columns can be in any order when there is a header), extra columns ignored, `%`, `$` and thousands separators accepted. JSON is also accepted: a list of players, or `{"players": [...], "field_size": 150000, "prizes": [...], "decay": 1500, "corr": 1.0}`.

In the browser, the field size, prizes, decay and correlation you enter are remembered on that device, so they are asked once. A JSON file whose `field_size`, `prizes`, `decay` or `corr` cannot be read is refused with a message naming the key.

Options: `--field N` (total entries, including yours), `--prizes` (1st place first), `--decay` (default 1500), `--corr` (default 1.0), `--json` (full result).

Python:

```python
from dfs_dupe import analyze, EXAMPLES, EXAMPLE_PRIZES
r = analyze(EXAMPLES["chalk"], 150_000, EXAMPLE_PRIZES)
r["expected_dupes"], r["p_unique"], r["expected_first_payout"]
```

## Method

Inputs: for each of the 9 players, projected ownership (percent of the field rostering that player, 0 < x <= 100) and salary. Contest: field size N. Optional: top prize table, salary decay, chalk correlation multiplier.

**1. Base match probability.** Model each opponent entry as choosing each of your nine players independently with probability equal to that player's ownership:

```
p0 = own_1 x own_2 x ... x own_9        (ownership as fractions, computed as exp(sum of logs))
```

A Classic lineup is a set of nine players. Two entries with the same nine players are the same lineup whichever WR slot a receiver sits in, and whichever RB, WR or TE fills FLEX. Ownership already counts a player regardless of the slot he was used in. So no permutation count is multiplied in; doing so would count the same set several times.

**2. Salary remaining.** Most entries in a large field spend $49,500 to $50,000. A lineup that leaves salary unspent is built by fewer people, so:

```
s = exp(-remaining / decay)     remaining = 50,000 - total salary, decay = 1,500 by default
```

At the default, leaving $1,500 unspent multiplies the estimate by e^-1 (about 0.37). A full-cap lineup gets s = 1. The decay is an adjustable input; a larger decay is a smaller penalty.

**3. Chalk correlation.** Real entries are not independent picks. Players stack a quarterback with his receivers and pair popular plays, so chalk combinations appear together more often than the product of ownerships predicts. A plain multiplier `c` (default 1.0, range 0.5 to 5) raises or lowers the estimate for that effect.

**4. Duplicate count.**

```
p          = min(1, p0 x s x c)                 chance one opponent entry equals yours
E          = (N - 1) p                          expected other entries with your lineup
P(unique)  = (1 - p)^(N - 1)
P(K = k)   = C(N-1, k) p^k (1 - p)^(N-1-k)      K ~ Binomial(N - 1, p)
```

The binomial is evaluated exactly in log space with the recurrence `log P(k+1) = log P(k) + log(N-1-k) - log(k+1) + log(p / (1-p))`, starting from `log P(0) = (N-1) log1p(-p)`. The chart and table show k = 0 to 9 and a 10+ tail bin. The tail is `1 - sum(head)` when it is larger than 1e-6, and is summed term by term otherwise so that tiny tails are not rounding noise.

The Poisson approximation with mean E is shown beside it, `P(k) = e^-E E^k / k!`. By Le Cam's inequality the total variation distance between the two is at most (N - 1) p^2, which is far below display precision for any realistic lineup in a large field.

**5. Tie split.** If your lineup finishes first and k others hold it, the k + 1 tied entries split places 1 through k + 1, so each receives `avg(prize_1 .. prize_(k+1))`. Places beyond the prize table you enter are valued at your last entered prize. The expected first-place payout given that you finish first is

```
E[prize | 1st] = sum over k of P(K = k) x avg(prize_1 .. prize_(k+1))
```

It is evaluated in closed form with no truncation. With m entered prizes, last prize L and D = sum(prizes) - m L, every group of g >= m entries receives L + D / g, so

```
E[prize | 1st] = sum_{k < m} P(k) (avg_(k+1) - L - D/(k+1)) + L + D x E[1/(K+1)]
E[1/(K+1)]     = (1 - (1-p)^(n+1)) / ((n+1) p),   n = N - 1
```

The tool compares this to the solo first-place prize.

## Example slate

Both lineups use invented player names, field size 150,000, and top prizes $100,000 / $50,000 / $25,000 / $15,000 / $10,000.

| Lineup | Salary | p | Expected duplicates | P(unique) | Expected 1st prize |
|---|---|---|---|---|---|
| Chalk (ownership 16% to 38%) | 49,900 | 4.22e-6 | 0.63 | 53.1% | $85,736 |
| Contrarian (ownership 2.5% to 9%) | 48,800 | 3.82e-13 | 5.7e-8 | >99.99999% | $100,000 |

## Limits

- Ownership projections are estimates, and the output is very sensitive to them. Nine numbers are multiplied, so a 20% error in every projection compounds to about a factor of 5 in p when they all run high (1.2^9 = 5.2) and about 7 when they all run low (0.8^9 = 0.13).
- Independence is wrong for real fields. Stacks, game environments and shared optimizer settings cluster entries. The correlation multiplier is a single knob, not a model of that structure; the default of 1.0 likely understates duplication for popular stacks.
- Each player is treated as an independent draw even though a real roster cannot exceed its slot counts. For typical ownership levels this is small next to projection error.
- Multi-entry players can submit the same lineup many times, and late swaps change lineups. Neither is modeled.
- The salary factor is a smooth assumption about how the field spends salary. It is not fit to contest data.
- Only the prizes a tie for first can reach affect the payout figure. Places beyond the table you enter are valued at your last entered prize; if the real ladder falls further, the expected payout for heavily duplicated lineups is overstated.
- Results inform contest strategy only. They are not a forecast of winnings.

## Validation

- Exactly 9 players; positions fill QB, RB, RB, WR, WR, WR, TE, FLEX (RB/WR/TE), DST; no player listed twice.
- Total salary at most 50,000. Ownership in (0, 100]. Salary positive. Field size a whole number from 1 to 10,000,000. Correlation 0.5 to 5. Decay positive. Prizes non-negative and non-increasing.
- Tests (`pytest`) cover the p0 product, salary factor, binomial pmf summing to 1 and matching the closed form, Poisson closeness within Le Cam's bound for large N, tail sums, tie-split payout against brute-force sums and hand cases, every validation error, parsing, the CLI, and extreme ownerships (all 100%, all 0.01%, all 90%).
- `tests/make_vectors.py` writes `tests/vectors.json` from the Python library. `web/parity.test.mjs` extracts the JavaScript core from `web/app.html` and checks it against those vectors to 1e-9 relative (1e-15 absolute for values near zero).

## Repo layout

```
src/dfs_dupe/       core.py (math), parsing.py (CSV/JSON), examples.py, cli.py
tests/              pytest suites, make_vectors.py, vectors.json
web/app.html        the browser tool
web/parity.test.mjs JS vs Python parity check (node 20+)
web/build_pages.py  writes docs/index.html for GitHub Pages
```

## License

MIT. Copyright 2026 Will Whitmire.
