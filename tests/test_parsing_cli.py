import json

import pytest

from dfs_dupe import LineupError
from dfs_dupe.cli import main
from dfs_dupe.parsing import parse_json, parse_number, parse_players_text

CSV = """Name,Position,Ownership,Salary,Team
QB Alpha,QB,18%,"$6,400",AAA
RB Bravo,RB,38,8600,BBB

RB Charlie,RB,26,6200,CCC
WR Delta,WR,31,7800,DDD
WR Echo,WR,24,5800,EEE
WR Foxtrot,WR,29,4600,FFF
TE Golf,TE,21,4300,GGG
RB Hotel,RB,35,3400,HHH
DST India,DST,16,2800,III
"""


def test_parse_number():
    assert parse_number("18%") == 18
    assert parse_number("$6,400") == 6400
    assert parse_number("abc") != parse_number("abc")  # NaN
    assert parse_number("") != parse_number("")


def test_csv_with_header_blank_lines_extra_columns():
    pl = parse_players_text(CSV)
    assert len(pl) == 9
    assert pl[0].salary == 6400 and pl[0].ownership == 18


def test_tsv_reordered_header():
    tsv = "salary\tname\town\tpos\n" + "\n".join(f"5000\tP{i}\t10\tQB" for i in range(2))
    pl = parse_players_text(tsv)
    assert pl[1].name == "P1" and pl[1].position == "QB" and pl[1].salary == 5000


def test_headerless_csv():
    pl = parse_players_text("A,QB,10,5000\nB,RB,12,6000")
    assert pl[1].ownership == 12


def test_bad_number_message():
    with pytest.raises(LineupError, match="Row 2: ownership 'lots'"):
        parse_players_text("A,QB,10,5000\nB,RB,lots,6000")


def test_missing_header_column():
    with pytest.raises(LineupError, match="salary"):
        parse_players_text("name,position,ownership\nA,QB,10")


def test_short_row():
    with pytest.raises(LineupError, match="Row 1"):
        parse_players_text("A,QB,10")


def test_empty():
    with pytest.raises(LineupError):
        parse_players_text("\n\n")


def test_json_forms():
    d = parse_json('[{"name":"A","position":"QB","ownership":10,"salary":5000}]')
    assert d["players"][0].name == "A"
    d = parse_json('{"players":[], "field_size": 10}')
    assert d["field_size"] == 10
    with pytest.raises(LineupError):
        parse_json("{bad")
    with pytest.raises(LineupError):
        parse_json('{"x":1}')


def test_cli_csv(tmp_path, capsys):
    f = tmp_path / "l.csv"
    f.write_text(CSV)
    assert main([str(f), "--field", "150000", "--prizes", "100000,50000,25000,15000,10000"]) == 0
    out = capsys.readouterr().out
    assert "expected duplicates" in out


def test_cli_json(tmp_path, capsys):
    f = tmp_path / "l.csv"
    f.write_text(CSV)
    assert main([str(f), "--field", "1000", "--json"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["total_salary"] == 49900


def test_cli_errors(tmp_path, capsys):
    f = tmp_path / "l.csv"
    f.write_text(CSV)
    assert main([str(f)]) == 2
    assert main([str(tmp_path / "missing.csv"), "--field", "10"]) == 2
    assert "error" in capsys.readouterr().err


# ---- review fixes: regression tests ----


def test_parse_number_rejects_non_ascii_and_underscore_forms():
    # Same grammar as the browser parser.
    for raw in ("1_000", "١٢", "inf", "nan", "1e400", "0x10"):
        assert parse_number(raw) != parse_number(raw), raw
    assert parse_number(10**400) != parse_number(10**400)  # huge int: NaN, not OverflowError
    assert parse_number("-2.5e1") == -25


def test_csv_with_bom_header_detected():
    pl = parse_players_text("﻿" + CSV)
    assert len(pl) == 9 and pl[0].name == "QB Alpha"


def test_json_deep_nesting_is_lineup_error():
    with pytest.raises(LineupError, match="nested too deeply"):
        parse_json("[" * 200_000)


def _lineup_json(tmp_path, **extra):
    rows = [
        {"name": f"P{i}", "position": p, "ownership": 20, "salary": 5000}
        for i, p in enumerate(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST"])
    ]
    f = tmp_path / "l.json"
    f.write_text(json.dumps({"players": rows, **extra}), encoding="utf-8")
    return f


@pytest.mark.parametrize(
    "extra, msg",
    [
        ({"field_size": 1.9}, "whole number"),
        ({"field_size": True}, "whole number"),
        ({"field_size": "100"}, "whole number"),
        ({"field_size": 100, "prizes": 5}, "must be a list"),
        ({"field_size": 100, "prizes": ["abc"]}, "Prize for place 1"),
        ({"field_size": 100, "decay": "abc"}, "'decay'"),
        ({"field_size": 100, "corr": None}, None),
    ],
)
def test_cli_json_bad_contest_values(tmp_path, capsys, extra, msg):
    rc = main([str(_lineup_json(tmp_path, **extra))])
    err = capsys.readouterr().err
    if msg is None:
        assert rc == 0
    else:
        assert rc == 2 and msg in err and "Traceback" not in err


def test_cli_huge_number_in_json(tmp_path, capsys):
    f = _lineup_json(tmp_path, field_size=100)
    f.write_text(f.read_text().replace('"ownership": 20', '"ownership": 1' + "0" * 400, 1))
    assert main([str(f)]) == 2
    assert "ownership" in capsys.readouterr().err


def test_cli_non_utf8_file(tmp_path, capsys):
    f = tmp_path / "l.csv"
    f.write_bytes("name,position,ownership,salary\n\xd1,QB,10,5000\n".encode("latin-1"))
    assert main([str(f), "--field", "100"]) == 2
    assert "UTF-8" in capsys.readouterr().err
