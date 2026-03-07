#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "match_id",
    "duration",
    "radiant_win",
    "radiant_score",
    "dire_score",
    "players",
)
DEFAULT_HERO_ALIASES = Path(__file__).resolve().parents[1] / "references" / "hero-name-aliases.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a Dota2 match from cache or OpenDota and output a normalized summary."
    )
    parser.add_argument("match_id", help="Dota2 match ID")
    parser.add_argument(
        "--cache-dir",
        default=str(Path(__file__).resolve().parents[1] / "cache"),
        help="Directory for raw OpenDota match payloads. Default: %(default)s",
    )
    parser.add_argument(
        "--from-file",
        help="Read raw match JSON from a local file instead of cache or network.",
    )
    parser.add_argument(
        "--normalized-out",
        help="Write normalized JSON to this path in addition to stdout.",
    )
    parser.add_argument(
        "--raw-out",
        help="Write raw match JSON to this path after loading or fetching.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Network timeout in seconds when fetching from OpenDota. Default: %(default)s",
    )
    parser.add_argument(
        "--hero-aliases-file",
        default=str(DEFAULT_HERO_ALIASES),
        help="CSV file with Chinese and English hero names plus aliases. Default: %(default)s",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_hero_aliases(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    aliases: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            english_name = (row.get("英文官方名称") or "").strip()
            if not english_name:
                continue
            alias_text = (row.get("常用简称 / 别称") or "").strip()
            alias_list = []
            if alias_text and alias_text != "-":
                alias_list = [item.strip() for item in alias_text.split("、") if item.strip()]

            entry = {
                "english_name": english_name,
                "chinese_name": (row.get("中文官方名称") or "").strip() or None,
                "aliases": alias_list,
            }

            # 添加小写空格版本作为 key（如 "queen of pain"）
            aliases[english_name.lower()] = entry
            # 添加下划线版本作为 key（如 "queenofpain"）
            underscores_removed = english_name.replace(" ", "").lower()
            if underscores_removed != english_name.lower():
                aliases[underscores_removed] = entry
            # 添加带下划线的版本（如 "faceless_void"），用于匹配 ability_uses
            underscore_version = english_name.replace(" ", "_").lower()
            if underscore_version != english_name.lower() and underscore_version != underscores_removed:
                aliases[underscore_version] = entry

            # 添加别名作为 key（如 "zuus", "skeleton_king"）
            for alias in alias_list:
                alias_key = alias.lower().replace(" ", "")
                if alias_key and alias_key not in aliases:
                    aliases[alias_key] = entry

    return aliases


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_match(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def team_from_slot(player_slot: int | None) -> str:
    if player_slot is None:
        return "unknown"
    return "radiant" if player_slot < 128 else "dire"


def player_name(player: dict[str, Any]) -> str:
    return (
        player.get("personaname")
        or player.get("name")
        or player.get("steam_name")
        or "Unknown"
    )


def resolve_hero_name(player: dict[str, Any]) -> str | None:
    # 优先从 ability_uses 提取英雄名（最可靠）
    ability_uses = player.get("ability_uses") or {}
    if ability_uses:
        # 排除中立物品等非英雄技能
        keys = [
            k for k in ability_uses.keys()
            if not k.startswith(("ability", "twin_gate", "observer", "sentry", "courier"))
        ]
        if not keys:
            return None

        if len(keys) == 1:
            # 只有一个技能，格式是 "英雄名_技能名"
            parts = keys[0].split("_")
            if len(parts) >= 2:
                return f"{parts[0]}_{parts[1]}"
            return parts[0] if parts else None
        else:
            # 多个技能，找公共前缀
            prefix = keys[0]
            for k in keys[1:]:
                while not k.startswith(prefix):
                    prefix = prefix[:-1]
                    if not prefix:
                        break
            # 去掉末尾下划线
            return prefix.rstrip("_") if prefix else None

    # 其次尝试从 OpenDota 返回的字段获取
    return (
        player.get("localized_name")
        or player.get("hero_name")
        or player.get("english_name")
        or None
    )


def normalize_hero(player: dict[str, Any], hero_aliases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    hero_id = player.get("hero_id")
    english_name = resolve_hero_name(player)
    matched = None

    if english_name:
        # 直接匹配
        matched = hero_aliases.get(english_name.lower())

        # 如果没匹配到，尝试用更短的前缀（如 "faceless_void_time" → "faceless_void"）
        if not matched and "_" in english_name:
            # 尝试去掉最后一部分
            parts = english_name.rsplit("_", 1)
            if len(parts) >= 2:
                matched = hero_aliases.get(parts[0].lower())

    return {
        "hero_id": hero_id,
        "english_name": matched["english_name"] if matched else english_name,
        "chinese_name": matched["chinese_name"] if matched else None,
        "aliases": matched["aliases"] if matched else [],
    }


def kda_ratio(player: dict[str, Any]) -> float:
    kills = player.get("kills", 0) or 0
    deaths = player.get("deaths", 0) or 0
    assists = player.get("assists", 0) or 0
    return round((kills + assists) / max(1, deaths), 2)


def normalize_players(
    players: list[dict[str, Any]], hero_aliases: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    normalized = []
    for player in players:
        normalized.append(
            {
                "team": team_from_slot(player.get("player_slot")),
                "slot": player.get("player_slot"),
                "name": player_name(player),
                "hero_id": player.get("hero_id"),
                "hero": normalize_hero(player, hero_aliases),
                "kills": player.get("kills", 0),
                "deaths": player.get("deaths", 0),
                "assists": player.get("assists", 0),
                "kda_ratio": kda_ratio(player),
                "hero_damage": player.get("hero_damage", 0),
                "tower_damage": player.get("tower_damage", 0),
                "hero_healing": player.get("hero_healing", 0),
                "net_worth": player.get("net_worth", player.get("total_gold", 0)),
                "total_xp": player.get("total_xp", 0),
                "last_hits": player.get("last_hits", 0),
                "denies": player.get("denies", 0),
                "level": player.get("level", 0),
                "stuns": player.get("stuns", 0),
            }
        )
    return normalized


def normalize_match(
    payload: dict[str, Any], source: str, hero_aliases: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    players = normalize_players(payload.get("players", []), hero_aliases)
    objectives = payload.get("objectives") or []
    teamfights = payload.get("teamfights") or []
    chat_messages = [
        item for item in (payload.get("chat") or []) if item.get("type") == "chat"
    ]

    return {
        "match_id": payload["match_id"],
        "source": source,
        "winner": "radiant" if payload["radiant_win"] else "dire",
        "duration_seconds": payload["duration"],
        "duration_minutes": round(payload["duration"] / 60, 2),
        "start_time": payload.get("start_time"),
        "region": payload.get("region"),
        "game_mode": payload.get("game_mode"),
        "score": {
            "radiant": payload["radiant_score"],
            "dire": payload["dire_score"],
        },
        "players": players,
        "signals": {
            "objective_count": len(objectives),
            "teamfight_count": len(teamfights),
            "chat_message_count": len(chat_messages),
            "has_objectives": bool(objectives),
            "has_teamfights": bool(teamfights),
            "has_chat": bool(chat_messages),
        },
    }


def fetch_match(match_id: str, timeout: int) -> dict[str, Any]:
    url = f"https://api.opendota.com/api/matches/{match_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "codex-dota2-match-analysis"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"OpenDota returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def load_raw_match(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    if args.from_file:
        return load_json(Path(args.from_file)), "file"

    cache_path = Path(args.cache_dir) / f"match_{args.match_id}.json"
    if cache_path.exists():
        return load_json(cache_path), "cache"

    payload = fetch_match(args.match_id, args.timeout)
    save_json(cache_path, payload)
    return payload, "network"


def main() -> int:
    args = parse_args()

    try:
        raw_match, source = load_raw_match(args)
        validate_match(raw_match)
        hero_aliases = load_hero_aliases(Path(args.hero_aliases_file))
        normalized = normalize_match(raw_match, source, hero_aliases)
        if args.raw_out:
            save_json(Path(args.raw_out), raw_match)
        if args.normalized_out:
            save_json(Path(args.normalized_out), normalized)
        sys.stdout.write(json.dumps(normalized, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return 0
    except FileNotFoundError as exc:
        sys.stderr.write(f"Input file not found: {exc}\n")
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"OpenDota request failed with HTTP {exc.code}\n")
    except urllib.error.URLError as exc:
        sys.stderr.write(f"OpenDota request failed: {exc.reason}\n")
    except Exception as exc:  # pragma: no cover - final guardrail
        sys.stderr.write(f"Unexpected error: {exc}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
