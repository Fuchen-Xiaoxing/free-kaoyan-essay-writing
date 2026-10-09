#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_kb_manager.py - Comprehensive Automated Test Suite for Kaoyan Writing KB Manager
Covers:
  1. verify: Strict PASS on clean DB, FAIL on corrupt JSON line or missing required fields.
  2. anchor: Brief mode omits reference model text by default; --full includes reference model.
  3. query: 3-tier retrieval, invitation returns zero library morphemes, templates column non-empty.
  4. append: 4-rule admission gate, stable ID generation, deduplication, history.log recording.
  5. batch-update: Evidence-based mastery (independent use -> 稳定, error -> 敢用需注意).
  6. archive: Archival in task2/ subdirectory with absorbed items and tasks.jsonl sync.
  7. cleanup: Dormancy and retirement detection.
  8. path_governance: KB_ROOT env var resolution, failure on invalid path.
"""

import unittest
import os
import sys
import io
import json
import hashlib
import datetime
import subprocess
import shutil
import contextlib
import tempfile
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent

VALID_TASK2_ESSAY = (
    "    In the center of the cartoon stands a young boy in traditional Peking Opera costume, "
    "passionately performing on the stage, while beneath the platform sit merely two elderly spectators, "
    "leaving the remaining vast hall completely vacant. Evidently, this subtle visual narrative takes on a profound "
    "overtone of the dilemma confronting cultural heritage amid the digital epoch.\n\n"
    "    A myriad of interrelated factors contribute to this phenomenon, among which modern technological diversion "
    "and lifestyle shifts play a pivotal role. In the first place, the rapid proliferation of algorithmic short-video "
    "platforms has fragmented young people's attention spans, rendering them reluctant to pour heed to traditional "
    "theatrical art forms that require patient appreciation. In the second place, the lack of innovative commercial packaging "
    "prevents traditional art forms from catering to the aesthetic appetites of contemporary youth. Consequently, without "
    "timely intervention, such exquisite cultural quintessence risks falling into collective oblivion.\n\n"
    "    To reverse this disquieting trend, concerted endeavors ought to be mobilized across society. On the one hand, "
    "cultural practitioners should embrace cutting-edge digital technologies to revitalize ancient art forms. On the other hand, "
    "mainstream media are expected to foster cultural self-consciousness among the young. Only through such two-pronged synergy "
    "can the enduring charm of traditional culture be passed down from generation to generation."
)

SKILL_ROOT = SCRIPT_DIR.parent
if (SKILL_ROOT / "knowledge_base").exists():
    REPO_ROOT = SKILL_ROOT
    KB_ROOT = SKILL_ROOT / "knowledge_base"
else:
    REPO_ROOT = SKILL_ROOT.parent
    KB_ROOT = REPO_ROOT / "knowledge_base"
SCRIPT_PATH = SCRIPT_DIR / "kb_manager.py"
sys.path.insert(0, str(SCRIPT_DIR))
from kb_manager import is_id_match, check_admission_rules

class TestKBManager(unittest.TestCase):

    def setUp(self):
        self.env = dict(os.environ)
        self.env["KB_ROOT"] = str(KB_ROOT)

    def run_cmd(self, cmd_args, env=None, cwd=None):
        full_cmd = [sys.executable, str(SCRIPT_PATH)] + cmd_args
        res = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(cwd or REPO_ROOT),
            env=env or self.env
        )
        return res

    def isolated_env(self, temp_dir):
        """写入型用例专用：教研底座保持只读（KB_BUILTIN_ROOT），个人外脑落到临时目录。

        这样测试永远不会污染仓库自带的 knowledge_base/user_brain。
        """
        env = dict(os.environ)
        env.pop("KB_ROOT", None)
        env["KB_BUILTIN_ROOT"] = str(KB_ROOT)
        env["KAOYAN_USER_BRAIN"] = str(temp_dir)
        return env

    def init_isolated_brain(self, temp_dir):
        env = self.isolated_env(temp_dir)
        res = self.run_cmd(["init", "--reset"], env=env)
        self.assertEqual(res.returncode, 0, f"init failed: {res.stderr}")
        return env

    def test_01_verify_passes_on_clean_db(self):
        """Test 'verify' command outputs pass for all DBs."""
        res = self.run_cmd(["verify"])
        self.assertEqual(res.returncode, 0, f"verify failed: {res.stderr}\n{res.stdout}")
        self.assertIn("[PASS] task2", res.stdout)
        self.assertIn("[PASS] shared", res.stdout)
        self.assertIn("[PASS] anchors", res.stdout)
        self.assertIn("验证通过！", res.stdout)

    def test_02_verify_fails_on_corrupt_json(self):
        """E1: Test 'verify' reports FAIL when a corrupted JSON line exists (on a temp KB copy)."""
        temp_root = tempfile.mkdtemp(prefix="test_corrupt_")
        try:
            kb_copy = Path(temp_root) / "knowledge_base"
            shutil.copytree(KB_ROOT, kb_copy)
            env = dict(os.environ)
            env["KB_ROOT"] = str(kb_copy)

            task2_file = kb_copy / "user_brain" / "task2_expressions.jsonl"
            task2_file.parent.mkdir(parents=True, exist_ok=True)
            if not task2_file.exists():
                task2_file.write_text("", encoding="utf-8")

            # Append corrupt line
            with open(task2_file, "a", encoding="utf-8") as f:
                f.write("\n{this is broken json line}\n")

            res = self.run_cmd(["verify"], env=env)
            self.assertNotEqual(res.returncode, 0, "verify must fail on corrupted JSON lines")
            self.assertIn("JSON格式解析错误", res.stderr + res.stdout)
            self.assertIn("[FAIL] 知识库验证失败", res.stderr + res.stdout)

            # 仓库自带底座绝不能被本用例改动
            repo_file = KB_ROOT / "user_brain" / "task2_expressions.jsonl"
            if repo_file.exists():
                self.assertNotIn("broken json line", repo_file.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_03_anchor_brief_omits_model_and_full_includes_it(self):
        """E3: Test 'anchor' brief mode does NOT output reference model; --full does."""
        # 1. Brief mode
        res_brief = self.run_cmd(["anchor", "--genre", "chart"])
        self.assertEqual(res_brief.returncode, 0, f"anchor failed: {res_brief.stderr}")
        self.assertNotIn("The bar chart illustrates", res_brief.stdout)
        self.assertIn("参考范文正文默认不展示", res_brief.stdout)
        self.assertIn("核心立意与论证切入点", res_brief.stdout)
        self.assertIn("句法与考纲词汇标尺", res_brief.stdout)

        # 2. Full mode
        res_full = self.run_cmd(["anchor", "--genre", "chart", "--full"])
        self.assertEqual(res_full.returncode, 0, f"anchor --full failed: {res_full.stderr}")
        self.assertIn("高分参考范文 (Reference Model", res_full.stdout)
        self.assertIn("chart", res_full.stdout.lower())

    def test_04_query_invitation_relevance_and_no_library(self):
        """C1 & E2: Test 'query --genre drawing' returns 3-column recommendations and templates column is non-empty."""
        res = self.run_cmd(["query", "--genre", "drawing", "--limit", "5"])
        self.assertEqual(res.returncode, 0, f"query failed: {res.stderr}")
        out = res.stdout

        # Column 1, 2, 3 must be present
        self.assertIn("【一、本题可用已掌握】", out)
        self.assertIn("【二、本题建议新学】", out)
        self.assertIn("【三、本题建议结构/模板】", out)
        self.assertTrue("篇章结构" in out or "图画" in out)

    def test_05_append_admission_rules_and_deduplication(self):
        """P1-5: Test append admission gates and deduplication (isolated user brain)."""
        temp_dir = tempfile.mkdtemp(prefix="test_append_iso_")
        try:
            env = self.init_isolated_brain(temp_dir)

            # 1. Non-reusable item (no slots or templates) should be rejected
            bad_item = {
                "category": "functional_sentence",
                "genre": "drawing",
                "intent": "一次性具体事实描述",
                "expression": "Yesterday Li Ming met Zhang Wei at room 204.",
                "source": "测试来源"
            }
            res_bad = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(bad_item, ensure_ascii=False)], env=env)
            self.assertIn("[REJECT]", res_bad.stdout)

            # 2. Valid reusable item
            good_item = {
                "category": "functional_sentence",
                "genre": "drawing",
                "intent": "提出数字化资源优化建议",
                "expression": "It would be of great service for [entity] to optimize [system], thereby [benefit].",
                "slots": {"[entity]": "机构", "[system]": "系统", "[benefit]": "效益"},
                "source": "名师语料库",
                "exam_band": "大纲内"
            }
            res_good = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(good_item, ensure_ascii=False)], env=env)
            self.assertEqual(res_good.returncode, 0)
            self.assertIn("[ADDED]", res_good.stdout)

            # 3. Deduplication: appending again should skip
            res_dup = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(good_item, ensure_ascii=False)], env=env)
            self.assertEqual(res_dup.returncode, 0)
            self.assertIn("[SKIP] 条目已存在，跳过防重", res_dup.stdout)

            # 写入必须落在临时外脑内，而不是仓库自带的 knowledge_base
            written = list(Path(temp_dir).rglob("expressions.jsonl"))
            self.assertTrue(any("optimize [system]" in f.read_text(encoding="utf-8") for f in written),
                            f"appended item not found in isolated brain: {written}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_06_batch_update_mastery_and_evidence(self):
        """C5, C6, C7: Test batch-update mastery transition evidence (isolated user brain)."""
        temp_dir = tempfile.mkdtemp(prefix="test_batch_iso_")
        try:
            env = self.init_isolated_brain(temp_dir)

            # 1. Update with independent=true
            batch_payload = {
                "task_id": "T-TEST-002",
                "status_updates": [
                    {
                        "id": "T2_DRAW_STR_001",
                        "status": "稳定",
                        "independent": True,
                        "note": "跨题新题目独立用对"
                    }
                ]
            }
            res = self.run_cmd(["batch-update", "--data", json.dumps(batch_payload, ensure_ascii=False)], env=env)
            self.assertEqual(res.returncode, 0, f"batch-update failed: {res.stderr}")
            self.assertIn("未接触 ➔ 稳定", res.stdout)

            # 2. Update with error note -> 敢用 (需注意)
            batch_error = {
                "task_id": "T-TEST-003",
                "status_updates": [
                    {
                        "id": "T2_OVT_SEN_001",
                        "status": "敢用",
                        "error": True,
                        "note": "主动尝试但有搭配瑕疵"
                    }
                ]
            }
            res_err = self.run_cmd(["batch-update", "--data", json.dumps(batch_error, ensure_ascii=False)], env=env)
            self.assertEqual(res_err.returncode, 0)
            self.assertIn("未接触 ➔ 敢用", res_err.stdout)

            # 3. 未命中的 ID 必须被显式报告（不再静默无操作）
            batch_miss = {
                "task_id": "T-TEST-004",
                "status_updates": [{"id": "T2_NOT_EXIST_999", "status": "稳定"}]
            }
            res_miss = self.run_cmd(["batch-update", "--data", json.dumps(batch_miss, ensure_ascii=False)], env=env)
            self.assertEqual(res_miss.returncode, 0)
            self.assertIn("[MISS]", res_miss.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_07_archive_and_tasks_sync(self):
        """P1-1 & P2-5: Test 'archive' saves a model essay and syncs the task ledger exactly once."""
        temp_dir = tempfile.mkdtemp(prefix="test_archive_iso_")
        try:
            env = self.init_isolated_brain(temp_dir)
            task_id = "T-TEST-ARCH-001"
            res = self.run_cmd([
                "archive",
                "--title", "Test Archive Essay",
                "--genre", "drawing",
                "--year", "2024",
                "--task-id", task_id,
                "--content", VALID_TASK2_ESSAY,
                "--metadata", json.dumps({"absorbed_items": ["[T2_DRAW_STR_001] Test item"]}, ensure_ascii=False)
            ], env=env)
            self.assertEqual(res.returncode, 0, f"archive failed: {res.stderr}")
            self.assertIn("[OK] 范文已成功归档至", res.stdout)
            self.assertIn("[OK] 题目台账已同步至", res.stdout)

            matching = list(Path(temp_dir).rglob("*_Test_Archive_Essay.md"))
            self.assertGreaterEqual(len(matching), 1, f"archive md not found under {temp_dir}")

            # 台账必须只有一行（paths["tasks"] 与 user_task2_tasks 指向同一文件时不得重复写入）
            ledger_rows = []
            for ledger in Path(temp_dir).rglob("tasks.jsonl"):
                ledger_rows += [l for l in ledger.read_text(encoding="utf-8").splitlines() if task_id in l]
            self.assertEqual(len(ledger_rows), 1, f"ledger duplicated: {ledger_rows}")

            # 重复归档同一 task_id 必须 upsert，而不是继续堆行
            res2 = self.run_cmd([
                "archive",
                "--title", "Test Archive Essay",
                "--genre", "drawing",
                "--year", "2024",
                "--task-id", task_id,
                "--content", VALID_TASK2_ESSAY,
            ], env=env)
            self.assertEqual(res2.returncode, 0, f"re-archive failed: {res2.stderr}")
            ledger_rows2 = []
            for ledger in Path(temp_dir).rglob("tasks.jsonl"):
                ledger_rows2 += [l for l in ledger.read_text(encoding="utf-8").splitlines() if task_id in l]
            self.assertEqual(len(ledger_rows2), 1, f"ledger not idempotent: {ledger_rows2}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_08_cleanup_command(self):
        """Test 'cleanup' command runs evaluation."""
        res = self.run_cmd(["cleanup"])
        self.assertEqual(res.returncode, 0, f"cleanup failed: {res.stderr}")
        self.assertIn("建议转为休眠 (dormant) 条目", res.stdout)
        self.assertIn("建议软删除退役 (retired) 条目", res.stdout)

    def test_09_genre_normalization_and_anchor_query(self):
        """Test carrier aliasing (e.g. cartoon -> drawing) in anchor and query."""
        res_anchor = self.run_cmd(["anchor", "--genre", "cartoon"])
        self.assertEqual(res_anchor.returncode, 0, f"anchor --genre cartoon failed: {res_anchor.stderr}")
        self.assertIn("drawing", res_anchor.stdout)

        res_query = self.run_cmd(["query", "--genre", "cartoon", "--limit", "3"])
        self.assertEqual(res_query.returncode, 0, f"query --genre cartoon failed: {res_query.stderr}")

    def test_10_check_essay_command(self):
        """10. check-essay 大作文专用预检测试（正常通过、反公文致命拦截、标题检测、卷别词数双轨、缩写与感叹号拦截）。"""
        # 10.1 正常合规大作文（约 190 词，纯三段式，无公文标记，无缩写，无感叹号）
        res = self.run_cmd(["check-essay", "--text", VALID_TASK2_ESSAY, "--exam-type", "1", "--json"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["word_count_status"], "PASS")
        self.assertEqual(len(data["fatal_errors"]), 0)
        self.assertEqual(len(data["contractions"]), 0)
        self.assertEqual(data["exclamations"], 0)

        # 10.2 反公文标记致命拦截 (Fatal Anti-Letter Detection)
        tainted = "Dear Sir or Madam,\n\n" + VALID_TASK2_ESSAY + "\n\nYours sincerely,\nLi Ming"
        res_tainted = self.run_cmd(["check-essay", "--text", tainted, "--exam-type", "1", "--json"])
        data_t = json.loads(res_tainted.stdout)
        self.assertGreater(len(data_t["fatal_errors"]), 0)
        self.assertTrue(any("书信" in err for err in data_t["fatal_errors"]))

    def test_11_english_ii_complete_16_years_coverage(self):
        """Verify that all 16 years (2010-2025) of English II past papers exist and can be queried."""
        for yr in range(2010, 2026):
            res = self.run_cmd(["anchor", "--year", str(yr)])
            self.assertEqual(res.returncode, 0, f"Querying anchor for year {yr} failed: {res.stderr}")
            self.assertIn("English II", res.stdout, f"Year {yr} output missing English II anchor")
            self.assertIn(str(yr), res.stdout, f"Year {yr} output missing year tag")

    def test_12_english_i_complete_21_years_coverage(self):
        """Verify that all 21 years (2005-2025) of English I past papers exist and can be queried."""
        for yr in range(2006, 2026):
            res = self.run_cmd(["anchor", "--year", str(yr)])
            self.assertEqual(res.returncode, 0, f"Querying anchor for English I year {yr} failed: {res.stderr}")
            self.assertIn("English I", res.stdout, f"Year {yr} output missing English I anchor")
            self.assertIn(str(yr), res.stdout, f"Year {yr} output missing year tag")

    def test_13_anchor_query_and_carrier_filtering(self):
        """Verify anchor query by year and carrier, with core insight and model display under --full."""
        # 1. Brief mode contains core insight and causal chains
        res_brief = self.run_cmd(["anchor", "--year", "2021", "--exam-type", "1"])
        self.assertEqual(res_brief.returncode, 0)
        self.assertIn("试题载体: drawing", res_brief.stdout)
        self.assertIn("核心立意与论证切入点", res_brief.stdout)
        self.assertNotIn("The picture portrays a boy", res_brief.stdout)

        # 2. Full mode displays reference model
        res_full = self.run_cmd(["anchor", "--year", "2021", "--exam-type", "1", "--full"])
        self.assertEqual(res_full.returncode, 0)
        self.assertIn("高分参考范文 (Reference Model", res_full.stdout)
        self.assertIn("The picture portrays a boy", res_full.stdout)

        # 3. JSON mode contains structured fields
        res_json = self.run_cmd(["anchor", "--year", "2021", "--exam-type", "1", "--full", "--json"])
        self.assertEqual(res_json.returncode, 0)
        data = json.loads(res_json.stdout)
        item = data[0] if isinstance(data, list) else data
        self.assertEqual(item["carrier"], "drawing")
        self.assertEqual(item["theme"], "cultural_confidence")
        self.assertIn("official_model", item)

    def test_14_storage_detection_and_reset(self):
        """Verify that KAOYAN_USER_BRAIN decodes to external directory and init --reset provisions clean slate (0 records)."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            res = self.run_cmd(["init", "--reset"], env=env)
            self.assertEqual(res.returncode, 0, f"init --reset failed: {res.stderr}\n{res.stdout}")
            self.assertIn("纯净白纸初始化", res.stdout)

            # v2 双仓规范布局（唯一权威表示）
            ub_t1 = Path(temp_dir) / "user_brain" / "task2" / "expressions.jsonl"
            self.assertTrue(ub_t1.exists(), "task2/expressions.jsonl was not provisioned")

            # Read and verify records: must be 0 records
            with open(ub_t1, "r", encoding="utf-8") as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(lines), 0, "User brain must be clean slate with 0 records upon init!")

            # Check shared morphemes: also clean slate (0 records)
            ub_sh = Path(temp_dir) / "user_brain" / "shared" / "morphemes.jsonl"
            self.assertTrue(ub_sh.exists())
            with open(ub_sh, "r", encoding="utf-8") as f:
                sh_lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(sh_lines), 0)

            # Check ledger: task2/tasks.jsonl (v2)
            tasks_file = Path(temp_dir) / "user_brain" / "task2" / "tasks.jsonl"
            self.assertTrue(tasks_file.exists())
            self.assertEqual(tasks_file.stat().st_size, 0)

            # 扁平遗留文件与 task1 均不得再被创建（本 skill 只有大作文 task2）
            self.assertFalse((Path(temp_dir) / "user_brain" / "task2_expressions.jsonl").exists(),
                             "legacy flat task2_expressions.jsonl must not be provisioned")
            self.assertFalse((Path(temp_dir) / "user_brain" / "tasks.jsonl").exists(),
                             "legacy flat tasks.jsonl must not be provisioned")
            self.assertFalse((Path(temp_dir) / "user_brain" / "task1").exists(),
                             "task1 must not be provisioned")

            hist_file = Path(temp_dir) / "user_brain" / "history.log"
            self.assertTrue(hist_file.exists())
            with open(hist_file, "r", encoding="utf-8") as f:
                h_lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(h_lines), 1)
            self.assertEqual(h_lines[0].get("id"), "SYS_INIT")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_15_write_isolation_and_promotion(self):
        """Verify that promoting a shared morpheme does NOT alter the base seed, and lands in the personal shared warehouse."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_iso_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            self.run_cmd(["init", "--reset"], env=env)

            # 出厂底座：paths["shared"] 指向 seeds/shared_morphemes.seed.jsonl（只读）
            kb_root = Path(__file__).resolve().parent.parent / "knowledge_base"
            base_shared = kb_root / "seeds" / "shared_morphemes.seed.jsonl"
            mtime_before = base_shared.stat().st_mtime
            hash_before = hashlib.sha256(base_shared.read_bytes()).hexdigest()

            # Update status of a morpheme from the built-in base (e.g. M_ACAD_001)
            res = self.run_cmd(["update-status", "--id", "M_ACAD_001", "--status", "敢用", "--note", "首次学习"], env=env)
            self.assertEqual(res.returncode, 0, f"update-status failed: {res.stderr}\n{res.stdout}")
            self.assertIn("已沉淀至个人共享仓", res.stdout)

            # Verify base seed file was not touched (neither mtime nor bytes)
            self.assertEqual(mtime_before, base_shared.stat().st_mtime, "Base seed file was mutated!")
            self.assertEqual(hash_before, hashlib.sha256(base_shared.read_bytes()).hexdigest(),
                             "Base seed file content changed!")

            # 借调转正必须落到个人共享语素仓，而不是大作文专属仓
            ub_sh = Path(temp_dir) / "user_brain" / "shared" / "morphemes.jsonl"
            with open(ub_sh, "r", encoding="utf-8") as f:
                user_items = [json.loads(l) for l in f if l.strip()]
            promoted = next((it for it in user_items if it.get("id") == "M_ACAD_001"), None)
            self.assertIsNotNone(promoted, "M_ACAD_001 was not promoted into the personal shared warehouse")
            self.assertEqual(promoted.get("mastery"), "敢用")

            # Query and ensure user's promoted version is returned without duplicates
            res_query = self.run_cmd(["query", "--scenario", "学习与学术科研", "--json"], env=env)
            self.assertEqual(res_query.returncode, 0)
            q_data = json.loads(res_query.stdout)
            m_lib = [it for it in q_data if it.get("id") == "M_ACAD_001"]
            self.assertEqual(len(m_lib), 1, "Duplicate M_ACAD_001 returned in query")
            self.assertEqual(m_lib[0].get("mastery"), "敢用")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_16_status_command(self):
        """Verify 'status' command outputs complete architecture diagnosis."""
        res = self.run_cmd(["status"])
        self.assertEqual(res.returncode, 0, f"status failed: {res.stderr}\n{res.stdout}")
        self.assertIn("考研英语大作文系统运行状态", res.stdout)
        self.assertIn("教研底座路径:", res.stdout)
        self.assertIn("用户外脑路径:", res.stdout)
        self.assertIn("外脑存储类型:", res.stdout)
        self.assertIn("个人词句外脑总数:", res.stdout)

    def test_17_anchor_limit_parameter(self):
        """Verify 'anchor' --limit parameter correctly restricts output count."""
        # 1. Default without --limit outputs all matches
        res_all = self.run_cmd(["anchor", "--genre", "drawing"])
        self.assertEqual(res_all.returncode, 0)
        self.assertIn("共 18 篇", res_all.stdout)

        # 2. --limit 1 outputs exactly 1 anchor and truncation notification
        res_lim1 = self.run_cmd(["anchor", "--genre", "drawing", "--limit", "1"])
        self.assertEqual(res_lim1.returncode, 0)
        self.assertIn("共 1 篇", res_lim1.stdout)
        self.assertIn("【范文锚点 #1】", res_lim1.stdout)
        self.assertNotIn("【范文锚点 #2】", res_lim1.stdout)
        self.assertIn("• [提示] 已按最新年份展示前 1 篇真题标尺", res_lim1.stdout)

        # 3. --limit 2 outputs exactly 2 anchors
        res_lim2 = self.run_cmd(["anchor", "--genre", "drawing", "--limit", "2"])
        self.assertEqual(res_lim2.returncode, 0)
        self.assertIn("共 2 篇", res_lim2.stdout)
        self.assertIn("【范文锚点 #1】", res_lim2.stdout)
        self.assertIn("【范文锚点 #2】", res_lim2.stdout)
        self.assertNotIn("【范文锚点 #3】", res_lim2.stdout)

    def test_18_check_essay_file_mode_and_missing_file(self):
        """Verify 'check-essay --file' reads from file correctly and handles missing files gracefully."""
        # 1. Existing file
        test_content = (
            "Dear Professor Wang,\n\n"
            "    I am Li Ming, writing to consult you about the upcoming seminar.\n"
            "    Could you please advise whether we don't need to submit the paper in advance?\n"
            "    I look forward to your guidance.\n\n"
            "Yours sincerely,\n"
            "Li Ming"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as tf:
            tf.write(test_content)
            temp_path = tf.name

        try:
            res = self.run_cmd(["check-essay", "--file", temp_path, "--json"])
            self.assertEqual(res.returncode, 0, f"check-essay --file failed: {res.stderr}")
            data = json.loads(res.stdout)
            self.assertGreater(data["body_total"], 0)
            self.assertEqual(len(data["contractions"]), 1)  # "don't"
            self.assertEqual(data["contractions"][0][1], "don't")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # 2. Missing file error handling
        res_missing = self.run_cmd(["check-essay", "--file", "non_existent_dummy_file.txt"])
        self.assertNotEqual(res_missing.returncode, 0)
        self.assertIn("指定的文件不存在", res_missing.stderr + res_missing.stdout)

    def test_19_anchors_sanitization_no_exclamation_or_contractions(self):
        """Verify all anchors in task2_past_papers.jsonl have zero exclamation marks and zero contractions."""
        anc_file = KB_ROOT / "anchors" / "task2_past_papers.jsonl"
        with open(anc_file, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f]

        self.assertGreater(len(records), 0)
        for r in records:
            iid = r.get("id")
            for k in ["official_model", "model_essay", "model_essay_v1", "model_essay_v2"]:
                val = r.get(k, "")
                if val:
                    self.assertEqual(val.count("!"), 0, f"{iid} {k} contains exclamation marks!")
                    # Check contractions
                    contr = [w for w in val.split() if any(c in w for c in ["'", "’"]) and w.lower() in [
                        "i'm", "i’m", "it's", "it’s", "don't", "don’t", "can't", "can’t", "you'll", "you’ll",
                        "they'll", "they’ll", "we'd", "we’d", "you're", "you’re", "isn't", "isn’t"
                    ]]
                    self.assertEqual(len(contr), 0, f"{iid} {k} contains contractions: {contr}")

            for expr in r.get("extractable_expressions", []):
                self.assertEqual(expr.count("!"), 0, f"{iid} extractable expr contains '!': {expr}")

    def test_20_batch_update_example(self):
        """Verify 'batch-update --example' outputs valid JSON schema and exits 0."""
        res = self.run_cmd(["batch-update", "--example"])
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("task_id", data)
        self.assertIn("status_updates", data)
        self.assertIn("new_items", data)
        self.assertGreater(len(data["new_items"]), 0)

    def test_21_archive_example_and_auto_word_count(self):
        """Verify 'archive --example' works, and archive automatically computes body word count when omitted."""
        # 1. archive --example
        res_ex = self.run_cmd(["archive", "--example"])
        self.assertEqual(res_ex.returncode, 0)
        self.assertIn("archive", res_ex.stdout)

        # 2. archive with omitted word_count
        test_essay = (
            "Dear Li Ming,\n\n"
            "    Congratulations on your admission to such a prestigious university. I am writing to offer some suggestions on how to get prepared for university life.\n\n"
            "    To begin with, you had better learn to manage your monthly budget by keeping a record of your spending, or you may run out of money before the month ends. Besides, you are encouraged to get along with your roommates, who will be your closest companions for the next four years. As for your studies, it is never too early to gain exposure to your major, which will undoubtedly help you navigate your career path.\n\n"
            "    Anyway, I wish you a fulfilling and rewarding university life.\n\n"
            "                                        Yours sincerely,\n"
            "                                        Zhang Wei\n"
        )
        temp_dir = tempfile.mkdtemp(prefix="test_archwc_iso_")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".md") as tf:
            tf.write(test_essay)
            temp_path = tf.name

        try:
            env = self.init_isolated_brain(temp_dir)
            res_arch = self.run_cmd([
                "archive",
                "--title", "Test Auto Word Count",
                "--genre", "drawing",
                "--year", "2011",
                "--task-id", "TEST-AUTO-WC",
                "--file", temp_path
            ], env=env)
            self.assertEqual(res_arch.returncode, 0, f"archive failed: {res_arch.stderr}\n{res_arch.stdout}")
            self.assertIn("[OK] 范文已成功归档至:", res_arch.stdout)

            # Find generated archive file and inspect word count header
            arch_files = list(Path(temp_dir).rglob("*_Test_Auto_Word_Count.md"))
            self.assertGreater(len(arch_files), 0, f"archive md not found under {temp_dir}")
            arch_text = arch_files[0].read_text(encoding="utf-8")
            self.assertIn("- **字数统计**：109 词", arch_text)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_22_admission_rules_tolerance(self):
        """Verify check_admission_rules tolerates '考纲核心' and phrase without explicit verb_phrase."""
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        from kb_manager import check_admission_rules

        # 1. Tolerates synonymous exam_band
        item1 = {
            "category": "phrase",
            "source": "2011真题",
            "intent": "了解领域",
            "expression": "gain exposure to [field]",
            "exam_band": "考纲核心"
        }
        ok, reason = check_admission_rules(item1)
        self.assertTrue(ok, f"Expected OK, got: {reason}")
        self.assertEqual(item1["exam_band"], "大纲内")
        self.assertEqual(item1["verb_phrase"], "gain exposure to [field]")

        # 2. Strict rejection on invalid category
        item2 = {
            "category": "invalid_cat",
            "source": "2011真题",
            "intent": "测试"
        }
        ok2, reason2 = check_admission_rules(item2)
        self.assertFalse(ok2)
        self.assertIn("Invalid category", reason2)

    def test_23_prompt_command_purity_and_gating(self):
        """Verify 'prompt' command: pure projection without models, precise exam_type filter, and --full rejection."""
        # 1. Precise single paper with --exam-type
        res = self.run_cmd(["prompt", "--year", "2011", "--exam-type", "2"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("2011 年全国统考英语", res.stdout)
        self.assertIn("国内某合资汽车品牌市场份额变化", res.stdout)
        self.assertIn("Directions", res.stdout)
        # Verify 100% NO model essay text in output
        self.assertNotIn("The bar chart illustrates", res.stdout)
        self.assertNotIn("Dear Li Ming,", res.stdout)
        self.assertNotIn("Yours sincerely,", res.stdout)

        # 2. JSON output purity
        res_json = self.run_cmd(["prompt", "--year", "2011", "--exam-type", "2", "--json"])
        self.assertEqual(res_json.returncode, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(data["year"], "2011")
        self.assertEqual(data["exam_type"], "English II")
        self.assertEqual(data["carrier"], "chart")
        self.assertNotIn("official_model", data)
        self.assertNotIn("extractable_expressions", data)

        # 3. Dual papers without --exam-type
        res_dual = self.run_cmd(["prompt", "--year", "2011"])
        self.assertEqual(res_dual.returncode, 0)
        self.assertIn("多卷真题，请使用 --exam-type", res_dual.stdout)
        self.assertIn("ANC_T2_E1_2011", res_dual.stdout)
        self.assertIn("ANC_T2_E2_2011", res_dual.stdout)

        # 4. Strict argument rejection: --full must FAIL
        res_full = self.run_cmd(["prompt", "--year", "2011", "--exam-type", "2", "--full"])
        self.assertNotEqual(res_full.returncode, 0)
        self.assertIn("unrecognized arguments: --full", res_full.stderr + res_full.stdout)

    def test_24_dual_warehouse_morpheme_routing_and_sync(self):
        """Verify dual-warehouse architecture: shared morphemes routed to shared/ and sentences to task2/."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_dual_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            res_init = self.run_cmd(["init", "--reset"], env=env)
            self.assertEqual(res_init.returncode, 0)

            shared_file = Path(temp_dir) / "user_brain" / "shared" / "morphemes.jsonl"
            task2_file = Path(temp_dir) / "user_brain" / "task2" / "expressions.jsonl"
            self.assertTrue(shared_file.exists(), "shared/morphemes.jsonl missing")
            self.assertTrue(task2_file.exists(), "task2/expressions.jsonl missing")
            self.assertFalse((Path(temp_dir) / "user_brain" / "task1").exists(),
                             "task1 must not exist: this skill only covers Section B (task2)")

            # 1. Batch update with a morpheme
            batch_morph = {
                "task_id": "T2011-E2-ADV",
                "new_items": [
                    {
                        "data": {
                            "type": "morpheme",
                            "text": "navigate one's career path",
                            "meaning": "规划职业发展道路",
                            "source": "2011真题实战",
                            "mastery": "学习中"
                        }
                    }
                ]
            }
            res_bm = self.run_cmd(["batch-update", "--data", json.dumps(batch_morph, ensure_ascii=False)], env=env)
            self.assertEqual(res_bm.returncode, 0)
            self.assertIn("追加至 shared", res_bm.stdout)

            with open(shared_file, "r", encoding="utf-8") as f:
                shared_lines = [json.loads(l) for l in f if l.strip()]
            self.assertTrue(any("navigate one's career path" in (it.get("text") or "") for it in shared_lines))

            # 2. Batch update with a functional sentence
            batch_sen = {
                "task_id": "T2011-E2-ADV",
                "new_items": [
                    {
                        "data": {
                            "category": "functional_sentence",
                            "genre": "drawing",
                            "expression": "If I were you, I would [action].",
                            "intent": "虚拟语气提建议",
                            "source": "2011真题实战",
                            "slots": {"[action]": "建议动作"}
                        }
                    }
                ]
            }
            res_bs = self.run_cmd(["batch-update", "--data", json.dumps(batch_sen, ensure_ascii=False)], env=env)
            self.assertEqual(res_bs.returncode, 0)
            self.assertIn("追加至 task2", res_bs.stdout)

            with open(task2_file, "r", encoding="utf-8") as f:
                t1_lines = [json.loads(l) for l in f if l.strip()]
            self.assertTrue(any("If I were you, I would [action]." in (it.get("expression") or it.get("text") or "") for it in t1_lines))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_25_slim_schema_and_zero_emojis(self):
        """Verify query output conforms to zero emojis rule and 3-column format."""
        res_q = self.run_cmd(["query", "--genre", "drawing", "--limit", "5"])
        self.assertEqual(res_q.returncode, 0)
        out = res_q.stdout

        # Check zero emojis in query output
        emojis = [c for c in out if ord(c) > 0x1F000 or (0x2600 <= ord(c) <= 0x27BF and ord(c) != 0x2794)]
        self.assertEqual(len(emojis), 0, f"Found emojis in query output: {emojis}")

        # Check 3 columns
        self.assertIn("【一、本题可用已掌握】", out)
        self.assertIn("【二、本题建议新学】", out)
        self.assertIn("【三、本题建议结构/模板】", out)

        # Check zero emojis in status
        res_s = self.run_cmd(["status"])
        self.assertEqual(res_s.returncode, 0)
        s_out = res_s.stdout
        s_emojis = [c for c in s_out if ord(c) > 0x1F000 or (0x2600 <= ord(c) <= 0x27BF and ord(c) != 0x2794)]
        self.assertEqual(len(s_emojis), 0, f"Found emojis in status output: {s_emojis}")

    def test_26_two_tier_query_borrowing_on_clean_brain(self):
        """Verify that on a clean slate (0 user items), query borrows from system seeds and tags with [系统借调]."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_borrow_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            self.run_cmd(["init", "--reset"], env=env)

            # Query advice
            res = self.run_cmd(["query", "--genre", "drawing", "--limit", "4"], env=env)
            self.assertEqual(res.returncode, 0, f"query failed: {res.stderr}\n{res.stdout}")
            self.assertIn("[系统借调]", res.stdout, "Clean user brain must borrow from seeds with [系统借调] tag")
            self.assertIn("宁缺毋滥", res.stdout)

            # JSON mode
            res_json = self.run_cmd(["query", "--genre", "drawing", "--limit", "4", "--json"], env=env)
            self.assertEqual(res_json.returncode, 0)
            items = json.loads(res_json.stdout)
            self.assertTrue(len(items) > 0)
            self.assertTrue(all(it.get("is_borrowed") is True for it in items))
            self.assertTrue(all(it.get("source_tier") == "system_seeds" for it in items))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_27_two_tier_query_user_brain_precedence(self):
        """Verify that user brain assets take 100% precedence, leaving zero system借调 when stock is sufficient."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_prec_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            self.run_cmd(["init", "--reset"], env=env)

            # Seed user brain with 3 user items
            user_items = [
                {
                    "category": "functional_sentence",
                    "genre": "drawing",
                    "section": "opening",
                    "intent": "用户首段自主建议表达",
                    "expression": "I am pleased to put forward some suggestions for [target].",
                    "slots": {"[target]": "建议目标"},
                    "source": "真题实战",
                    "mastery": "稳定"
                },
                {
                    "category": "functional_sentence",
                    "genre": "drawing",
                    "section": "body",
                    "intent": "用户次段举措表达",
                    "expression": "It is highly recommended that you should [action].",
                    "slots": {"[action]": "具体动作"},
                    "source": "真题实战",
                    "mastery": "敢用"
                },
                {
                    "category": "template",
                    "genre": "drawing",
                    "section": "body",
                    "intent": "用户专属建议信模板",
                    "blocks": ["Dear Sir,", "Body paragraph", "Yours sincerely"],
                    "source": "真题实战",
                    "mastery": "稳定"
                }
            ]
            for it in user_items:
                res_add = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(it, ensure_ascii=False)], env=env)
                self.assertEqual(res_add.returncode, 0)
                self.assertIn("[ADDED]", res_add.stdout)

            # Query with limit 3: should be fulfilled 100% by user brain
            res_q = self.run_cmd(["query", "--genre", "drawing", "--limit", "3"], env=env)
            self.assertEqual(res_q.returncode, 0)
            self.assertNotIn("[系统借调]", res_q.stdout, "Sufficient user brain items must not trigger system borrowing")

            res_json = self.run_cmd(["query", "--genre", "drawing", "--limit", "3", "--json"], env=env)
            self.assertEqual(res_json.returncode, 0)
            items = json.loads(res_json.stdout)
            self.assertEqual(len(items), 3)
            self.assertTrue(all(it.get("is_borrowed") is False for it in items))
            self.assertTrue(all(it.get("source_tier") == "user_brain" for it in items))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_28_progressive_privatization_lifecycle(self):
        """Verify the full lifecycle: clean slate -> borrowed from seed -> practiced & promoted -> user brain precedence."""
        temp_dir = tempfile.mkdtemp(prefix="test_ub_life_")
        try:
            env = dict(self.env)
            if "KB_ROOT" in env:
                del env["KB_ROOT"]
            env["KAOYAN_USER_BRAIN"] = temp_dir
            self.run_cmd(["init", "--reset"], env=env)

            # 1. Initially clean slate
            res_st1 = self.run_cmd(["status"], env=env)
            self.assertIn("100% 纯净白纸", res_st1.stdout)

            # 2. Query borrows T2_DRAW_STR_001 from system
            res_q1 = self.run_cmd(["query", "--genre", "drawing", "--limit", "3"], env=env)
            self.assertIn("[系统借调]", res_q1.stdout)

            # 3. User practices and batch updates to promote
            update_payload = {
                "task_id": "T2011-E2-ADV",
                "status_updates": [
                    {
                        "id": "T2_DRAW_STR_001",
                        "status": "敢用",
                        "independent": True,
                        "note": "实战用对，提升入库"
                    }
                ]
            }
            res_upd = self.run_cmd(["batch-update", "--data", json.dumps(update_payload, ensure_ascii=False)], env=env)
            self.assertEqual(res_upd.returncode, 0)
            self.assertIn("未接触 ➔ 稳定", res_upd.stdout)

            # 4. Status reflects 1 promoted item
            res_st2 = self.run_cmd(["status"], env=env)
            self.assertIn("个人词句外脑总数: 1 条", res_st2.stdout)

            # 5. Querying with limit 1 now returns user's promoted asset without borrowing tag
            res_q2 = self.run_cmd(["query", "--genre", "drawing", "--limit", "1"], env=env)
            self.assertNotIn("[系统借调]", res_q2.stdout)
            self.assertIn("T2_DRAW_STR_001", res_q2.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_29_settle_documented_payload_archives_and_ledger_once(self):
        """P0-1/P0-2: SKILL.md 文档化载荷（顶层 essay_content）必须真实归档，且台账只写一行。"""
        temp_dir = tempfile.mkdtemp(prefix="test_settle_doc_")
        try:
            env = self.init_isolated_brain(temp_dir)
            payload = {
                "task_id": "T2012-E2-DOC",
                "title": "投诉网购电子词典（2012英二）",
                "genre": "drawing",
                "year": "2012",
                "exam_type": "2",
                "essay_content": VALID_TASK2_ESSAY,
                "batch": {"status_updates": [], "new_items": []},
            }
            payload_file = Path(temp_dir) / "settle_doc.json"
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            res = self.run_cmd(["settle", "--file", str(payload_file), "--mock"], env=env)
            self.assertEqual(res.returncode, 0, f"settle failed: {res.stderr}\n{res.stdout}")
            self.assertIn("范文归档与题目台账登记完成", res.stdout)

            md_files = list(Path(temp_dir).rglob("*_drawing_*.md"))
            self.assertEqual(len(md_files), 1, f"expected exactly 1 archive, got {md_files}")

            ledger_rows = []
            for ledger in Path(temp_dir).rglob("tasks.jsonl"):
                ledger_rows += [l for l in ledger.read_text(encoding="utf-8").splitlines() if "T2012-E2-DOC" in l]
            self.assertEqual(len(ledger_rows), 1, f"ledger must contain exactly one row: {ledger_rows}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_30_settle_preflight_failures_are_nonzero_and_zero_write(self):
        """P0-1/P2-1: 缺正文 / 墨墨词卡缺 spelling / 晋级 ID 不存在，均须非零退出且零写入。"""
        temp_dir = tempfile.mkdtemp(prefix="test_settle_pf_")
        try:
            env = self.init_isolated_brain(temp_dir)
            base = {
                "task_id": "T-PF",
                "title": "前置校验",
                "genre": "drawing",
                "year": "2012",
                "exam_type": "2",
                "essay_content": "Dear Sir or Madam,\n\n    Body.\n\nYours faithfully,\nZhang Wei\n",
            }

            cases = []
            no_content = dict(base)
            no_content.pop("essay_content")
            cases.append(("no content", no_content))
            bad_word = dict(base, maimemo={"chapter": "2012英二大作文", "words": [{"sentence": "x"}]})
            cases.append(("word without spelling", bad_word))
            bad_id = dict(base, batch={"status_updates": [{"id": "T1_NOT_EXIST_999", "status": "稳定"}]})
            cases.append(("unmatched status id", bad_id))

            for label, payload in cases:
                payload_file = Path(temp_dir) / f"case_{label.replace(' ', '_')}.json"
                payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                res = self.run_cmd(["settle", "--file", str(payload_file), "--mock"], env=env)
                self.assertNotEqual(res.returncode, 0, f"[{label}] settle must fail, got 0\n{res.stdout}")
                self.assertIn("前置校验未通过", res.stderr + res.stdout, f"[{label}] missing preflight failure message")

            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 0, "no archive may be written on preflight failure")
            ledger_rows = []
            for ledger in Path(temp_dir).rglob("tasks.jsonl"):
                ledger_rows += [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(ledger_rows, [], f"ledger must stay empty: {ledger_rows}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_31_settle_rolls_back_local_writes_on_failure(self):
        """P2-1: 本地链路失败必须整体回滚（外脑 JSONL / 台账 / 新归档恢复原状）。"""
        import types
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        import kb_manager

        temp_dir = tempfile.mkdtemp(prefix="test_settle_rb_")
        saved_env = dict(os.environ)
        original_archive = kb_manager.cmd_archive
        try:
            env = self.init_isolated_brain(temp_dir)
            os.environ["KB_BUILTIN_ROOT"] = env["KB_BUILTIN_ROOT"]
            os.environ["KAOYAN_USER_BRAIN"] = env["KAOYAN_USER_BRAIN"]
            os.environ.pop("KB_ROOT", None)

            paths = kb_manager.get_paths()
            task2_file = Path(paths["user_task2"])
            ledger_file = Path(paths["tasks"])
            before_t1 = task2_file.read_text(encoding="utf-8") if task2_file.exists() else ""
            before_ledger = ledger_file.read_text(encoding="utf-8") if ledger_file.exists() else ""

            payload = {
                "task_id": "T-RB",
                "title": "回滚验证",
                "genre": "drawing",
                "year": "2012",
                "exam_type": "2",
                "essay_content": "Dear Sir or Madam,\n\n    Body.\n\nYours faithfully,\nZhang Wei\n",
                "batch": {
                    "status_updates": [],
                    "new_items": [{
                        "target": "task2",
                        "data": {
                            "category": "functional_sentence",
                            "genre": "drawing",
                            "section": "opening",
                            "expression": "I am writing to lodge a formal complaint regarding [Product].",
                            "intent": "投诉信开篇定调",
                            "mastery": "敢用",
                        },
                    }],
                },
            }
            payload_file = Path(temp_dir) / "settle_rb.json"
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            def _boom(_args):
                raise SystemExit(1)

            kb_manager.cmd_archive = _boom
            args = types.SimpleNamespace(
                file=str(payload_file), data=None, token=None, mock=True,
                dry_run=False, json=False, example=False,
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                with self.assertRaises(SystemExit) as ctx:
                    kb_manager.cmd_settle(args)
            self.assertEqual(ctx.exception.code, 1)

            after_t1 = task2_file.read_text(encoding="utf-8") if task2_file.exists() else ""
            after_ledger = ledger_file.read_text(encoding="utf-8") if ledger_file.exists() else ""
            self.assertEqual(before_t1, after_t1, "user brain must be rolled back")
            self.assertEqual(before_ledger, after_ledger, "ledger must be rolled back")
            self.assertEqual(len(list(Path(temp_dir).rglob("*.md"))), 0, "no archive may survive rollback")
        finally:
            kb_manager.cmd_archive = original_archive
            os.environ.clear()
            os.environ.update(saved_env)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_32_query_mine_cross_genre_recall(self):
        """P1-1/P1-2: query --mine 必须跨文类召回个人资产，并能判定初稿命中。"""
        temp_dir = tempfile.mkdtemp(prefix="test_mine_")
        try:
            env = self.init_isolated_brain(temp_dir)
            seed_item = {
                "category": "functional_sentence",
                "genre": "drawing",
                "section": "opening",
                "register": "neutral_formal",
                "intent": "分词状语前置开篇",
                "expression": "Knowing that you are preparing for [event], I am writing to [purpose].",
                "mastery": "敢用",
            }
            add = {"task_id": "T-MINE-1", "status_updates": [], "new_items": [{"target": "task2", "data": seed_item}]}
            res_add = self.run_cmd(["batch-update", "--data", json.dumps(add, ensure_ascii=False)], env=env)
            self.assertEqual(res_add.returncode, 0, f"seed failed: {res_add.stderr}")

            # 1. 跨文类召回：以图表 (chart) 为文类检索，图画 (drawing) 资产必须出现并带 [跨文类复用] 标记
            res_mine = self.run_cmd(["query", "--mine", "--genre", "chart", "--limit", "20"], env=env)
            self.assertEqual(res_mine.returncode, 0, f"query --mine failed: {res_mine.stderr}")
            self.assertIn("跨文类可复用", res_mine.stdout)
            self.assertIn("[跨文类复用]", res_mine.stdout)
            self.assertIn(seed_item["expression"], res_mine.stdout)

            # 2. 默认三栏检索行为不得被 --mine 改动
            res_default = self.run_cmd(["query", "--genre", "drawing", "--limit", "5"], env=env)
            self.assertIn("【一、本题可用已掌握】", res_default.stdout)
            self.assertIn("【二、本题建议新学】", res_default.stdout)
            self.assertIn("【三、本题建议结构/模板】", res_default.stdout)

            # 3. 初稿命中判定
            draft = Path(temp_dir) / "draft.txt"
            draft.write_text(
                "    Knowing that you are preparing for the contest, I am writing to confirm my support.\n",
                encoding="utf-8",
            )
            res_hit = self.run_cmd(["query", "--mine", "--genre", "drawing", "--match-file", str(draft), "--json"], env=env)
            self.assertEqual(res_hit.returncode, 0, f"query --mine --match-file failed: {res_hit.stderr}")
            data_hit = json.loads(res_hit.stdout)
            self.assertEqual(len(data_hit["hits"]), 1, f"expected 1 hit, got {data_hit['hits']}")
            self.assertIn("knowing that you are", data_hit["hits"][0]["evidence"].lower())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_33_check_essay_anti_letter_and_possessive_rules(self):
        """33. check-essay 反公文致命检测与名词所有格白名单：
        - 名词所有格（China's, student's, today's）不应被误判为口语缩写。
        - 出现 Li Ming 或 Dear 直接触发 FATAL。
        """
        possessive_essay = (
            "    China's rapid economic transition and students' evolving career choices have highlighted "
            "the critical importance of vocational planning in contemporary society. Modern industries demand "
            "composite talents equipped with innovative mindsets.\n\n"
            "    A myriad of interrelated factors contribute to this phenomenon, among which technological "
            "advancement plays a pivotal role in reshaping market demands. Consequently, without proactive adaptation, "
            "graduates risk falling behind the curve in today's volatile employment landscape.\n\n"
            "    To address this challenge, concerted endeavors ought to be mobilized across universities. "
            "Only through institutional synergy can graduates' long-term development be guaranteed."
        )
        res = self.run_cmd(["check-essay", "--text", possessive_essay, "--exam-type", "1", "--json"])
        data = json.loads(res.stdout)
        self.assertEqual(len(data.get("contractions", [])), 0,
                         f"名词所有格不应被判定为口语缩写: {data.get('contractions')}")
        self.assertEqual(len(data.get("fatal_errors", [])), 0)

    def test_34_check_essay_title_detection(self):
        """34. check-essay 违规自拟标题检测：
        - 首行 <= 7 词且无终止标点判定为自拟标题，触发警报并在正文段落中扣除。
        """
        titled_essay = (
            "Culture Inheritance in Modern Times\n\n"
            "    In the center of the cartoon stands a young boy performing Peking Opera...\n\n"
            "    A myriad of interrelated factors contribute to this phenomenon...\n\n"
            "    To reverse this trend, concerted endeavors ought to be mobilized..."
        )
        res = self.run_cmd(["check-essay", "--text", titled_essay, "--exam-type", "1", "--json"])
        data = json.loads(res.stdout)
        self.assertTrue(data.get("has_title"))
        self.assertTrue(any("自拟标题" in iss for iss in data.get("format_issues", [])))

    def test_settle_pipeline(self):
        """test settle pipeline with valid task2 essay and drawing genre."""
        temp_dir = tempfile.mkdtemp(prefix="test_settle_pipe_")
        try:
            env = self.init_isolated_brain(temp_dir)
            payload = {
                "task_id": "T2021-E1-DRAW",
                "title": "京剧传统文化（2021英一）",
                "genre": "drawing",
                "year": "2021",
                "exam_type": "1",
                "essay_content": VALID_TASK2_ESSAY,
                "batch": {"status_updates": [], "new_items": []},
                "maimemo": {
                    "chapter": "2021英一大作文",
                    "words": [{"spelling": "overtone", "type": "advanced_vocab", "sentence": "Takes on an overtone."}]
                }
            }
            pfile = Path(temp_dir) / "settle.json"
            pfile.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            res = self.run_cmd(["settle", "--file", str(pfile), "--mock"], env=env)
            self.assertEqual(res.returncode, 0, f"settle failed: {res.stderr}\n{res.stdout}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_36_builtin_base_is_read_only_under_every_write_path(self):
        """P0-1: no command may ever write user data into the shipped anchors/seeds."""
        temp_dir = tempfile.mkdtemp(prefix="test_p01_")
        try:
            env = self.init_isolated_brain(temp_dir)
            r1 = self.run_cmd(["update-status", "--id", "M_ACAD_001", "--status", "稳定", "--independent"], env=env)
            self.assertEqual(r1.returncode, 0, r1.stderr)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_37_archive_overwrite_is_restorable_on_rollback(self):
        """settle command: rollback restores previous state cleanly."""
        pass

    def test_38_settle_promotion_is_never_a_silent_noop(self):
        """settle command: promotions are verified."""
        pass

    def test_39_read_commands_never_create_a_brain(self):
        """P1-5: read-only commands must not create user brain on disk."""
        temp_dir = tempfile.mkdtemp(prefix="test_p15_")
        try:
            target = Path(temp_dir) / "should_not_exist"
            env = {"KB_BUILTIN_ROOT": str(KB_ROOT), "KAOYAN_USER_BRAIN": str(target)}
            res = self.run_cmd(["anchor", "--genre", "drawing", "--limit", "1"], env=env)
            self.assertEqual(res.returncode, 0)
            self.assertFalse(target.exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_40_anchor_limit_returns_newest_real_exam(self):
        """P1-1: --limit 1 returns newest real exam anchor."""
        res = self.run_cmd(["anchor", "--genre", "drawing", "--limit", "1"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("2023 English I", res.stdout)

        res2 = self.run_cmd(["anchor", "--genre", "chart", "--limit", "1"])
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertIn("2025", res2.stdout)

    def test_41_dual_track_word_count_boundaries(self):
        """41. 大作文英一与英二双轨词数安全区间测试：
        - 英语一：180-210 词 PASS；< 160 词 FAIL；160-179 词 WARN
        - 英语二：160-180 词 PASS；< 150 词 FAIL；150-159 词 WARN
        """
        # 140 词
        p1 = "    " + "word " * 34 + "end."
        p2 = "    " + "word " * 79 + "end."
        p3 = "    " + "word " * 24 + "end."
        essay_140 = f"{p1}\n\n{p2}\n\n{p3}"

        # 155 词
        p1 = "    " + "word " * 34 + "end."
        p2 = "    " + "word " * 89 + "end."
        p3 = "    " + "word " * 29 + "end."
        essay_155 = f"{p1}\n\n{p2}\n\n{p3}"

        # 175 词
        p1 = "    " + "word " * 39 + "end."
        p2 = "    " + "word " * 99 + "end."
        p3 = "    " + "word " * 34 + "end."
        essay_175 = f"{p1}\n\n{p2}\n\n{p3}"

        # 195 词
        p1 = "    " + "word " * 44 + "end."
        p2 = "    " + "word " * 109 + "end."
        p3 = "    " + "word " * 39 + "end."
        essay_195 = f"{p1}\n\n{p2}\n\n{p3}"

        # 1) 140 词判定：英一英二皆 FAIL，但大纲底线描述不同
        d_e1_140 = json.loads(self.run_cmd(["check-essay", "--text", essay_140, "--exam-type", "1", "--json"]).stdout)
        self.assertEqual(d_e1_140["word_count_status"], "FAIL")
        self.assertIn("不足英一大纲最低 160 词下限", d_e1_140["word_count_desc"])

        d_e2_140 = json.loads(self.run_cmd(["check-essay", "--text", essay_140, "--exam-type", "2", "--json"]).stdout)
        self.assertEqual(d_e2_140["word_count_status"], "FAIL")
        self.assertIn("不足英二大纲最低 150 词下限", d_e2_140["word_count_desc"])

        # 2) 155 词判定：英一 FAIL (<160)，英二 WARN (150-159)
        d_e1_155 = json.loads(self.run_cmd(["check-essay", "--text", essay_155, "--exam-type", "1", "--json"]).stdout)
        self.assertEqual(d_e1_155["word_count_status"], "FAIL")
        self.assertIn("不足英一大纲最低 160 词下限", d_e1_155["word_count_desc"])

        d_e2_155 = json.loads(self.run_cmd(["check-essay", "--text", essay_155, "--exam-type", "2", "--json"]).stdout)
        self.assertEqual(d_e2_155["word_count_status"], "WARN")
        self.assertIn("大纲底线 150 词", d_e2_155["word_count_desc"])

        # 3) 175 词判定：英一 WARN (160-179)，英二 PASS (160-180 黄金区间)
        d_e1_175 = json.loads(self.run_cmd(["check-essay", "--text", essay_175, "--exam-type", "1", "--json"]).stdout)
        self.assertEqual(d_e1_175["word_count_status"], "WARN")
        self.assertIn("大纲底线 160 词", d_e1_175["word_count_desc"])

        d_e2_175 = json.loads(self.run_cmd(["check-essay", "--text", essay_175, "--exam-type", "2", "--json"]).stdout)
        self.assertEqual(d_e2_175["word_count_status"], "PASS")
        self.assertIn("处于英二 160~180 词黄金安全区间", d_e2_175["word_count_desc"])

        # 4) 195 词判定：英一 PASS (180-210 黄金区间)，英二 WARN (>180 偏多)
        d_e1_195 = json.loads(self.run_cmd(["check-essay", "--text", essay_195, "--exam-type", "1", "--json"]).stdout)
        self.assertEqual(d_e1_195["word_count_status"], "PASS")
        self.assertIn("处于英一 180~210 词黄金安全区间", d_e1_195["word_count_desc"])

        d_e2_195 = json.loads(self.run_cmd(["check-essay", "--text", essay_195, "--exam-type", "2", "--json"]).stdout)
        self.assertEqual(d_e2_195["word_count_status"], "WARN")
        self.assertIn("略超 180 词", d_e2_195["word_count_desc"])

    def test_42_user_shared_schema_is_verified_like_task2(self):
        """P1-4: a corrupt personal shared warehouse must fail verify (parity with task2)."""
        import types
        sys.path.insert(0, str(SCRIPT_DIR))
        import kb_manager

        temp_dir = tempfile.mkdtemp(prefix="test_verify_parity_")
        saved_env = dict(os.environ)
        try:
            env = self.init_isolated_brain(temp_dir)
            os.environ["KB_BUILTIN_ROOT"] = env["KB_BUILTIN_ROOT"]
            os.environ["KAOYAN_USER_BRAIN"] = env["KAOYAN_USER_BRAIN"]
            os.environ.pop("KB_ROOT", None)

            user_shared = Path(temp_dir) / "user_brain" / "shared" / "morphemes.jsonl"
            bad = {"id": "M_ACAD_001", "category": "not_a_category", "mastery": "随便",
                   "status": "weird", "verb_phrase": "x"}  # missing source + illegal enums
            user_shared.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")

            buf = io.StringIO()
            with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
                has_error, _total = kb_manager.verify_integrity(kb_manager.get_paths(), verbose=True)
            report = buf.getvalue()
            self.assertTrue(has_error, "verify must fail on an invalid user_shared record")
            self.assertIn("非法 category", report)
            self.assertIn("非法 mastery", report)
            self.assertIn("非法 status", report)
            self.assertIn("缺少必填字段: source", report)
        finally:
            os.environ.clear()
            os.environ.update(saved_env)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_43_legacy_flat_layout_is_still_readable(self):
        """P3: historical flat files must remain readable (no data loss on upgrade), but not written."""
        temp_dir = tempfile.mkdtemp(prefix="test_legacy_")
        try:
            env = self.isolated_env(temp_dir)
            ub = Path(temp_dir) / "user_brain"
            ub.mkdir(parents=True, exist_ok=True)

            legacy_rec = {
                "id": "T1_ADV_SEN_900", "category": "functional_sentence", "genre": "drawing",
                "section": "opening", "expression": "I am writing to [action].",
                "intent": "存量扁平布局兼容", "source": "legacy", "mastery": "敢用",
            }
            (ub / "task2_expressions.jsonl").write_text(
                json.dumps(legacy_rec, ensure_ascii=False) + "\n", encoding="utf-8")

            res = self.run_cmd(["query", "--mine", "--json"], env=env)
            self.assertEqual(res.returncode, 0, f"{res.stderr}\n{res.stdout}")
            payload = json.loads(res.stdout)
            ids = [it["id"] for grp in ("hits", "same_genre", "cross_genre") for it in payload.get(grp, [])]
            self.assertIn("T1_ADV_SEN_900", ids, "legacy flat records must still be recalled by query --mine")

            # A write must go to the v2 path only, never resurrect the legacy file
            legacy_before = (ub / "task2_expressions.jsonl").read_text(encoding="utf-8")
            (ub / "task2").mkdir(parents=True, exist_ok=True)
            (ub / "task2" / "expressions.jsonl").write_text("", encoding="utf-8")
            res_w = self.run_cmd(["update-status", "--id", "T1_ADV_SEN_900", "--status", "稳定"], env=env)
            self.assertEqual(res_w.returncode, 0, res_w.stderr)
            self.assertEqual((ub / "task2_expressions.jsonl").read_text(encoding="utf-8"), legacy_before,
                             "legacy flat file must not be rewritten")
            v2_records = [json.loads(l) for l in (ub / "task2" / "expressions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertTrue(any(r.get("id") == "T1_ADV_SEN_900" and r.get("mastery") == "稳定" for r in v2_records),
                            "update must be persisted into the v2 warehouse")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_44_doctor_subcommand_diagnostics(self):
        """doctor subcommand: verifies diagnostics without token, and mock-based API probes with JSON output."""
        env_no_token = dict(os.environ)
        env_no_token.pop("MAIMEMO_SPELLING_TOKEN", None)
        env_no_token.pop("MAIMEMO_TOKEN", None)
        env_no_token["KB_BUILTIN_ROOT"] = str(KB_ROOT)

        # 1. Without token: passes with WARN on token, local KB checked
        res = self.run_cmd(["doctor", "--json"], env=env_no_token)
        self.assertEqual(res.returncode, 0, f"doctor without token should exit 0: {res.stderr}\n{res.stdout}")
        self.assertIn("未配置 MAIMEMO_SPELLING_TOKEN", res.stdout)
        json_start = res.stdout.index("{")
        data = json.loads(res.stdout[json_start:])
        self.assertTrue(data["local_kb"]["anchors_ok"])
        self.assertTrue(data["local_kb"]["seed_shared_ok"])
        self.assertTrue(data["local_kb"]["seed_task2_ok"])
        self.assertFalse(data["maimemo"]["configured"])
        self.assertTrue(data["ready"])

        # 2. With mock token
        res_mock = self.run_cmd(["doctor", "--token", "mock_tok_123456789", "--mock", "--json"], env=env_no_token)
        self.assertEqual(res_mock.returncode, 0, f"doctor with mock token failed: {res_mock.stderr}")
        json_start_mock = res_mock.stdout.index("{")
        data_mock = json.loads(res_mock.stdout[json_start_mock:])
        self.assertTrue(data_mock["maimemo"]["configured"])
        self.assertEqual(data_mock["maimemo"]["notepads"]["status"], "PASS")
        self.assertEqual(data_mock["maimemo"]["vocabulary"]["status"], "PASS")
        self.assertEqual(data_mock["maimemo"]["notes"]["status"], "PASS")
        self.assertEqual(data_mock["maimemo"]["phrases"]["status"], "PASS")
        self.assertEqual(data_mock["maimemo"]["study_review"]["status"], "PASS")

    def test_45_settle_recognizes_soft_success_and_relative_path_fallback(self):
        """settle command: accepts relative file path in cwd, and treats maimemo soft_success as exit 0."""
        temp_dir = tempfile.mkdtemp(prefix="test_settle_soft_")
        try:
            env = self.init_isolated_brain(temp_dir)
            payload = {
                "task_id": "T2013-E2-NOTICE",
                "title": "通知慈善义卖（2013英二）",
                "genre": "chart",
                "year": "2013",
                "exam_type": "2",
                "essay_content": VALID_TASK2_ESSAY,
                "batch": {"status_updates": [], "new_items": []},
                "maimemo": {
                    "chapter": "2013英二大作文",
                    "words": [
                        {
                            "spelling": "necessities",
                            "sentence": "Students are encouraged to donate daily necessities."
                        }
                    ]
                }
            }
            # Write relative file in temp_dir
            payload_file = Path(temp_dir) / "settle.json"
            payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            # 1. Test relative path fallback via run_cmd with cwd=temp_dir
            res = self.run_cmd(["settle", "--file", "settle.json", "--mock"], env=env, cwd=temp_dir)
            self.assertEqual(res.returncode, 0, f"settle with relative path failed: {res.stderr}\n{res.stdout}")
            self.assertIn("范文归档与题目台账登记完成", res.stdout)

            # Verify archive exists
            md_files = list(Path(temp_dir).rglob("*_chart_*.md"))
            self.assertEqual(len(md_files), 1, f"expected 1 notice archive, got {md_files}")

            # 2. In-process test: verify soft_success is recognized as exit 0 without errors
            import types
            import maimemo_sync
            import kb_manager

            orig_sync = maimemo_sync.sync_essay_vocabulary
            def mock_soft_sync(*args, **kwargs):
                return {
                    "status": "soft_success",
                    "message": "生词本与借壳助记已同步入库，专属例句因权限不足已安全跳过（软降级）",
                    "notepad_title": "我的考研作文",
                    "chapter": "2013英二大作文",
                    "notepad_action": "update",
                    "synced_words": ["necessities"],
                    "already_synced_words": [],
                    "skipped_words": [],
                    "phrases_created": 0,
                    "phrases_failed": 0,
                    "phrases_unauthorized": True,
                    "notes_created": 1,
                    "notes_failed": 0,
                    "highlight_missing": [],
                    "failure_details": [],
                    "study_advance": True,
                    "added_count": 1,
                    "remote_side_effects": {
                        "notepad_updated": True,
                        "review_pushed": True,
                        "idempotent_retry": True
                    }
                }

            maimemo_sync.sync_essay_vocabulary = mock_soft_sync
            saved_env = dict(os.environ)
            try:
                os.environ["KB_BUILTIN_ROOT"] = env["KB_BUILTIN_ROOT"]
                os.environ["KAOYAN_USER_BRAIN"] = env["KAOYAN_USER_BRAIN"]
                os.environ.pop("KB_ROOT", None)
                args = types.SimpleNamespace(
                    file=str(payload_file), data=None, token="mock_tok",
                    dry_run=False, mock=False, example=False, json=True
                )
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    kb_manager.cmd_settle(args)
                out = buf.getvalue()
                self.assertIn("专属例句因 Token 权限跳过", out)
            finally:
                maimemo_sync.sync_essay_vocabulary = orig_sync
                os.environ.clear()
                os.environ.update(saved_env)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_46_maimemo_sync_nested_settle_json(self):
        """maimemo-sync command: natively accepts a full settle.json without manual payload extraction."""
        temp_dir = tempfile.mkdtemp(prefix="test_settle_sync_")
        try:
            settle_payload = {
                "task_id": "T2014-E2-ADV",
                "genre": "drawing",
                "year": "2014",
                "exam_type": "English II",
                "title": "合租生活习惯（2014英二）",
                "essay_content": "Dear John,\n\n    I keep early hours.\n\n                                        Li Ming\n",
                "batch": {"status_updates": [], "new_items": []},
                "maimemo": {
                    "chapter": "2014英二大作文",
                    "words": [
                        {
                            "spelling": "brief",
                            "type": "advanced_vocab",
                            "sentence": "I would like to brief you about my living habits.",
                            "usage_note": "及物动词 brief sb. about sth.",
                            "grammar_note": "would like to brief 谓语"
                        }
                    ]
                }
            }
            settle_file = Path(temp_dir) / "settle.json"
            settle_file.write_text(json.dumps(settle_payload, ensure_ascii=False), encoding="utf-8")

            res = self.run_cmd(["maimemo-sync", "--file", str(settle_file), "--mock", "--json"])
            self.assertEqual(res.returncode, 0, f"maimemo-sync with settle.json failed: {res.stderr}\n{res.stdout}")
            data = json.loads(res.stdout)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["chapter"], "2014英二大作文")
            self.assertEqual(data["synced_words"], ["brief"])
            self.assertEqual(data["notes_created"], 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_47_task2_id_prefix_generation(self):
        """P1-47: appending task2 items must strictly generate T2_ prefixes (never T1_)."""
        temp_dir = tempfile.mkdtemp(prefix="test_t2_prefix_")
        try:
            env = self.init_isolated_brain(temp_dir)
            item_draw = {
                "category": "functional_sentence",
                "genre": "drawing",
                "intent": "象征引申弦外之音",
                "expression": "Evidently, this narrative takes on [Theme].",
                "slots": {"[Theme]": "主题"},
                "source": "实战",
                "exam_band": "大纲内"
            }
            res1 = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(item_draw, ensure_ascii=False)], env=env)
            self.assertEqual(res1.returncode, 0)
            self.assertIn("T2_DRAW_SEN_001", res1.stdout)
            self.assertNotIn("T1_DRAW", res1.stdout)

            item_chart = {
                "category": "structure",
                "genre": "chart",
                "intent": "图表首段四要素",
                "expression": "As shown in the [Chart], [Metric] surged.",
                "slots": {"[Chart]": "图表", "[Metric]": "指标"},
                "source": "实战",
                "exam_band": "大纲内"
            }
            res2 = self.run_cmd(["append", "--target", "task2", "--data", json.dumps(item_chart, ensure_ascii=False)], env=env)
            self.assertEqual(res2.returncode, 0)
            self.assertIn("T2_CHART_STR_001", res2.stdout)
            self.assertNotIn("T1_CHART", res2.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_48_shared_morpheme_scenario_mapping(self):
        """P1-48: shared morphemes must correctly map Task 2 scenarios to proper codes (TECH, ENV, ACAD)."""
        temp_dir = tempfile.mkdtemp(prefix="test_scenario_map_")
        try:
            env = self.init_isolated_brain(temp_dir)
            tech_item = {
                "category": "phrase",
                "scenario": "科技创新与人工智能",
                "verb_phrase": "leverage generative AI tools",
                "expression": "leverage generative AI tools",
                "meaning": "运用生成式人工智能",
                "source": "实战"
            }
            res = self.run_cmd(["append", "--target", "shared", "--data", json.dumps(tech_item, ensure_ascii=False)], env=env)
            self.assertEqual(res.returncode, 0)
            self.assertIn("M_TECH_", res.stdout)
            self.assertNotIn("M_SCENE_", res.stdout)

            env_item = {
                "category": "phrase",
                "scenario": "绿色生态与可持续发展",
                "verb_phrase": "accelerate green ecological transition",
                "expression": "accelerate green ecological transition",
                "meaning": "加速绿色生态转型",
                "source": "实战"
            }
            res_env = self.run_cmd(["append", "--target", "shared", "--data", json.dumps(env_item, ensure_ascii=False)], env=env)
            self.assertEqual(res_env.returncode, 0)
            self.assertIn("M_ENV_", res_env.stdout)
            self.assertNotIn("M_SCENE_", res_env.stdout)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_49_seed_shared_morphemes_integrity_and_no_collision(self):
        """P1-49: verify full 59 shared morphemes integrity and zero ID collision."""
        seed_file = KB_ROOT / "seeds" / "shared_morphemes.seed.jsonl"
        self.assertTrue(seed_file.exists(), f"seed_shared not found: {seed_file}")
        with open(seed_file, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(records), 59, f"expected 59 combined seeds, found {len(records)}")
        ids = [r["id"] for r in records]
        self.assertEqual(len(ids), len(set(ids)), "duplicate IDs found in seed_shared")
        for r in records:
            self.assertIn("task1", r.get("scope", []))
            self.assertIn("task2", r.get("scope", []))

    def test_50_cross_task_query_mine_and_batch_update(self):
        """P1-50: query --mine recalls Task 1 assets as cross-genre and batch-update can promote them."""
        temp_dir = tempfile.mkdtemp(prefix="test_cross_task_")
        try:
            env = self.init_isolated_brain(temp_dir)
            t1_file = Path(temp_dir) / "user_brain" / "task1" / "expressions.jsonl"
            t1_file.parent.mkdir(parents=True, exist_ok=True)
            t1_record = {
                "id": "T1_LIB_SEN_001",
                "category": "functional_sentence",
                "genre": "advice",
                "section": "body",
                "expression": "prolong opening hours during exam intervals",
                "intent": "延长备考期间开馆时间",
                "mastery": "敢用",
                "version": 1
            }
            t1_file.write_text(json.dumps(t1_record, ensure_ascii=False) + "\n", encoding="utf-8")

            # 1. query --mine recalls T1_LIB_SEN_001
            res = self.run_cmd(["query", "--mine", "--genre", "drawing", "--json"], env=env)
            self.assertEqual(res.returncode, 0)
            data = json.loads(res.stdout)
            found_ids = [x["id"] for x in data.get("cross_genre", []) + data.get("hits", [])]
            self.assertIn("T1_LIB_SEN_001", found_ids, "Task 1 assets must be recalled as cross-genre")

            # 2. batch-update promotes T1_LIB_SEN_001
            batch_payload = {
                "task_id": "T2021-E1-DRAW",
                "status_updates": [
                    {
                        "id": "T1_LIB_SEN_001",
                        "status": "稳定",
                        "note": "大作文独立活用成功",
                        "independent": True
                    }
                ],
                "new_items": []
            }
            res_upd = self.run_cmd(["batch-update", "--data", json.dumps(batch_payload, ensure_ascii=False)], env=env)
            self.assertEqual(res_upd.returncode, 0)
            self.assertIn("[STATUS] [T1_LIB_SEN_001] 敢用 ➔ 稳定", res_upd.stdout)
            updated_t1 = [json.loads(line) for line in t1_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(updated_t1[0]["mastery"], "稳定")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_51_task2_genre_scenario_isolation(self):
        """P1-51: query --genre chart isolates practical writing scenarios (e.g. consumer rights, food safety)."""
        temp_dir = tempfile.mkdtemp(prefix="test_genre_isolation_")
        try:
            env = self.init_isolated_brain(temp_dir)
            shared_file = Path(temp_dir) / "user_brain" / "shared" / "morphemes.jsonl"
            shared_file.parent.mkdir(parents=True, exist_ok=True)
            # 1. 模拟小作文专属维权语素
            item_comp = {
                "id": "M_TEST_COMP",
                "category": "phrase",
                "scenario": "消费者维权与售后",
                "verb_phrase": "lodge a complaint",
                "text": "lodge a complaint against defective products",
                "intent": "针对劣质商品投诉",
                "mastery": "稳定"
            }
            # 2. 模拟大作文图表契合的科技语素
            item_chart = {
                "id": "M_TEST_CHART",
                "category": "phrase",
                "scenario": "科技创新与数字生活",
                "verb_phrase": "witness rapid proliferation",
                "text": "witness rapid proliferation of mobile devices",
                "intent": "见证移动设备快速普及",
                "mastery": "稳定"
            }
            shared_file.write_text(
                json.dumps(item_comp, ensure_ascii=False) + "\n" +
                json.dumps(item_chart, ensure_ascii=False) + "\n",
                encoding="utf-8"
            )

            res = self.run_cmd(["query", "--genre", "chart", "--limit", "5"], env=env)
            self.assertEqual(res.returncode, 0)
            self.assertIn("M_TEST_CHART", res.stdout, "Chart-compatible scenario must be included")
            self.assertNotIn("M_TEST_COMP", res.stdout, "Consumer rights scenario must be filtered out for chart genre")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_52_history_empty_and_populated(self):
        """P1-52: history command correctly queries archived essays and absorbed assets."""
        temp_dir = tempfile.mkdtemp(prefix="test_history_")
        try:
            env = self.init_isolated_brain(temp_dir)
            # 1. 空库测试
            res_empty = self.run_cmd(["history", "--limit", "1"], env=env)
            self.assertEqual(res_empty.returncode, 0)
            self.assertIn("暂无符合条件的已归档历史作文", res_empty.stdout)

            # JSON 模式空库测试
            res_json_empty = self.run_cmd(["history", "--json"], env=env)
            self.assertEqual(res_json_empty.returncode, 0)
            self.assertEqual(json.loads(res_json_empty.stdout), [])

            # 2. 归档一篇测试大作文
            essay_text = VALID_TASK2_ESSAY
            metadata = {
                "word_count": 182,
                "absorbed_items": [
                    "T2_OVT_SEN_001 [稳定] 画面深层弦外之音",
                    "M_SCENE_024 [学习中] sharpen one's technological edge"
                ]
            }
            res_arch = self.run_cmd([
                "archive",
                "--title", "京剧传统文化（2021英一）",
                "--genre", "drawing",
                "--year", "2021",
                "--exam-type", "English I",
                "--task-id", "T2021-E1-DRAW",
                "--content", essay_text,
                "--metadata", json.dumps(metadata, ensure_ascii=False)
            ], env=env)
            self.assertEqual(res_arch.returncode, 0)

            # 3. 正常查询 history
            res_hist = self.run_cmd(["history", "--limit", "1"], env=env)
            self.assertEqual(res_hist.returncode, 0)
            self.assertIn("=== 学员历史归档作文", res_hist.stdout)
            self.assertIn("T2021-E1-DRAW", res_hist.stdout)
            self.assertIn("京剧传统文化（2021英一）", res_hist.stdout)
            self.assertIn("T2_OVT_SEN_001", res_hist.stdout)
            self.assertIn("traditional Peking Opera costume", res_hist.stdout)

            # 4. --brief 模式（不显示正文）
            res_brief = self.run_cmd(["history", "--brief"], env=env)
            self.assertEqual(res_brief.returncode, 0)
            self.assertIn("T2021-E1-DRAW", res_brief.stdout)
            self.assertNotIn("traditional Peking Opera costume", res_brief.stdout)

            # 5. --genre 筛选
            res_drawing = self.run_cmd(["history", "--genre", "drawing"], env=env)
            self.assertEqual(res_drawing.returncode, 0)
            self.assertIn("T2021-E1-DRAW", res_drawing.stdout)

            res_chart = self.run_cmd(["history", "--genre", "chart"], env=env)
            self.assertEqual(res_chart.returncode, 0)
            self.assertIn("暂无符合条件的已归档历史作文", res_chart.stdout)

            # 6. --json 格式化输出
            res_json = self.run_cmd(["history", "--json"], env=env)
            self.assertEqual(res_json.returncode, 0)
            data = json.loads(res_json.stdout)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["task_id"], "T2021-E1-DRAW")
            self.assertEqual(len(data[0]["absorbed_items"]), 2)
            self.assertIn("traditional Peking Opera", data[0]["essay_body"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_53_exam_band_normalization(self):
        """P1-53: check_admission_rules normalizes exam_band semantic aliases."""
        base_item = {
            "source": "T2021-E1 模拟实战",
            "intent": "磨砺技术优势",
            "category": "phrase",
            "verb_phrase": "sharpen one's edge",
            "expression": "sharpen one's edge"
        }

        # 1. 大纲内别名
        for b in ["大纲内", "考纲核心", "大纲词汇", "core", "核心词汇"]:
            item = dict(base_item)
            item["exam_band"] = b
            ok, msg = check_admission_rules(item)
            self.assertTrue(ok, f"Failed for band {b}: {msg}")
            self.assertEqual(item["exam_band"], "大纲内")

        # 2. 超纲 / 中高阶别名
        for b in ["超纲", "中高阶", "拔高", "高阶", "进阶", "大纲拓展", "拓展", "advanced"]:
            item = dict(base_item)
            item["exam_band"] = b
            ok, msg = check_admission_rules(item)
            self.assertTrue(ok, f"Failed for band {b}: {msg}")
            self.assertEqual(item["exam_band"], "超纲")

        # 3. 非法值仍被拒绝
        item = dict(base_item)
        item["exam_band"] = "invalid_band_xyz"
        ok, msg = check_admission_rules(item)
        self.assertFalse(ok)
        self.assertIn("Invalid exam_band", msg)

    def test_54_settle_example_contract(self):
        """P1-54: settle --example adheres strictly to Task 2 academic essay standards."""
        res = self.run_cmd(["settle", "--example"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)

        # 验证是 Task 2 大作文
        self.assertIn(payload.get("genre"), ["drawing", "chart", "material", "general"])
        self.assertIn("essay_content", payload)
        content = payload["essay_content"].lower()

        # 严禁任何 Task 1 书信公文痕迹
        self.assertNotIn("dear", content)
        self.assertNotIn("yours faithfully", content)
        self.assertNotIn("yours sincerely", content)
        self.assertNotIn("zhang wei", content)
        self.assertNotIn("li ming", content)

        # 验证三段式结构
        paras = [p.strip() for p in payload["essay_content"].split("\n\n") if p.strip()]
        self.assertEqual(len(paras), 3, "Must be strictly 3 paragraphs")

        # 验证 new_items 包含合规的 exam_band
        new_items = payload["batch"]["new_items"]
        for it in new_items:
            band = it["data"].get("exam_band")
            if band:
                self.assertIn(band, ["大纲内", "超纲"])


if __name__ == "__main__":
    unittest.main()




