"""Example slate. Invented players; not real people. Same data as the browser tool."""

from .core import Player

EXAMPLE_FIELD = 150_000
EXAMPLE_PRIZES = [100_000.0, 50_000.0, 25_000.0, 15_000.0, 10_000.0]

EXAMPLES = {
    "chalk": [
        Player("QB Alpha", "QB", 18.0, 6400),
        Player("RB Bravo", "RB", 38.0, 8600),
        Player("RB Charlie", "RB", 26.0, 6200),
        Player("WR Delta", "WR", 31.0, 7800),
        Player("WR Echo", "WR", 24.0, 5800),
        Player("WR Foxtrot", "WR", 29.0, 4600),
        Player("TE Golf", "TE", 21.0, 4300),
        Player("RB Hotel", "RB", 35.0, 3400),
        Player("DST India", "DST", 16.0, 2800),
    ],
    "contrarian": [
        Player("QB Juliet", "QB", 4.0, 5600),
        Player("RB Kilo", "RB", 9.0, 7400),
        Player("RB Lima", "RB", 3.5, 5200),
        Player("WR Mike", "WR", 6.0, 7200),
        Player("WR November", "WR", 2.5, 6000),
        Player("WR Oscar", "WR", 5.0, 5000),
        Player("TE Papa", "TE", 3.0, 3800),
        Player("WR Quebec", "WR", 7.5, 5400),
        Player("DST Romeo", "DST", 4.0, 3200),
    ],
}
