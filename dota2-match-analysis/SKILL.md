---
name: dota2-match-analysis
description: 分析 Dota2 比赛或玩家数据并输出结构化复盘。适用于用户要求分析比赛、查看比赛详情、评价玩家表现、判断谁打得最好、复盘关键团战、总结阵容优劣、提取聊天和关键事件，或要求根据 account_id 查看玩家资料、近期战绩、常用英雄、胜率走势等场景；当用户提供 match_id、account_id，明确指向某一场 Dota2 对局或某位玩家，或者提到“最近一场比赛”“上一把打得怎么样”这类最近对局查询时使用。
---

# Dota2 比赛分析技能

基于单场 Dota2 对局或单个玩家账户数据生成可靠、可读的分析。先获取数据，再提炼结果、阵容、玩家表现、关键事件、比赛走势或玩家画像；不要把输出写成原始字段转抄。

优先使用 `scripts/fetch_match.py` 处理比赛、使用 `scripts/fetch_player.py` 处理账户数据并生成基础归一化结果；当用户需要更深入的分析口径时，再读取 `references/analysis-guidelines.md`。英雄中英文名称和常用别称优先参考 `references/hero-name-aliases.csv`。

## 必要输入

- `match_id`：比赛 ID
- `account_id`：玩家账户 ID

根据用户意图选择输入：

- 分析单场比赛时需要 `match_id`
- 分析某位玩家近期表现、常用英雄、胜率时需要 `account_id`
- 分析“最近一场比赛”时，先需要 `account_id`，再从玩家近期比赛中取最近一场的 `match_id`

如果缺少 `match_id`，直接向用户索取，不要猜测。

如果缺少 `account_id`，按这个顺序处理：

1. 先检查用户记忆里是否已有可用的 `account_id`
2. 只有在记忆中找不到时，再请用户输入 `account_id`

不要猜测 `account_id`，也不要把其他数字误当成玩家账户 ID。

如果用户问的是“最近一场比赛情况怎么样”“我上一把打得怎么样”这类最近对局问题，按这个顺序执行：

1. 先获取 `account_id`；如果用户没给，就先查用户记忆，记忆里没有再向用户索取
2. 使用 `scripts/fetch_player.py {account_id}` 获取玩家数据
3. 从 `recentMatches` 原始数据或对应缓存中提取最近一场的 `match_id`
4. 再使用 `scripts/fetch_match.py {match_id}` 获取该场比赛详情
5. 最后按比赛分析报告输出，不要只给玩家概况

## 执行流程

### 1. 获取比赛数据

优先使用工作区内的脚本和缓存数据，不要每次都手写 `curl`。

```bash
/usr/bin/python3 scripts/fetch_match.py {match_id}
```

脚本行为：

- 优先读取 `cache/match_{match_id}.json`
- 缓存不存在时再请求 OpenDota
- 输出基础归一化 JSON，便于后续分析
- 可通过 `--from-file` 使用本地原始样本
- 会尝试根据 `references/hero-name-aliases.csv` 补充英雄中文名、英文名和别称
- 可通过 `--normalized-out` 和 `--raw-out` 保存结果

如果请求失败、返回 404、字段严重缺失，明确告诉用户无法完成分析，并说明原因。

### 1b. 获取玩家数据

分析玩家账户时，优先使用：

```bash
/usr/bin/python3 scripts/fetch_player.py {account_id}
```

脚本行为：

- 优先读取 `cache/player_{account_id}_*.json`
- 缓存不存在时再请求 OpenDota 玩家接口
- 聚合 `profile`、`recentMatches`、`heroes`、`totals`、`counts`
- 输出基础归一化 JSON，便于后续生成玩家报告
- 可通过 `--profile-file`、`--recent-matches-file`、`--heroes-file`、`--totals-file`、`--counts-file` 使用本地样本
- 会尝试根据 `references/hero-name-aliases.csv` 补充常用英雄的中文名、英文名和别称

如果 API 失败或账户数据缺失，明确说明无法完成玩家分析，并标记缺失模块。

### 1c. 从玩家近期比赛中提取最近一场 `match_id`

当用户要看“最近一场比赛”时，不要让用户再额外提供 `match_id`，优先从玩家近期比赛数据里拿。

处理顺序：

- 先运行 `scripts/fetch_player.py {account_id}`
- 然后从 OpenDota 的 `recentMatches` 原始返回里取最近一条记录的 `match_id`
- 如果脚本是通过缓存命中，优先检查 `cache/player_{account_id}_recent_matches.json`
- 只有在 `recentMatches` 为空或缺少 `match_id` 时，才明确告诉用户当前拿不到最近一场比赛 ID

默认把 `recentMatches` 的第一条视为最近一场；如果返回结果为空，不要编造比赛 ID。

### 2. 先做完整性检查

至少确认以下字段可用后再继续：

