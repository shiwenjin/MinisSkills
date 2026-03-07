from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / "SKILL.md"


class SkillOutputGuidanceTests(unittest.TestCase):
    def test_default_match_report_template_is_compact(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("默认输出为精简版结构化 Markdown", content)
        self.assertIn("## 一句话结论", content)
        self.assertIn("## 关键信息", content)
        self.assertIn("## 胜负手与关键转折", content)
        self.assertIn("## 玩家亮点", content)

    def test_default_account_report_template_is_compact(self) -> None:
        content = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("默认输出为精简版玩家账户分析报告", content)
        self.assertIn("## 核心判断", content)
        self.assertIn("## 近期表现", content)
        self.assertIn("## 常用英雄", content)
        self.assertIn("## 风格与建议", content)


if __name__ == "__main__":
    unittest.main()
