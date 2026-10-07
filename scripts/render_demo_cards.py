#!/usr/bin/env python3
"""Render every Pillow card in ``utils/banner.py`` to ``docs/demo/`` as sample PNGs.

The bot generates all broadcast graphics at runtime, so nothing here is required to
run the bot. This script only exists so reviewers and server staff can preview the
full card set without starting Discord, and so the committed samples in
``docs/demo/`` can be regenerated exactly:

    python scripts/render_demo_cards.py

Sample data mirrors the fixtures used by ``tests/test_banners.py``; it is fake
tournament data and contains no real player, student or Garena identity.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.banner import (  # noqa: E402
    generate_booyah_card,
    generate_bounty_poster,
    generate_broadcast_lowerthird_card,
    generate_certificate_card,
    generate_hall_of_fame_card,
    generate_killfeed_card,
    generate_live_stream_card,
    generate_match_banner,
    generate_matchup_clash_card,
    generate_mvp_card,
    generate_player_passport_card,
    generate_points_table_graphic,
    generate_room_pass_card,
    generate_slotlist_card,
    generate_tournament_banner,
    generate_tournament_bracket_card,
    generate_ultimate_player_card,
    generate_wolf_icon,
)

BRAND = "Root LU"
OUT_DIR = ROOT / "docs" / "demo"

ROWS = [
    {"name": f"Squad {i}", "tag": f"S{i}", "matches": 3, "kills": 20 - i, "pts": 50 - i * 3}
    for i in range(1, 13)
]

TEAMS_12 = [
    {"name": f"Squad {i}", "tag": f"S{i}", "batch": "60", "section": "A"}
    for i in range(1, 13)
]

HOF_ENTRIES = [
    {
        "season": "2026 Season",
        "team_name": f"Legends {i}",
        "team_tag": f"L{i}",
        "achievement": "CHAMPION",
        "points": 88,
        "kills": 41,
    }
    for i in range(1, 7)
]

BRACKET_ROUNDS = [
    [
        {
            "team_a_name": f"Team {i}",
            "team_b_name": f"Team {17 - i}",
            "team_a_tag": f"T{i}",
            "team_b_tag": f"T{17 - i}",
            "winner_name": None,
            "status": "pending",
        }
        for i in range(1, 9)
    ],
    [
        {
            "team_a_name": "Team 1",
            "team_b_name": "Team 8",
            "winner_name": "Team 1",
            "status": "completed",
        }
        for _ in range(4)
    ],
    [
        {"team_a_name": "Team 1", "team_b_name": None, "winner_name": None, "status": "pending"}
        for _ in range(2)
    ],
    [{"team_a_name": None, "team_b_name": None, "winner_name": None, "status": "pending"}],
]

KILLFEED_EVENTS = [
    {"player": f"P{i}Killa", "action": "ELIMINATED", "detail": f"{i} opponents down"}
    for i in range(1, 8)
]

ATTRS = {"PAC": 88, "SHO": 91, "PAS": 76, "DRI": 84, "DEF": 60, "PHY": 79}

TEAM_A = {"name": "Root Wolves", "tag": "RW", "pts": 120, "kills": 45, "matches": 6}
TEAM_B = {"name": "Alpha", "tag": "AL", "pts": 98, "kills": 38, "matches": 6}

# filename -> (callable, args) ; order matches the README graphics table
CARDS = [
    ("01-tournament-banner", generate_tournament_banner,
     ("Root LU Cup", BRAND, 12, 5000, 100, 1, "OPEN")),
    ("02-match-banner", generate_match_banner,
     ("Root LU Cup", 1, "Bermuda", "Tonight 9PM", BRAND)),
    ("03-room-pass", generate_room_pass_card,
     ("Root Wolves", "Root LU Cup", 1, "Bermuda", 3, BRAND)),
    ("04-points-table", generate_points_table_graphic, ("Root LU Cup", ROWS, BRAND)),
    ("05-booyah", generate_booyah_card, ("Root Wolves", "Root LU Cup", 120, 45, BRAND)),
    ("06-mvp", generate_mvp_card, ("JoyPro", "Root Wolves", 12, 3450, 1, BRAND)),
    ("07-live-stream", generate_live_stream_card,
     ("Root LU Cup", 2, "Purgatory", "YouTube", BRAND)),
    ("08-player-passport", generate_player_passport_card,
     ("Joy Ahmed", "JoyPro", "100200300", "IGL", "60", "A", 120, 30, BRAND)),
    ("09-certificate", generate_certificate_card,
     ("Joy Ahmed", "MVP of the Tournament", "Root LU Cup", "Root Wolves",
      "RLU-ABC123", "2026-10-07 12:00:00", BRAND)),
    ("10-slotlist", generate_slotlist_card, ("Root LU Cup", TEAMS_12, 12, BRAND)),
    ("11-matchup-clash", generate_matchup_clash_card, (TEAM_A, TEAM_B, "Root LU Cup", 3, BRAND)),
    ("12-hall-of-fame", generate_hall_of_fame_card, (HOF_ENTRIES, BRAND)),
    ("13-bracket", generate_tournament_bracket_card, ("Root LU Cup", BRACKET_ROUNDS, BRAND)),
    ("14-killfeed", generate_killfeed_card, (KILLFEED_EVENTS, BRAND, "Match #1 - Bermuda")),
    ("15-lowerthird", generate_broadcast_lowerthird_card,
     ("Root Wolves take the lead!", "Match #1 - Bermuda - Live", BRAND)),
    ("16-ultimate-player", generate_ultimate_player_card,
     ("JoyPro", "RW", "IGL", 81, ATTRS, 120, 30, 8, BRAND)),
    ("17-bounty-poster", generate_bounty_poster,
     ("ShadowStrike", 500, "Joy", "Team kill in scrims", BRAND)),
    ("18-wolf-icon", generate_wolf_icon, (256,)),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, func, args in CARDS:
        buf = func(*args)
        if not isinstance(buf, io.BytesIO):  # pragma: no cover - defensive
            raise TypeError(f"{func.__name__} did not return a BytesIO buffer")
        dest = OUT_DIR / f"{name}.png"
        dest.write_bytes(buf.getvalue())
        size = dest.stat().st_size
        total += size
        print(f"  {dest.relative_to(ROOT)}  {size / 1024:7.1f} KB")
    print(f"\n{len(CARDS)} demo cards written to {OUT_DIR.relative_to(ROOT)} "
          f"({total / 1024 / 1024:.2f} MB total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
