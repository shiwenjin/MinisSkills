import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_player.py"


SAMPLE_PROFILE = {
    "profile": {
        "account_id": 87278757,
        "personaname": "Sample Player",
    },
    "rank_tier": 74,
    "leaderboard_rank": 123,
}

SAMPLE_RECENT_MATCHES = [
    {
        "match_id": 1,
        "player_slot": 0,
        "radiant_win": True,
        "kills": 10,
        "deaths": 2,
        "assists": 12,
        "hero_id": 1,
    },
    {
        "match_id": 2,
        "player_slot": 128,
        "radiant_win": True,
        "kills": 2,
        "deaths": 8,
        "assists": 9,
        "hero_id": 2,
    },
]

SAMPLE_HEROES = [
    {
        "hero_id": 1,
        "games": 20,
        "win": 14,
        "localized_name": "Anti-Mage",
    },
    {
        "hero_id": 2,
        "games": 10,
        "win": 4,
        "localized_name": "Axe",
    },
]

SAMPLE_TOTALS = [
    {"field": "kills", "sum": 300.0, "n": 20},
    {"field": "deaths", "sum": 120.0, "n": 20},
    {"field": "assists", "sum": 250.0, "n": 20},
]

SAMPLE_COUNTS = {
    "game_mode": {"22": 10},
    "leaver_status": {"0": 20},
}


class FetchPlayerScriptTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_normalizes_player_from_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profile_path = temp_path / "profile.json"
            recent_path = temp_path / "recent.json"
            heroes_path = temp_path / "heroes.json"
            totals_path = temp_path / "totals.json"
            counts_path = temp_path / "counts.json"
            normalized_path = temp_path / "normalized.json"

            self.write_json(profile_path, SAMPLE_PROFILE)
            self.write_json(recent_path, SAMPLE_RECENT_MATCHES)
            self.write_json(heroes_path, SAMPLE_HEROES)
            self.write_json(totals_path, SAMPLE_TOTALS)
            self.write_json(counts_path, SAMPLE_COUNTS)

            result = self.run_script(
                "87278757",
                "--profile-file",
                str(profile_path),
                "--recent-matches-file",
                str(recent_path),
                "--heroes-file",
                str(heroes_path),
                "--totals-file",
                str(totals_path),
                "--counts-file",
                str(counts_path),
                "--normalized-out",
                str(normalized_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            self.assertEqual(normalized["account_id"], 87278757)
            self.assertEqual(normalized["profile"]["personaname"], "Sample Player")
            self.assertEqual(normalized["recent"]["match_count"], 2)
            self.assertEqual(normalized["recent"]["win_count"], 1)
            self.assertEqual(normalized["recent"]["win_rate"], 50.0)
            self.assertEqual(normalized["top_heroes"][0]["hero"]["chinese_name"], "敌法师")
            self.assertEqual(normalized["top_heroes"][0]["win_rate"], 70.0)
            self.assertEqual(normalized["totals"]["kills"]["average"], 15.0)

    def test_uses_cached_payloads_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_dir = temp_path / "cache"
            cache_dir.mkdir()
            self.write_json(cache_dir / "player_87278757_profile.json", SAMPLE_PROFILE)
            self.write_json(cache_dir / "player_87278757_recent_matches.json", SAMPLE_RECENT_MATCHES)
            self.write_json(cache_dir / "player_87278757_heroes.json", SAMPLE_HEROES)
            self.write_json(cache_dir / "player_87278757_totals.json", SAMPLE_TOTALS)
            self.write_json(cache_dir / "player_87278757_counts.json", SAMPLE_COUNTS)

            result = self.run_script("87278757", "--cache-dir", str(cache_dir))

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(result.stdout)
            self.assertEqual(normalized["source"], "cache")
            self.assertEqual(normalized["profile"]["rank_tier"], 74)

    def test_exits_non_zero_when_profile_is_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            profile_path = temp_path / "profile.json"
            recent_path = temp_path / "recent.json"
            heroes_path = temp_path / "heroes.json"
            totals_path = temp_path / "totals.json"
            counts_path = temp_path / "counts.json"

            self.write_json(profile_path, {"profile": {}})
            self.write_json(recent_path, [])
            self.write_json(heroes_path, [])
            self.write_json(totals_path, [])
            self.write_json(counts_path, {})

            result = self.run_script(
                "87278757",
                "--profile-file",
                str(profile_path),
                "--recent-matches-file",
                str(recent_path),
                "--heroes-file",
                str(heroes_path),
                "--totals-file",
                str(totals_path),
                "--counts-file",
                str(counts_path),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing required fields", result.stderr)


if __name__ == "__main__":
    unittest.main()
