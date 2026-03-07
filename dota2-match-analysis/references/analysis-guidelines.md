# Dota2 Match Analysis Reference

## Table of Contents
- [Purpose](#purpose)
- [Normalized Script Output](#normalized-script-output)
- [Hero Name Reference](#hero-name-reference)
- [Player Evaluation Heuristics](#player-evaluation-heuristics)
- [Account Analysis Heuristics](#account-analysis-heuristics)
- [Match Flow Heuristics](#match-flow-heuristics)
- [Data Caveats](#data-caveats)
- [Output Style](#output-style)
- [Output Defaults](#output-defaults)

## Purpose

Use this file when the user wants a deeper report or when raw OpenDota data needs interpretation beyond the core workflow in `SKILL.md`.

## Normalized Script Output

Use `scripts/fetch_match.py` first. The script returns a normalized JSON object. 

**Logic:** This normalization layer ensures you don't get lost in the 1000+ lines of raw OpenDota JSON. Treat the normalized output as the "Executive Summary" and only dive into raw data for specific "crime scene" investigations (e.g., exact timestamps of buybacks).

## Hero Name Reference

Use `references/hero-name-aliases-with-id.csv` as the source of truth for mapping. It contains:

- `Hero ID`: The primary key for mapping from raw match data.
- `中文官方名称`: Official Chinese names.
- `英文官方名称`: Official English names (localized_name).
- `常用简称 / 别称`: Common community aliases.

**Mapping Logic:**
- Always prioritize mapping via `Hero ID` if available in the source payload.
- Use the Chinese official name as the primary display name in reports.
- Use aliases (e.g., "AM", "冰女") to add flavor or brevity in the "Snarky" commentary sections.

## Player Evaluation Heuristics

Avoid ranking players by a single stat. 

**Logic:** Dota2 is a resource allocation game. High KDA on a Pos 1 doesn't mean much if they failed to convert farm into objectives, while a Pos 5 with 15 deaths might be the unsung hero who secured every crucial stack and vision.

Use these signals together:

- **Carry/core impact:** net worth, hero damage, tower damage, death count, closing contribution.
- **Support impact:** assists, stuns, hero healing, warding-related context if available, low-death utility.
- **Tempo impact:** early kill participation, objective pressure, map-opening fights.
- **Cost of mistakes:** deaths during key timings, long downtime on the highest-farm hero.

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

**Logic:** Avoid "Recency Bias". A 3-game losing streak doesn't make a pro player bad, just as a 5-game win streak on Sniper doesn't mean they've mastered the hero. Always contextualize stats with sample sizes.

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

**Logic:** Every Dota game has a "Turning Point". Your job is to find the exact moment (gold swing or key death) where the game's momentum shifted permanently.

## Data Caveats

- `chat` may be absent or heavily filtered.
- `teamfights` may be missing even on valid matches.
- `objectives` is useful for timeline anchors but is not a complete narration of the game.
- **Hero Names:** If ID is missing, don't guess. Use "Unknown Hero (ID: X)".

## Output Style

Default to **snarky commentary style**, like casters roasting each other during a stream.

- Roast key mistakes, questionable plays, and "crime scenes".
- Even the winning side can get some "too easy, boring" feedback.
- Snark should be grounded in real data, don't hate just for the sake of hate.

**Before & After Example:**
- **Standard (Boring):** "Juggernaut had 15,000 net worth but died 8 times. He didn't play very well."
- **Snarky (Recommended):** "1.5W 经济的剑圣 30 分钟死 8 次，对面提款都快提冒烟了。全场不是在逛街就是在白给，主宰硬生生打成了‘对面第六人’。这波属于典型的顶级战犯。"

## Output Defaults

Default to concise structured output. Prefer:
- opening verdict first
- 4 to 6 short sections total
- 2 to 4 highlighted players instead of full-roster commentary
- only the most explanatory fight, objective, or chat details

Expand only when the user asks for:
- full replay-style timeline
- per-player deep dive
- only MVP / best player judgment
- only lineup comparison
