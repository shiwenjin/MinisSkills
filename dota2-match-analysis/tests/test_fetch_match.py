import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_match.py"


SAMPLE_MATCH = {
    "match_id": 1234567890,
    "duration": 2451,
    "radiant_win": True,
    "radiant_score": 38,
    "dire_score": 24,
    "start_time": 1700000000,
    "region": 3,
    "game_mode": 22,
    "players": [
        {
            "player_slot": 0,
            "personaname": "Radiant One",
            "hero_id": 1,
            "localized_name": "Anti-Mage",
            "kills": 12,
            "deaths": 3,
            "assists": 14,
            "hero_damage": 22000,
            "tower_damage": 5100,
            "hero_healing": 0,
            "net_worth": 21500,
            "total_xp": 24123,
            "last_hits": 211,
            "denies": 9,
            "level": 24,
            "stuns": 1.5,
        },
        {
            "player_slot": 128,
            "personaname": "Dire One",
            "hero_id": 2,
            "localized_name": "Axe",
            "kills": 5,
            "deaths": 8,
            "assists": 11,
            "hero_damage": 14000,
            "tower_damage": 1200,
            "hero_healing": 500,
            "net_worth": 15400,
            "total_xp": 17234,
            "last_hits": 130,
            "denies": 4,
            "level": 20,
            "stuns": 2.0,
        },
    ],
    "objectives": [
        {"type": "CHAT_MESSAGE_FIRSTBLOOD", "time": 115},
        {"type": "CHAT_MESSAGE_ROSHAN_KILL", "time": 1630},
    ],
    "teamfights": [{"start": 1200}, {"start": 1800}],
    "chat": [
        {"type": "chat", "time": 90, "player_slot": 0, "key": "go"},
        {"type": "chatwheel", "time": 95, "player_slot": 128, "key": "laugh"},
    ],
}


class FetchMatchScriptTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_normalizes_match_from_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "source.json"
            normalized_path = temp_path / "normalized.json"
            source_path.write_text(json.dumps(SAMPLE_MATCH), encoding="utf-8")

            result = self.run_script(
                "1234567890",
                "--from-file",
                str(source_path),
                "--normalized-out",
                str(normalized_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
            self.assertEqual(normalized["match_id"], 1234567890)
            self.assertEqual(normalized["winner"], "radiant")
            self.assertEqual(normalized["duration_seconds"], 2451)
            self.assertEqual(normalized["players"][0]["team"], "radiant")
            self.assertEqual(normalized["players"][1]["team"], "dire")
            self.assertEqual(normalized["players"][0]["hero"]["english_name"], "Anti-Mage")
            self.assertEqual(normalized["players"][0]["hero"]["chinese_name"], "敌法师")
            self.assertEqual(normalized["players"][0]["hero"]["aliases"], ["AM", "敌法"])
            self.assertEqual(normalized["players"][0]["kda_ratio"], 8.67)
            self.assertEqual(normalized["signals"]["teamfight_count"], 2)
            self.assertEqual(normalized["signals"]["chat_message_count"], 1)

    def test_uses_cached_raw_match_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_dir = temp_path / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "match_1234567890.json"
            cache_file.write_text(json.dumps(SAMPLE_MATCH), encoding="utf-8")

            result = self.run_script("1234567890", "--cache-dir", str(cache_dir))

            self.assertEqual(result.returncode, 0, result.stderr)

            normalized = json.loads(result.stdout)
            self.assertEqual(normalized["source"], "cache")
            self.assertEqual(normalized["score"]["radiant"], 38)

    def test_exits_non_zero_when_required_fields_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "broken.json"
            source_path.write_text(json.dumps({"match_id": 1, "players": []}), encoding="utf-8")

            result = self.run_script("1", "--from-file", str(source_path))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing required fields", result.stderr)


if __name__ == "__main__":
    unittest.main()
