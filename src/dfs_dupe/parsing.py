"""Tolerant CSV / JSON parsing for lineup files. Mirrors the browser parser."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from .core import LineupError, Player

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
# Same grammar as the browser parser: ASCII digits only, no underscores, no inf/nan words.
_NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", re.ASCII)

HEADER_KEYS = {
    "name": ("name", "player", "player name"),
    "position": ("position", "pos", "roster position"),
    "ownership": ("ownership", "own", "own%", "ownership%", "projected ownership", "proj own", "pown"),
    "salary": ("salary", "sal", "cost"),
}


def parse_number(raw: Any) -> float:
    """Parse '12.5', '12.5%', '$7,200'. Returns NaN when it is not a number."""
    if isinstance(raw, bool):
        return math.nan
    if isinstance(raw, (int, float)):
        try:
            return float(raw)
        except OverflowError:  # integer too large for a float
            return math.nan
    s = str(raw).strip().replace(",", "").replace("$", "").replace("%", "")
    if not _NUMBER.fullmatch(s):
        return math.nan
    v = float(s)
    return v if math.isfinite(v) else math.nan


def _split(line: str, delim: str) -> list[str]:
    """Split one line, honoring double-quoted fields."""
    out, cur, q = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if q:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    q = False
            else:
                cur.append(ch)
        elif ch == '"':
            q = True
        elif ch == delim:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur).strip())
    return out


def parse_players_text(text: str) -> list[Player]:
    """Parse comma- or tab-separated rows: name, position, ownership, salary.

    A header row is detected when it names the columns (any order). Without a header
    the column order must be name, position, ownership, salary. Extra columns are ignored.
    """
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise LineupError("file", "File is larger than 5 MB.")
    text = text.lstrip("\ufeff")
    lines = [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if not lines:
        raise LineupError("file", "No rows found. Expected name, position, ownership, salary.")
    if len(lines) > MAX_ROWS:
        raise LineupError("file", f"File has more than {MAX_ROWS:,} rows.")
    delim = "\t" if lines[0].count("\t") > lines[0].count(",") else ","
    first = [c.lower() for c in _split(lines[0], delim)]
    idx = {"name": 0, "position": 1, "ownership": 2, "salary": 3}
    start = 0
    if any(c in keys for keys in HEADER_KEYS.values() for c in first):
        found = {}
        for field, keys in HEADER_KEYS.items():
            for j, c in enumerate(first):
                if c in keys:
                    found[field] = j
                    break
        missing = [f for f in HEADER_KEYS if f not in found]
        if missing:
            raise LineupError("file", "Header is missing column(s): " + ", ".join(missing) + ".")
        idx = found
        start = 1
    players = []
    for r, ln in enumerate(lines[start:], start=start + 1):
        cells = _split(ln, delim)
        if len(cells) <= max(idx.values()):
            raise LineupError("file", f"Row {r} has {len(cells)} column(s); need name, position, ownership, salary.")
        own = parse_number(cells[idx["ownership"]])
        sal = parse_number(cells[idx["salary"]])
        if math.isnan(own):
            raise LineupError("file", f"Row {r}: ownership '{cells[idx['ownership']]}' is not a number.")
        if math.isnan(sal):
            raise LineupError("file", f"Row {r}: salary '{cells[idx['salary']]}' is not a number.")
        players.append(Player(cells[idx["name"]], cells[idx["position"]], own, sal))
    return players


def parse_json(text: str) -> dict:
    """Parse JSON: either a list of players or {players, field_size, prizes, decay, corr}."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise LineupError("file", "File is larger than 5 MB.")
    try:
        data = json.loads(text.lstrip("\ufeff"))
    except json.JSONDecodeError as e:
        raise LineupError("file", f"Not valid JSON: {e.msg} (line {e.lineno}).") from None
    except RecursionError:
        raise LineupError("file", "Not valid JSON: nested too deeply. Expected a list of players.") from None
    if isinstance(data, list):
        data = {"players": data}
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise LineupError("file", "JSON must be a list of players or an object with a 'players' list.")
    players = []
    for i, row in enumerate(data["players"], start=1):
        if not isinstance(row, dict):
            raise LineupError("file", f"Player {i} is not an object.")
        players.append(
            Player(
                str(row.get("name", "")),
                str(row.get("position", "")),
                parse_number(row.get("ownership", "")),
                parse_number(row.get("salary", "")),
            )
        )
    out = {"players": players}
    for key in ("field_size", "prizes", "decay", "corr"):
        if key in data:
            out[key] = data[key]
    return out
