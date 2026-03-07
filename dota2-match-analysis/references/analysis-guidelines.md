# Dota2 Match Analysis Reference

## Purpose

Use this file when the user wants a deeper report or when raw OpenDota data needs interpretation beyond the core workflow in `SKILL.md`.

## Normalized Script Output

Use `scripts/fetch_match.py` first. The script returns a normalized JSON object with:

- `match_id`
- `source`
- `winner`
- `duration_seconds`
- `duration_minutes`
- `start_time`
- `region`
- `game_mode`
- `score`
- `players`
- `signals`

Treat this output as the baseline summary. Go back to raw JSON only when you need details not present in the normalized payload.

## Hero Name Reference

Use `references/hero-name-aliases.csv` to map English hero names to:

- Chinese official names
- Common short names
- Common aliases

Current limitation:

- This CSV does not contain `hero_id`
- If the source payload only has `hero_id`, do not infer the hero name from row order or memory
- Only enrich hero naming when the payload already includes a stable English hero name such as `localized_name` or `hero_name`

## Player Evaluation Heuristics

Avoid ranking players by a single stat.

Use these signals together:

- Carry/core impact: net worth, hero damage, tower damage, death count, closing contribution
- Support impact: assists, stuns, hero healing, warding-related context if available, low-death utility
- Tempo impact: early kill participation, objective pressure, map-opening fights
- Cost of mistakes: deaths during key timings, long downtime on the highest-farm hero

Prefer evidence like:

- "highest hero damage on the winning side with low deaths"
- "modest KDA but top tower damage and objective conversion"
- "support with low farm but highest control time and strong teamfight presence"

## Account Analysis Heuristics

When the user provides `account_id`, prioritize these questions:

- What is the player's recent form?
- Which heroes are most played recently or overall?
- Is the player winning on comfort picks or only spamming games?
- Do totals suggest aggressive, stable, or sacrificial play?

Useful interpretations:

- Recent form: combine `recentMatches` sample size with recent win rate
- Comfort pool: use top heroes by games played, then compare win rate
- Baseline style: use `totals` averages for kills, deaths, assists
- Ranked signal: use `rank_tier` and `leaderboard_rank` only as context, not as the whole conclusion

Avoid overclaiming from tiny samples. If the recent sample is small, say so directly.

Suggested output sections for account reports:

- Player profile
- Recent results
- Most-played heroes
- Totals and playstyle signal
- Bottom-line judgment

## Match Flow Heuristics

When summarizing why a team won, look for:

- lane advantage converting into earlier tower pressure
- superior initiation or counter-initiation in midgame fights
- Roshan control leading to map choke or high-ground attempts
- lineup scaling overtaking an early-game draft
- repeated pickoffs before major objectives

Avoid fake certainty. If the data only weakly supports a conclusion, say "likely" or "the numbers suggest".

## Data Caveats

- `chat` may be absent or heavily filtered
- `teamfights` may be missing even on valid matches
- `objectives` is useful for timeline anchors but is not a complete narration of the game
- hero names may be unavailable if you only have `hero_id`; do not invent mappings

## Output Defaults

Default to concise structured output unless the user asks for:

- full replay-style timeline
- per-player deep dive
- only MVP / best player judgment
- only lineup comparison