- `match_id`
- `duration`
- `radiant_win`
- `radiant_score`
- `dire_score`
- `players`

如果 `players`、`objectives`、`teamfights`、`chat` 中有部分缺失，可以继续分析，但要在结果中说明哪些模块基于不完整数据。

### 3. 提取比赛概况

整理并解释这些信息：

- 比赛结果：天辉或夜魇获胜
- 比赛时长：换算为分钟和秒
- 双方总击杀
- 开始时间
- 区域、模式、可用时的段位或房间信息

不要只列字段名，要转成自然语言摘要。

### 4. 分析双方阵容

基于 `players` 数据区分双方：

- `player_slot` 0-4 为天辉，128-132 为夜魇
- 识别每名玩家的英雄、常用位置倾向和基础出装概况

给出简短阵容判断，重点看：

- 控制能力
- 爆发与持续输出
- 线上强度
- 推塔与肉山能力
- 后期成长性

如果原始数据里带有英文英雄名，优先结合 `references/hero-name-aliases.csv` 输出中文名和别称；如果只有 `hero_id`，先保留 `hero_id`，不要编造映射。

### 5. 评估玩家表现

逐名玩家至少分析：

- `kills` / `deaths` / `assists`
- `hero_damage`
- `tower_damage`
- `hero_healing`
- `total_gold` 或 `net_worth`
- `total_xp`
- `last_hits` / `denies`
- `level`
- `stuns`

计算 KDA 时使用：

`(kills + assists) / max(1, deaths)`

不要只按 KDA 排名。综合考虑参战、经济转换、伤害贡献、推塔、控制、治疗和死亡成本，给出 1 到 3 名表现最佳玩家，并说明理由。

如果需要更稳定的评价口径，读取 `references/analysis-guidelines.md` 中的玩家评估与比赛走势启发式。

### 6. 提取关键事件和比赛转折

优先从 `objectives`、`teamfights`、分数变化和时长节点中整理：

- 一血
- 首塔和重要建筑击杀
- 肉山击杀
- 信使阵亡
- 决定比赛走向的团战或连续击杀

如果数据支持，给出时间线；如果不支持，就只总结关键转折，不要伪造精确时间。

### 7. 分析团战

如果 `teamfights` 存在，概括：

- 团战次数
- 关键团战发生的大致阶段
- 双方主要输出点、承伤点、治疗点
- 哪几波团战直接改变了经济或局势

不要机械罗列每一波团战，优先保留最有解释力的内容。

### 8. 处理聊天记录

如果 `chat` 存在，过滤明显系统消息，只摘取少量对理解比赛有帮助或明显有趣的内容。不要把整段聊天原样倾倒给用户。

除了摘录原话，还要补一小段“聊天气氛分析”，说明这些聊天更像：

- 开局互相试探
- 优势方整活
- 劣势方嘴硬或心态波动
- 团战后情绪上头

分析要轻松，但不要恶意揣测玩家人格。

## 输出要求

默认输出为结构化 Markdown，建议保持以下顺序：

```markdown
# Dota2 比赛分析报告

## 比赛概况

## 双方阵容

## 玩家表现

## 关键事件与转折

## 团战总结

## 阵容与胜负原因

## 聊天摘录（如有）
```

如果用户提供的是 `account_id`，默认输出为玩家账户分析报告，建议保持以下顺序：

```markdown
# Dota2 玩家账户分析报告

## 玩家概况
- account_id: xxx
- 玩家名: xxx
- rank tier: xx
- leaderboard rank: xx（如有）

## 近期表现
- 最近样本: xx 场
- 胜率: xx%
- 简评: xxx

## 常用英雄
| 英雄 | 场次 | 胜场 | 胜率 | 结论 |
|------|------|------|------|------|

## 数据画像
- 场均击杀: xx
- 场均死亡: xx
- 场均助攻: xx
- 风格判断: xxx

## 综合判断
- 优势: xxx
- 风险: xxx
- 一句话结论: xxx
```

## 写作要求

- 先下结论，再给证据
- 突出“为什么赢、为什么输、谁打得最好”
- 避免把输出写成 API 字段清单
- 数据不足时明确说明，不要脑补
- 除非用户要求详细版，否则默认控制篇幅，优先保留高信息量内容
- 比赛报告默认使用轻松、风趣、带一点解说感的语气，不要写成严肃赛后公文
- 幽默要建立在真实数据和实际比赛走势上，不要为了搞笑硬编剧情
- 如果有聊天记录，优先把聊天摘录和比赛走势联系起来，写出一点“场上在打，场下也在斗嘴”的感觉
- 可以适度使用俏皮小标题或一句话点评，但不要变成纯玩梗文

## 错误处理

- `match_id` 无效：提示用户检查比赛 ID
- `account_id` 无效：提示用户检查玩家账户 ID
- API 失败：说明获取数据失败，并保留可重试建议
- 数据不完整：照常输出可分析部分，并标记缺失模块
