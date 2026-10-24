"""Command line: python -m dfs_dupe.cli lineup.csv --field 150000 --prizes 100000,50000,25000"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import DEFAULT_CORR, DEFAULT_DECAY, LineupError, analyze
from .parsing import MAX_BYTES, parse_json, parse_number, parse_players_text


def _prizes(s: str) -> list[float]:
    return [parse_number(x) for x in s.split(",") if x.strip()]


def _json_number(key: str, v, default):
    """A number from the JSON file, or a LineupError naming the key."""
    if v is None:
        return default
    x = parse_number(v)
    if x != x:  # NaN
        raise LineupError(key, f"'{key}' in the JSON file must be a number (got {v!r}).")
    return x


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dfs-dupe",
        description="Estimate how many other entries hold your exact NFL Classic lineup (heuristic).",
    )
    ap.add_argument("file", help="CSV/TSV (name, position, ownership, salary) or JSON")
    ap.add_argument("--field", type=int, help="contest field size N (entries, including yours)")
    ap.add_argument("--prizes", type=_prizes, help="top prizes, 1st first, comma separated")
    ap.add_argument("--decay", type=float, help=f"salary decay in dollars (default {DEFAULT_DECAY:g})")
    ap.add_argument("--corr", type=float, help=f"chalk correlation multiplier (default {DEFAULT_CORR:g})")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    a = ap.parse_args(argv)

    path = Path(a.file)
    try:
        if path.stat().st_size > MAX_BYTES:
            raise LineupError("file", "File is larger than 5 MB.")
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            raise LineupError("file", "File is not UTF-8 text. Save it as CSV UTF-8 (or plain UTF-8 JSON) and try again.") from None
        if path.suffix.lower() == ".json":
            data = parse_json(text)
        else:
            data = {"players": parse_players_text(text)}
        field = a.field if a.field is not None else data.get("field_size")
        if field is None:
            raise LineupError("field", "Give a field size with --field (or field_size in JSON).")
        if isinstance(field, bool) or not isinstance(field, int):
            raise LineupError("field", f"field_size in the JSON file must be a whole number (got {field!r}).")
        if a.prizes is not None:
            prizes = a.prizes
        else:
            prizes = data.get("prizes", [1.0])
            if not isinstance(prizes, list):
                raise LineupError("prizes", "prizes in the JSON file must be a list of numbers, 1st place first.")
            prizes = [parse_number(x) for x in prizes]
        decay = a.decay if a.decay is not None else _json_number("decay", data.get("decay"), DEFAULT_DECAY)
        corr = a.corr if a.corr is not None else _json_number("corr", data.get("corr"), DEFAULT_CORR)
        r = analyze(data["players"], field, prizes, decay=decay, corr=corr)
    except OSError as e:
        print(f"error: cannot read {a.file}: {e.strerror}", file=sys.stderr)
        return 2
    except (LineupError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print(f"Salary used         {r['total_salary']:,.0f} (remaining {r['remaining']:,.0f})")
    print(f"p0 (ownership prod) {r['p0']:.4e}")
    print(f"salary factor s     {r['salary_factor']:.4f}")
    print(f"correlation c       {r['corr']:.2f}")
    print(f"p (per opponent)    {r['p']:.4e}")
    print(f"expected duplicates {r['expected_dupes']:.4f}")
    print(f"P(unique)           {r['p_unique']:.4f}")
    print("k    binomial   poisson")
    for k, (b, q) in enumerate(zip(r["binomial"], r["poisson"])):
        lab = f"{k}" if k < len(r["binomial"]) - 1 else f"{k}+"
        print(f"{lab:<4} {b:.6f}   {q:.6f}")
    print(f"solo 1st prize      {r['solo_prize']:,.2f}")
    print(f"expected 1st payout {r['expected_first_payout']:,.2f} ({r['payout_ratio'] * 100:.1f}% of solo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
