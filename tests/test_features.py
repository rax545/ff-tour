import asyncio
import io
import os
import sys
import aiosqlite

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SERVER_NAME, BRAND
from database.db import connect, init_db
from services.scoring import calculate
from services.leaderboard import leaderboard
from utils.banner import (
    generate_tournament_banner,
    generate_match_banner,
    generate_wolf_icon,
    clean_text_for_image
)
from utils.embeds import (
    base,
    ok,
    err,
    og_match_dm_embed,
    og_room_dm_embed
)


async def run_tests():
    print(f"Testing with SERVER_NAME = {SERVER_NAME}")

    # 1. Test clean_text_for_image
    cleaned = clean_text_for_image(SERVER_NAME)
    print(f"[1] clean_text_for_image('{SERVER_NAME}') -> '{cleaned}'")
    assert "WHITE WOLF GLOBAL" in cleaned.upper(), f"Expected WHITE WOLF GLOBAL, got {cleaned}"

    # 2. Test banner generation
    print("[2] Generating tournament banner...")
    tourn_buf = generate_tournament_banner(
        tournament_name="FREE FIRE PRO INVITATIONAL 2026",
        server_name=SERVER_NAME,
        max_teams=48,
        prize_pool=10000,
        entry_fee=200,
        tournament_id=99,
        status="OPEN"
    )
    assert isinstance(tourn_buf, io.BytesIO)
    tourn_bytes = tourn_buf.getvalue()
    assert len(tourn_bytes) > 10000, f"Banner image too small: {len(tourn_bytes)}"
    print(f"    Tournament banner generated successfully: {len(tourn_bytes)} bytes")

    # 3. Test match banner generation
    print("[3] Generating match banner...")
    match_buf = generate_match_banner(
        tournament_name="FREE FIRE PRO INVITATIONAL 2026",
        match_no=1,
        map_name="Bermuda",
        scheduled_at="Tonight 9:00 PM",
        server_name=SERVER_NAME
    )
    assert isinstance(match_buf, io.BytesIO)
    match_bytes = match_buf.getvalue()
    assert len(match_bytes) > 10000, f"Match banner image too small: {len(match_bytes)}"
    print(f"    Match banner generated successfully: {len(match_bytes)} bytes")

    # 4. Test 4+1 lineup in OG Match DM embed
    print("[4] Testing OG Match DM embed with 4 Starters + 1 Substitute...")
    test_lineup = [
        {"user_id": 11111, "ign": "WW_Leader", "uid": "10000001", "role": "IGL", "is_sub": 0},
        {"user_id": 22222, "ign": "WW_Rusher", "uid": "10000002", "role": "Rusher", "is_sub": 0},
        {"user_id": 33333, "ign": "WW_Sniper", "uid": "10000003", "role": "Sniper", "is_sub": 0},
        {"user_id": 44444, "ign": "WW_Assault", "uid": "10000004", "role": "Assaulter", "is_sub": 0},
        {"user_id": 55555, "ign": "WW_SubExtra", "uid": "10000005", "role": "Substitute", "is_sub": 1},
    ]
    dm_embed = og_match_dm_embed(
        team_name="White Wolf Esports",
        team_tag="WW",
        tournament_name="PRO LEAGUE S1",
        tournament_id=1,
        match_no=1,
        match_id=101,
        map_name="Bermuda",
        scheduled_at="Tonight 9:00 PM",
        lineup_details=test_lineup,
        server_name=SERVER_NAME
    )
    embed_dict = dm_embed.to_dict()
    assert SERVER_NAME in embed_dict["title"], "Server name missing in DM embed title"
    assert "White Wolf Esports" in embed_dict["description"], "Team name missing in DM embed description"
    assert "WW" in embed_dict["description"], "Team tag missing in DM embed description"

    # Verify lineup field exists and has all 5 players and roles
    lineup_field = next((f for f in embed_dict.get("fields", []) if "Lineup" in f["name"]), None)
    assert lineup_field is not None, "Missing Lineup & Roles field in DM embed"
    lineup_val = lineup_field["value"]
    assert "WW_Leader" in lineup_val and "10000001" in lineup_val and "IGL" in lineup_val
    assert "WW_Rusher" in lineup_val and "10000002" in lineup_val and "Rusher" in lineup_val
    assert "WW_Sniper" in lineup_val and "10000003" in lineup_val and "Sniper" in lineup_val
    assert "WW_Assault" in lineup_val and "10000004" in lineup_val and "Assaulter" in lineup_val
    assert "WW_SubExtra" in lineup_val and "10000005" in lineup_val and "Substitute" in lineup_val
    print("    Lineup & 4+1 roles in OG Match DM embed verified successfully!")

    # 5. Test Database creation & 4 Starters + 1 Sub insertion
    print("[5] Testing Database schema and 4 Starters + 1 Sub roster...")
    await init_db()
    db = await connect()

    # Insert test tournament
    cur = await db.execute(
        """
        INSERT INTO tournaments (name, description, max_teams, entry_fee, prize_pool, created_by)
        VALUES ('Full Lineup Championship', 'Testing 4+1 players', 12, 50, 500, 12345)
        """
    )
    t_id = cur.lastrowid

    # Insert test team
    cur = await db.execute(
        """
        INSERT INTO teams (tournament_id, name, tag, captain_id)
        VALUES (?, 'Alpha Predators', 'PRED', 11111)
        """,
        (t_id,)
    )
    team_id = cur.lastrowid

    # Insert 4 starters + 1 substitute
    for p in test_lineup:
        await db.execute(
            """
            INSERT INTO team_members (team_id, user_id, ign, uid, role, is_sub)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (team_id, p["user_id"], p["ign"], p["uid"], p["role"], p["is_sub"])
        )

    # Check member count
    cur = await db.execute("SELECT COUNT(*) AS c FROM team_members WHERE team_id=?", (team_id,))
    total_c = (await cur.fetchone())["c"]
    assert total_c == 5, f"Expected 5 players, got {total_c}"

    cur = await db.execute("SELECT COUNT(*) AS c FROM team_members WHERE team_id=? AND is_sub=0", (team_id,))
    starter_c = (await cur.fetchone())["c"]
    assert starter_c == 4, f"Expected 4 starters, got {starter_c}"

    cur = await db.execute("SELECT COUNT(*) AS c FROM team_members WHERE team_id=? AND is_sub=1", (team_id,))
    sub_c = (await cur.fetchone())["c"]
    assert sub_c == 1, f"Expected 1 sub, got {sub_c}"

    # Clean up test rows
    await db.execute("DELETE FROM tournaments WHERE id=?", (t_id,))
    await db.commit()
    await db.close()
    print("    Database 4 Starters + 1 Sub tests passed successfully!")

    print("\nALL LINEUP & ROLE TESTS PASSED! 🔥🐺")


if __name__ == "__main__":
    asyncio.run(run_tests())
