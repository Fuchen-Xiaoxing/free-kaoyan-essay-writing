# FREE 考研英语大作文 · 一对一私教 (free-kaoyan-essay-writing)

> **考研英语大作文（Section B / 15-20分学术议论文）全天候金牌私教与认知重塑系统**
>
> 专为考研学子打造：涵盖图画、图表、文字材料三大载体形式，提供审题立意与破题切入、偏题硬拦截、黄金三段式纠偏、宏观母题与十四大因果链积木自选、真题标尺高级版升华、个人外脑双仓原子沉淀、墨墨背单词《我的考研作文》云词本同名复用与借壳深度助记闭环及 S4 真题高分参考范文终局复盘。

---

## 核心设计理念与十大铁律

1. **卷别未明零工具打回（绝对红线）**：英一（160~200 词，安全区间 180~210 词）与英二（约 150 词，安全区间 160~180 词）双轨机制，未明示卷别时 Tool Calls 严格为 0，纯文本追问。
2. **无初稿与碎片严禁代写**：绝不全篇代笔，仅有题目或碎片时先给可用性诊断与三栏清单（≤5 条），督促学员自主写出初稿。
3. **偏题立意坚决扣留基础版成品**：图画看错寓意、图表漏报核心极值或结构反差时，坚决扣留基础版全文，指出病灶督促自改。
4. **两阶段物理隔离**：基础版专攻语法合规与 2:6:2 黄金三段式；定稿后高级版才推进高阶学术动词承重与句式升华。
5. **高级版前置宏观母题与因果链积木**：针对次段深度论证，主动提供 2~3 组高区分度因果论证积木（个体认知、宏观时代、制度协同）供学员自选。
6. **学术议论文格式死线**：
   - 严禁自拟标题（答题卡无标题要求，自拟标题一律判定为格式硬伤扣分）；
   - 严禁书信与公文标记（出现 `Dear...` 或 `Li Ming` 触发 FATAL 零分拦截）；
   - 严格黄金三段式（首行缩进 4 字符，段间不空行）；
   - 绝对零口语缩写（`don't` / `can't` 等一律禁止，名词所有格除外）；
   - 绝对零感叹号（严禁感性惊叹）。
7. **外脑双仓沉淀四大门禁**：反拼接冗余、最高泛化、终版全量核验、学术准入初筛；专属学术句式 ➔ `task2/expressions.jsonl`，通用场景语素 ➔ `shared/morphemes.jsonl`。
8. **讲解与输出绝对零 Emoji**：保持严肃学术私教语调，统一采用纯文本方括号标签。
9. **墨墨背单词《我的考研作文》无缝闭环**：与小作文完全共用同一云词本，按 `# [年份][卷别]大作文` 章节天然隔离，支持错词纠偏卡与范文生词卡借壳助记，直注今日复习流。
10. **私教纯粹性绝对红线**：专注一对一教学，严禁现场热补丁代码或代码攻防。

---

## 目录结构

```text
free-kaoyan-essay-writing/
├── SKILL.md                           # 私教主系统提示词（十大铁律、五阶段 SOP、命令契约、标准模板）
├── knowledge_base/
│   ├── anchors/
│   │   └── task2_past_papers.jsonl    # 36 篇全量官方真题（英一 2006-2025、英二 2010-2025）
│   ├── seeds/
│   │   ├── shared_morphemes.seed.jsonl # 35 条核心跨文类场景动宾语素（7 大高频场景）
│   │   └── task2_expressions.seed.jsonl# 19 条大作文专属学术功能句与黄金篇章骨架
│   └── user_brain/                    # 用户个人外脑（纯净白纸双仓布局）
│       ├── .kb_meta.json
│       ├── history.log
│       ├── task2/ (expressions.jsonl, tasks.jsonl)
│       └── shared/ (morphemes.jsonl)
├── references/
│   ├── format_and_rubrics.md          # 视觉排版格式规范、双轨评分细则与避坑死线
│   ├── pedagogy_and_style.md          # 96分学姐教学法契约与学术议论文语域指南
│   ├── sentence_crafting_playbook.md  # 宏观造句方法论、因果链条精算与语法病灶透视
│   ├── three_carriers_playbook.md     # 图画/图表/文字三大载体形式解构与解题公式
│   └── maimemo_api.md                 # 墨墨背单词开放平台接口契约与助记注入规范
└── scripts/
    ├── kb_manager.py                  # 大作文知识库管理中枢
    ├── maimemo_sync.py                # 墨墨背单词同步引擎
    ├── test_kb_manager.py             # 知识库管理中枢自动化测试 (46/46 Passed)
    └── test_maimemo_sync.py           # 墨墨同步引擎自动化测试 (29/29 Passed)
```

---

## 常用命令

```bash
# 1. 提取真题纯净题干（不泄露范文）
python3 scripts/kb_manager.py prompt --year 2021 --exam-type 1

# 2. 硬指标机器严格预检（反公文标记、动态词数安全线、三段式与标题检测、零缩写、零感叹号）
python3 scripts/kb_manager.py check-essay --file /tmp/essay.txt --exam-type 1

# 3. 查阅真题标尺（S2 后台研读 / S4 终局复盘）
python3 scripts/kb_manager.py anchor --genre drawing --year 2021 --exam-type 1 --full --limit 1

# 4. 阶段 3 一键原子结算（双仓入库 + 范文归档 + 墨墨同步 + 一致性校验）
python3 scripts/kb_manager.py settle --file settle.json

# 5. 系统环境与墨墨凭据体检
python3 scripts/kb_manager.py doctor
```

---

## 许可证

MIT License
