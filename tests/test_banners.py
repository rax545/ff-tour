"""God-tier graphics test suite — every banner/card generator in utils/banner.py."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from utils.banner import (
    generate_tournament_banner,
    generate_match_banner,
    generate_room_pass_card,
    generate_points_table_graphic,
    generate_booyah_card,
    generate_mvp_card,
    generate_live_stream_card,
    generate_player_passport_card,
    generate_certificate_card,
    generate_slotlist_card,
    generate_matchup_clash_card,
    generate_hall_of_fame_card,
    generate_tournament_bracket_card,
    generate_killfeed_card,
    generate_broadcast_lowerthird_card,
    generate_ultimate_player_card,
    generate_bounty_poster,
    generate_wolf_icon,
    clean_text_for_image,
    DEV_TAG,
)


def _assert_png(testcase, buf, size=None, min_bytes=5000):
    testcase.assertIsInstance(buf, io.BytesIO)
    data = buf.getvalue()
    testcase.assertGreater(len(data), min_bytes)
    img = Image.open(io.BytesIO(data))
    img.verify()
    img = Image.open(io.BytesIO(data))
    testcase.assertEqual(img.format, "PNG")
    if size is not None:
        testcase.assertEqual(img.size, size)
    return img


ROWS = [
    {"name": f"Squad {i}", "tag": f"S{i}", "matches": 3, "kills": 20 - i, "pts": 50 - i * 3}
    for i in range(1, 13)
]

TEAMS_12 = [
    {"name": f"Squad {i}", "tag": f"S{i}", "batch": "60", "section": "A"}
    for i in range(1, 13)
]

HOF_ENTRIES = [
    {"season": "2026 Season", "team_name": f"Legends {i}", "team_tag": f"L{i}",
     "achievement": "CHAMPION", "points": 88, "kills": 41}
    for i in range(1, 7)
]

BRACKET_ROUNDS = [
    [
        {"team_a_name": f"Team {i}", "team_b_name": f"Team {17 - i}",
         "team_a_tag": f"T{i}", "team_b_tag": f"T{17 - i}",
         "winner_name": None, "status": "pending"}
        for i in range(1, 9)
    ],
    [
        {"team_a_name": "Team 1", "team_b_name": "Team 8",
         "winner_name": "Team 1", "status": "completed"}
        for _ in range(4)
    ],
    [
        {"team_a_name": "Team 1", "team_b_name": None,
         "winner_name": None, "status": "pending"}
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


class BannerTests(unittest.TestCase):
    def test_dev_tag_branding(self):
        self.assertIn("JOY", DEV_TAG.upper())
        self.assertIn("DEVELOPED BY", DEV_TAG.upper())

    def test_clean_text(self):
        self.assertIn("ROOT LU", clean_text_for_image("Root LU").upper())
        # Exotic characters are stripped instead of rendering as boxes
        self.assertNotIn("🔥", clean_text_for_image("🔥 Root LU 🔥"))

    def test_tournament_banner(self):
        _assert_png(self, generate_tournament_banner(
            "Root LU Cup", "Root LU", 12, 5000, 100, 1, "OPEN"), (1200, 520))

    def test_match_banner(self):
        _assert_png(self, generate_match_banner(
            "Root LU Cup", 1, "Bermuda", "Tonight 9PM", "Root LU"), (1200, 460))

    def test_room_pass_card(self):
        _assert_png(self, generate_room_pass_card(
            "Root Wolves", "Root LU Cup", 1, "Bermuda", 3, "Root LU"), (1100, 500))

    def test_points_table_graphic_full(self):
        _assert_png(self, generate_points_table_graphic("Root LU Cup", ROWS, "Root LU"),
                    (1200, 880))

    def test_points_table_graphic_partial_and_empty(self):
        # Fewer than 12 rows renders open slots; empty list still renders
        _assert_png(self, generate_points_table_graphic("Root LU Cup", ROWS[:5], "Root LU"),
                    (1200, 880))
        _assert_png(self, generate_points_table_graphic("Root LU Cup", [], "Root LU"),
                    (1200, 880))

    def test_booyah_card(self):
        _assert_png(self, generate_booyah_card(
            "Root Wolves", "Root LU Cup", 120, 45, "Root LU"), (1200, 630))

    def test_mvp_card(self):
        _assert_png(self, generate_mvp_card(
            "JoyPro", "Root Wolves", 12, 3450, 1, "Root LU"), (1200, 630))

    def test_live_stream_card_hd(self):
        _assert_png(self, generate_live_stream_card(
            "Root LU Cup", 2, "Purgatory", "YouTube", "Root LU"), (1280, 720))
        _assert_png(self, generate_live_stream_card(
            "Root LU Cup", 2, "Kalahari", "Twitch", "Root LU"), (1280, 720))

    def test_player_passport_card(self):
        _assert_png(self, generate_player_passport_card(
            "Joy Ahmed", "JoyPro", "100200300", "IGL", "60", "A", 120, 30, "Root LU"),
            (960, 600))

    def test_certificate_card(self):
        _assert_png(self, generate_certificate_card(
            "Joy Ahmed", "MVP of the Tournament", "Root LU Cup", "Root Wolves",
            "RLU-ABC123", "2026-10-07 12:00:00", "Root LU"), (1600, 1000))

    def test_slotlist_card(self):
        _assert_png(self, generate_slotlist_card(
            "Root LU Cup", TEAMS_12, 12, "Root LU"), (1280, 840))
        # Partial lobby renders open slots
        _assert_png(self, generate_slotlist_card(
            "Root LU Cup", TEAMS_12[:7], 12, "Root LU"), (1280, 840))

    def test_matchup_clash_card(self):
        _assert_png(self, generate_matchup_clash_card(
            TEAM_A, TEAM_B, "Root LU Cup", 3, "Root LU"), (1200, 700))

    def test_hall_of_fame_card(self):
        _assert_png(self, generate_hall_of_fame_card(HOF_ENTRIES, "Root LU"), (1280, 800))
        # Empty hall of fame still renders
        _assert_png(self, generate_hall_of_fame_card([], "Root LU"), (1280, 800))

    def test_tournament_bracket_card(self):
        buf = generate_tournament_bracket_card("Root LU Cup", BRACKET_ROUNDS, "Root LU")
        img = _assert_png(self, buf)
        self.assertGreaterEqual(img.size[0], 1200)
        self.assertGreaterEqual(img.size[1], 560)

    def test_killfeed_card(self):
        _assert_png(self, generate_killfeed_card(
            KILLFEED_EVENTS, "Root LU", "Match #1 - Bermuda"), (1280, 640))
        # Empty feed still renders
        _assert_png(self, generate_killfeed_card([], "Root LU", "Match #1"), (1280, 640))

    def test_broadcast_lowerthird_card(self):
        _assert_png(self, generate_broadcast_lowerthird_card(
            "Root Wolves take the lead!", "Match #1 - Bermuda - Live", "Root LU"),
            (1920, 220))

    def test_ultimate_player_card(self):
        _assert_png(self, generate_ultimate_player_card(
            "JoyPro", "RW", "IGL", 81, ATTRS, 120, 30, 8, "Root LU"), (600, 900))

    def test_bounty_poster(self):
        _assert_png(self, generate_bounty_poster(
            "ShadowStrike", 500, "Joy", "Team kill in scrims", "Root LU"), (900, 1200))
        # No reason still renders
        _assert_png(self, generate_bounty_poster(
            "ShadowStrike", 500, "Joy", "", "Root LU"), (900, 1200))

    def test_wolf_icon(self):
        _assert_png(self, generate_wolf_icon(256), (256, 256), min_bytes=1000)

    def test_long_inputs_are_clamped(self):
        # Extremely long inputs must not crash the generators
        long_name = "X" * 500
        _assert_png(self, generate_ultimate_player_card(
            long_name, "RW", "IGL", 99, ATTRS, 1, 1, 1, "Root LU"), (600, 900))
        _assert_png(self, generate_bounty_poster(
            long_name, 10**9, long_name, long_name, "Root LU"), (900, 1200))
        _assert_png(self, generate_tournament_banner(
            long_name, long_name, 12, 0, 0, 1, "OPEN"), (1200, 520))


if __name__ == "__main__":
    unittest.main()
