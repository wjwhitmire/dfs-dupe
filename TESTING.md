# Testing

This file lists every function of Lineup Dupe Check, how each was tested, and the result. Browser checks ran against the published form of the site (tracked files with the release placeholders filled, `docs/` served under `/dfs-dupe/`), in headless Chromium at 1280 px (light and dark) and 400 px with touch (light and dark). `web/app.html` was also opened from `file://`.

## Numbers checked against independent references

| Check | Reference | Result |
|---|---|---|
| 300 random lineups (ownership 0.01% to 99%, any salary under the cap), field sizes 2 to 10,000,000, 1 to 8 prizes, decay 1 to 10,000, correlation 0.5 to 5 | p0, salary factor and p from the formulas; `scipy.stats.binom` and `scipy.stats.poisson` for k = 0 to 9 and the 10+ tail; expected first prize by direct summation of P(K = k) x average of places 1 to k + 1 | Equal within 1e-7 (distribution 1e-6 relative, 1e-13 absolute) |
| README example table | Chalk p 4.22e-6, 0.63 duplicates, 53.1% unique, $85,736; contrarian $100,000 | Match (the page prints $85,735.88) |
| Hand case | Four identical entries, prizes 100 and 50: (100 + 50 + 50 + 50) / 4 = 62.5 | Match |
| Python and browser cores | `web/parity.test.mjs` | Identical |

## Function inventory

| # | Area | Function | How it was tested | Result |
|---|---|---|---|---|
| 1 | Page | Load with the chalk example | Numbers above; verdict chip; calculation chain | Pass |
| 2 | Page | Light and dark, 400 px layout | No sideways scroll; controls at least 44 px on touch | Pass |
| 3 | Page | Network | No requests except Google Fonts; no CSP violations | Pass |
| 4 | Lineup | Chalk and contrarian examples; example remembered after reload | Pass | Pass |
| 5 | Lineup | 9 rows: name, position, ownership, salary; slot column fills FLEX | QB RB RB WR WR WR TE FLEX DST | Pass |
| 6 | Lineup | Field rules | Ownership 0 and 150, salary over the cap, illegal positions, the same player twice: refused with a message and the field marked | Pass |
| 7 | Contest | Field size | 0, 1.5, 10,000,001 and blank refused; 1 accepted | Pass |
| 8 | Contest | Prizes (8 boxes) | Rising prizes refused; a blank in the middle refused | Pass |
| 9 | Advanced | Decay, correlation slider and box (synced); panel state remembered | Decay 0 and correlation 6 refused | Pass |
| 10 | Results | Tiles, verdict, chain, chart with hover and keyboard tooltip, table, Poisson note | Pass | Pass |
| 11 | Export | Copy results as CSV; fallback | Lineup rows, metrics, distribution | Pass |
| 12 | Input | Load CSV (`$`, `%`, `D/ST`), TSV without header, JSON with contest settings | Values and contest fields applied | Pass |
| 13 | Input | Bad files | 8 rows, bad JSON: message | Pass |
| 14 | Input | JSON with an unreadable `field_size` | Was ignored silently in the browser while the CLI refused it | Pass after fix |
| 15 | file:// | `web/app.html` opened as a file | Example computed | Pass |
| 16 | CLI | README command, `--json --decay --corr`, JSON input with `field_size` | Pass | Pass |
| 17 | CLI | Errors: no field size, field 0, correlation 9, bad `field_size`, missing file | Exit 2 with a message | Pass |
| 18 | Library | `analyze` and helpers | `pytest` | Pass |

## Bugs fixed in this pass

| Bug | Severity | Fix |
|---|---|---|
| A JSON file with an unreadable `field_size`, `prizes`, `decay` or `corr` was accepted and the value silently kept from before | Low | The page refuses the file and names the key, as the CLI does |

## Decisions the app now makes for you

| Decision point | Before | After |
|---|---|---|
| Field size, prizes, decay, correlation | Reset to the example contest on every visit | Asked once; remembered on the device, with a line saying they are from last time |
| FLEX slot | Already worked out from positions | No change |
| Ownership, salary, players | Only you know them | Asked in the table |

## How to rerun

```
pip install -e .[dev] playwright
python -m playwright install chromium
pytest -q
python tests/make_vectors.py && node web/parity.test.mjs
python web/build_pages.py
```

Test counts: 82 Python tests before this pass, 84 after, plus the parity script.

## Known limits

- The JSON prize list fills at most 8 boxes in the page; further places are valued at the last entered prize, as the README describes.
- The estimate is a heuristic; see the README limits.
