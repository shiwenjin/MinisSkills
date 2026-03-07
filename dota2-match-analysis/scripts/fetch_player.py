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


DEFAULT_HERO_ALIASES = Path(__file__).resolve().parents[1] / "references" / "hero-name-aliases.csv"
PLAYER_ENDPOINTS = {
    "profile": "",
    "recent_matches": "/recentMatches",
    "heroes": "/heroes",
    "totals": "/totals",
    "counts": "/counts",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a Dota2 player from cache or OpenDota and output a normalized summary."
    )
    parser.add_argument("account_id", help="Dota2 account ID")
    parser.add_argument(
        "--cache-dir",
        default="cache",
        help="Directory for raw OpenDota player payloads. Default: %(default)s",
    )
    parser.add_argument("--profile-file", help="Read raw profile JSON from a local file.")
    parser.add_argument("--recent-matches-file", help="Read raw recent matches JSON from a local file.")
    parser.add_argument("--heroes-file", help="Read raw heroes JSON from a local file.")
    parser.add_argument("--totals-file", help="Read raw totals JSON from a local file.")
    parser.add_argument("--counts-file", help="Read raw counts JSON from a local file.")
    parser.add_argument("--normalized-out", help="Write normalized JSON to this path in addition to stdout.")
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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
            aliases[english_name.lower()] = {
                "english_name": english_name,
                "chinese_name": (row.get("中文官方名称") or "").strip() or None,
                "aliases": alias_list,
            }
    return aliases


def resolve_hero(english_name: str | None, hero_id: Any, hero_aliases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matched = hero_aliases.get(english_name.lower()) if english_name else None
    return {
        "hero_id": hero_id,
        "english_name": matched["english_name"] if matched else english_name,
        "chinese_name": matched["chinese_name"] if matched else None,
        "aliases": matched["aliases"] if matched else [],
    }


def load_payload_from_arg_or_cache(
    direct_path: str | None,
    cache_path: Path,
) -> tuple[Any, str]:
    if direct_path:
        return load_json(Path(direct_path)), "file"
    if cache_path.exists():
        return load_json(cache_path), "cache"
    return None, "network"


def fetch_endpoint(account_id: str, suffix: str, timeout: int) -> Any:
    url = f"https://api.opendota.com/api/players/{account_id}{suffix}"
    request = urllib.request.Request(url, headers={"User-Agent": "codex-dota2-match-analysis"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"OpenDota returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def load_player_payloads(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    direct_files = {
        "profile": args.profile_file,
        "recent_matches": args.recent_matches_file,
        "heroes": args.heroes_file,
        "totals": args.totals_file,
        "counts": args.counts_file,
    }

    payloads: dict[str, Any] = {}
    sources: set[str] = set()
    cache_dir = Path(args.cache_dir)

    for name, suffix in PLAYER_ENDPOINTS.items():
        cache_path = cache_dir / f"player_{args.account_id}_{name}.json"
        payload, source = load_payload_from_arg_or_cache(direct_files[name], cache_path)
        if payload is None:
            payload = fetch_endpoint(args.account_id, suffix, args.timeout)
            save_json(cache_path, payload)
            source = "network"
        payloads[name] = payload
        sources.add(source)

    if sources == {"cache"}:
        source = "cache"
    elif sources == {"file"}:
        source = "file"
    elif "network" in sources:
        source = "network"
    else:
        source = "mixed"
    return payloads, source


def validate_profile(profile_payload: dict[str, Any], account_id: str) -> None:
    profile = profile_payload.get("profile") or {}
    missing = []
    if "account_id" not in profile:
        missing.append("profile.account_id")
    if str(profile.get("account_id")) != str(account_id):
        missing.append("profile.account_id")
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(set(missing)))}")


def did_player_win(match: dict[str, Any]) -> bool:
    player_slot = match.get("player_slot", 128)
    on_radiant = player_slot < 128
    radiant_win = bool(match.get("radiant_win"))
    return radiant_win if on_radiant else not radiant_win


def normalize_recent_matches(matches: list[dict[str, Any]]) -> dict[str, Any]:
    match_count = len(matches)
    win_count = sum(1 for match in matches if did_player_win(match))
    return {
        "match_count": match_count,
        "win_count": win_count,
        "win_rate": round((win_count / match_count) * 100, 2) if match_count else 0.0,
        "sample_size": match_count,
    }


def normalize_totals(totals: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {}
    for item in totals:
        field = item.get("field")
        if not field:
            continue
        total_sum = float(item.get("sum", 0.0) or 0.0)
        sample_size = int(item.get("n", 0) or 0)
        normalized[field] = {
            "sum": total_sum,
            "sample_size": sample_size,
            "average": round(total_sum / sample_size, 2) if sample_size else 0.0,
        }
    return normalized


def normalize_top_heroes(
    heroes: list[dict[str, Any]], hero_aliases: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    ranked = sorted(heroes, key=lambda item: int(item.get("games", 0) or 0), reverse=True)
    normalized = []
    for hero in ranked[:5]:
        games = int(hero.get("games", 0) or 0)
        wins = int(hero.get("win", 0) or 0)
        normalized.append(
            {
                "hero": resolve_hero(hero.get("localized_name"), hero.get("hero_id"), hero_aliases),
                "games": games,
                "wins": wins,
                "win_rate": round((wins / games) * 100, 2) if games else 0.0,
            }
        )
    return normalized


def normalize_profile(profile_payload: dict[str, Any]) -> dict[str, Any]:
    profile = profile_payload.get("profile") or {}
    return {
        "account_id": profile.get("account_id"),
        "personaname": profile.get("personaname"),
        "name": profile.get("name"),
        "rank_tier": profile_payload.get("rank_tier"),
        "leaderboard_rank": profile_payload.get("leaderboard_rank"),
    }


def normalize_player(
    account_id: str,
    payloads: dict[str, Any],
    source: str,
    hero_aliases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "account_id": int(account_id),
        "source": source,
        "profile": normalize_profile(payloads["profile"]),
        "recent": normalize_recent_matches(payloads["recent_matches"]),
        "top_heroes": normalize_top_heroes(payloads["heroes"], hero_aliases),
        "totals": normalize_totals(payloads["totals"]),
        "counts": payloads["counts"],
    }


def main() -> int:
    args = parse_args()
    try:
        payloads, source = load_player_payloads(args)
        validate_profile(payloads["profile"], args.account_id)
        hero_aliases = load_hero_aliases(Path(args.hero_aliases_file))
        normalized = normalize_player(args.account_id, payloads, source, hero_aliases)
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
