#!/usr/bin/env python3
"""
Unit Test Suite for AI-First Workspace (`scripts/audit-workspace.py`)
---------------------------------------------------------------------
Zero external dependencies (uses Python built-in `unittest`).
Run with:
    python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit-workspace.py"

# Dynamically load scripts/audit-workspace.py as a module
spec = importlib.util.spec_from_file_location("audit_workspace", SCRIPT_PATH)
audit_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_mod)


class TestTokenEstimator(unittest.TestCase):
    """單元測試 1：驗證 AI 設定檔 Token 估算器 (ASCII 與繁體中文 CJK 混合計費)"""

    def test_ascii_and_cjk_token_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "CLAUDE.md"
            # 400 ASCII chars (~100 tokens) + 100 CJK chars (~130 tokens) = ~230 tokens
            p.write_text("A" * 400 + "繁" * 100, encoding="utf-8")
            tokens = audit_mod.estimate_file_tokens(p)
            self.assertEqual(tokens, 230)

    def test_missing_or_empty_file_returns_safe_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nonexistent.md"
            self.assertEqual(audit_mod.estimate_file_tokens(missing), 0)

            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            self.assertEqual(audit_mod.estimate_file_tokens(empty), 1)


class TestKebabCaseConverter(unittest.TestCase):
    """單元測試 2：驗證目錄名稱全小寫 kebab-case 標準化轉換"""

    def test_spaces_underscores_and_camelcase(self):
        self.assertEqual(audit_mod.to_kebab_case("AI Study Notes"), "ai-study-notes")
        self.assertEqual(audit_mod.to_kebab_case("render_work_v2"), "render-work-v2")
        self.assertEqual(audit_mod.to_kebab_case("OldWorkspace"), "old-workspace")
        self.assertEqual(audit_mod.to_kebab_case("OldWorkspace/MyAppServer"), "my-app-server")
        # 驗證外部使用者的常見中文資料夾名稱能自動轉譯為乾淨英文 kebab-case
        self.assertEqual(audit_mod.to_kebab_case("學習筆記"), "study-notes")
        self.assertEqual(audit_mod.to_kebab_case("2024 備份"), "2024-backup")


class TestFolderClassifier(unittest.TestCase):
    """單元測試 3：驗證五層聯邦架構與 10 大分類規則（中英雙語標籤 + 跨平台路徑 + 邊界防誤判）"""

    def test_all_ten_architecture_categories(self):
        cases = [
            ("AI-Models", "ai-models", "~/ai-models/shared-weights/"),
            ("claude-skills-hub", "agent-hub", "~/agent-hub/skills/claude-skills-hub/"),
            ("Windows_Backup_2024", "archives", "~/archives/windows-backup-2024/"),
            ("agent-workspace-daily", "agent-lab", "~/agent-lab/workspaces/agent-workspace-daily/"),
            ("OldWorkspace/AI Study Notes", "knowledge", "~/knowledge/study/ai-study-notes/"),
            ("OldWorkspace/voice-kit", "projects", "~/projects/media-studio/tools/voice-kit/"),
            ("render_work/ep01_intro", "episodes", "~/projects/media-studio/episodes/ep01-intro/"),
            ("OldWorkspace/custom-agent-harness", "projects", "~/projects/agent-ecosystem/custom-agent-harness/"),
            ("OldWorkspace/ComfyUI", "projects", "~/projects/media-ai/comfy-ui/"),
            ("OldWorkspace/backend-service", "projects", "~/projects/engineering/backend-service/"),
        ]
        for folder_name, expected_layer, expected_unix_target in cases:
            with self.subTest(folder=folder_name):
                res = audit_mod.classify_folder(folder_name, is_git=True, markers=["package.json"])
                self.assertEqual(res["layer"], expected_layer)
                self.assertEqual(res["target_unix"], expected_unix_target)
                self.assertTrue(res["target_win"].startswith("%USERPROFILE%\\"))
                self.assertTrue(len(res["tree_group_zh"]) > 0 and len(res["tree_group_en"]) > 0)
                self.assertTrue(len(res["reason_zh"]) > 0 and len(res["reason_en"]) > 0)

    def test_oldworkspace_container_and_old_substrings_not_misclassified(self):
        """驗證 OldWorkspace/ 容器與含 'old' 子字串之正常單字 (scaffold, folder) 不會被誤判為冷封存 archives"""
        r_voice = audit_mod.classify_folder("OldWorkspace/voice-kit", True, ["pyproject.toml"])
        self.assertEqual(r_voice["layer"], "projects")
        self.assertEqual(r_voice["target_unix"], "~/projects/media-studio/tools/voice-kit/")

        r_notes = audit_mod.classify_folder("OldWorkspace/AI Study Notes", False, [])
        self.assertEqual(r_notes["layer"], "knowledge")
        self.assertEqual(r_notes["target_unix"], "~/knowledge/study/ai-study-notes/")

        r_scaffold = audit_mod.classify_folder("OldWorkspace/scaffold-engine", True, ["package.json"])
        self.assertEqual(r_scaffold["layer"], "projects")
        self.assertNotEqual(r_scaffold["layer"], "archives")

        # 驗證多個 skills 資料夾擁有獨立子路徑，搬移時不會互相覆蓋
        s1 = audit_mod.classify_folder("claude-skills", True, [])
        s2 = audit_mod.classify_folder("cursor-skills", True, [])
        self.assertNotEqual(s1["target_unix"], s2["target_unix"])

        # 驗證 Windows 反斜線路徑 (OldWorkspace\voice-kit, render_work\ep01) 能被正確正規化與分類
        win_voice = audit_mod.classify_folder("OldWorkspace\\voice-kit", True, [])
        self.assertEqual(win_voice["target_unix"], "~/projects/media-studio/tools/voice-kit/")
        win_ep = audit_mod.classify_folder("render_work\\ep01_intro", False, [])
        self.assertEqual(win_ep["layer"], "episodes")
        self.assertEqual(win_ep["target_unix"], "~/projects/media-studio/episodes/ep01-intro/")


class TestDirectoryScannerAndMetrics(unittest.TestCase):
    """單元測試 4：驗證真實目錄掃描引擎（Token 帳單明細 + node_modules/.venv/.cache 空間精算）"""

    def test_scan_directory_unroll_and_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            # 1. 重度開發專案 (含 CLAUDE.md, AGENTS.md, .claude/, node_modules)
            app_dir = home / "OldWorkspace" / "heavy-monolith"
            (app_dir / ".claude" / "agents").mkdir(parents=True)
            (app_dir / "node_modules" / "dep").mkdir(parents=True)
            (app_dir / ".git").mkdir(parents=True)
            (app_dir / "package.json").write_text("{}", encoding="utf-8")
            (app_dir / "CLAUDE.md").write_text("Rule " * 1200, encoding="utf-8")
            (app_dir / "AGENTS.md").write_text("Contract " * 800, encoding="utf-8")
            (app_dir / ".claude" / "agents" / "reviewer.md").write_text("Review " * 400, encoding="utf-8")
            (app_dir / "node_modules" / "dep" / "lib.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2.0 MB

            # 2. 單集渲染工作區 (含 dist/.cache)
            ep_dir = home / "render_work" / "ep01_rag"
            (ep_dir / "dist" / ".cache").mkdir(parents=True)
            (ep_dir / "dist" / ".cache" / "frames.bin").write_bytes(b"y" * (1536 * 1024))  # 1.5 MB

            results = audit_mod.scan_directory(home)
            self.assertEqual(len(results), 2)
            by_name = {r["name"]: r for r in results}

            monolith = by_name["OldWorkspace/heavy-monolith"]
            self.assertTrue(monolith["is_git"])
            self.assertGreater(monolith["total_tokens"], 3000)
            self.assertEqual(monolith["reclaimable_mb"], 2.0)
            ai_file_names = {f["file"] for f in monolith["ai_files"]}
            self.assertIn("CLAUDE.md", ai_file_names)
            self.assertIn("AGENTS.md", ai_file_names)

            episode = by_name["render_work/ep01_rag"]
            self.assertEqual(episode["layer"], "episodes")
            self.assertEqual(episode["reclaimable_mb"], 1.5)

    def test_scan_directory_skips_os_dirs_and_existing_7_top_layers(self):
        """驗證真實掃描會自動跳過 Desktop/Documents/Downloads 與已建立的 7 大頂層目錄"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for skip_name in ("Desktop", "Documents", "Downloads", "knowledge", "projects", "ai-models", "agent-hub", "agent-lab", "outputs", "archives"):
                (home / skip_name).mkdir()
            (home / "my-legacy-project").mkdir()

            results = audit_mod.scan_directory(home)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["name"], "my-legacy-project")

    def test_universal_containers_and_structural_heuristic_unrolling(self):
        """驗證外部開發者常用的 ~/workspace、~/dev 以及內含多個子專案的自訂容器皆能自動展開"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            # 1. 常見通用容器名 ~/workspace/
            (home / "workspace" / "web-frontend" / ".git").mkdir(parents=True)
            (home / "workspace" / "api-server" / ".git").mkdir(parents=True)

            # 2. 自訂名稱容器 ~/2025_Company_Stuff/ (本身無 .git，但內含 >=2 個 git 子專案)
            (home / "2025_Company_Stuff" / "service-a" / ".git").mkdir(parents=True)
            (home / "2025_Company_Stuff" / "service-b" / ".git").mkdir(parents=True)

            results = audit_mod.scan_directory(home)
            names = {r["name"] for r in results}
            self.assertEqual(
                names,
                {
                    "workspace/web-frontend",
                    "workspace/api-server",
                    "2025_Company_Stuff/service-a",
                    "2025_Company_Stuff/service-b",
                }
            )

    def test_content_based_heuristics_for_vaults_models_and_outputs(self):
        """驗證不靠資料夾名字、純靠『內部檔案特徵 (Content Heuristics)』精準識別知識庫、模型庫與影音成品庫"""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            # 1. 名字叫 ~/my-random-box，但裡面有 .obsidian 與 .md 筆記 -> 應識別為 knowledge
            box = home / "my-random-box"
            (box / ".obsidian").mkdir(parents=True)
            (box / "idea.md").write_text("# My Idea", encoding="utf-8")

            # 2. 名字叫 ~/custom-blobs，但裡面有 .safetensors 模型權重 -> 應識別為 ai-models
            blobs = home / "custom-blobs"
            blobs.mkdir(parents=True)
            (blobs / "flux-dev.safetensors").write_bytes(b"weights")

            # 3. 名字叫 ~/master-renders，但裡面全是 .mp4 / .wav 成品且無程式碼 -> 應識別為 outputs
            renders = home / "master-renders"
            renders.mkdir(parents=True)
            (renders / "ep01.mp4").write_bytes(b"video")

            results = {r["name"]: r for r in audit_mod.scan_directory(home)}
            self.assertEqual(results["my-random-box"]["layer"], "knowledge")
            self.assertEqual(results["custom-blobs"]["layer"], "ai-models")
            self.assertEqual(results["master-renders"]["layer"], "outputs")


class TestAntiDumpRepoPurity(unittest.TestCase):
    """單元測試 5：驗證「防混放檢查 (Anti-Dump / CWD Dumping)」攔截與一鍵分流後純淨度"""

    def test_detect_and_resolve_all_six_cwd_dumping_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "ai-first-workspace"
            repo.mkdir(parents=True)
            (repo / "README.md").write_text("# Clean Spec Repo", encoding="utf-8")

            # 模擬 AI 協作時誤塞入當前專案的 6 種不相干支線產物
            (repo / ".local").mkdir()
            (repo / ".local" / "scan.json").write_text("{}", encoding="utf-8")
            (repo / "dry-run-report.html").write_text("<html></html>", encoding="utf-8")
            (repo / "sidecars").mkdir()
            (repo / "model-7b.gguf").write_bytes(b"weights")
            (repo / "episode-final.mp4").write_bytes(b"video")
            (repo / "personal-notes.md").write_text("notes", encoding="utf-8")

            # 步驟 A：偵測混放
            issues = audit_mod.check_repo_purity(repo)
            self.assertEqual(len(issues), 6)
            layers = {i["layer"] for i in issues}
            self.assertEqual(
                layers,
                {"agent-lab", "global-ide-config", "ai-models", "outputs", "knowledge"}
            )

            # 步驟 B：模擬將這 6 項混放產物分流移出後，再次驗證應為 100% 純淨 (0 issues)
            shutil.rmtree(repo / ".local")
            (repo / "dry-run-report.html").unlink()
            shutil.rmtree(repo / "sidecars")
            (repo / "model-7b.gguf").unlink()
            (repo / "episode-final.mp4").unlink()
            (repo / "personal-notes.md").unlink()

            clean_issues = audit_mod.check_repo_purity(repo)
            self.assertEqual(clean_issues, [])

    def test_purity_check_works_on_arbitrary_project_names(self):
        """驗證一般業務專案 (非 ai-first-workspace 名稱) 也能攔截 sidecars/ 與帶空白路徑"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "my-saas-web-app"
            repo.mkdir(parents=True)
            (repo / "sidecars").mkdir()
            (repo / "llama3.safetensors").write_bytes(b"w")
            issues = audit_mod.check_repo_purity(repo)
            self.assertEqual(len(issues), 2)
            for iss in issues:
                # 驗證生成的搬移指令有加上雙引號保護路徑
                self.assertIn('"', iss["cmd"])


class TestHtmlSimulatorAndJavaScriptRuntime(unittest.TestCase):
    """單元測試 6：驗證雙語 HTML 模擬器之 DOM ID 對齊、JS 語法與 Node.js 全按鈕執行期互動"""

    def test_generated_html_dom_and_js_interactions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "sim.html"
            items = audit_mod.build_generic_demo_items()
            audit_mod.generate_html_report(items, out_html, default_lang="zh")

            content = out_html.read_text(encoding="utf-8")

            # 1. 確保無殘留的 Python f-string 雙大括號
            self.assertNotIn("{{", content)
            self.assertNotIn("}}", content)

            # 2. 確保所有 getElementById 引用的 ID 在 HTML 中皆有定義
            ref_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", content))
            def_ids = set(re.findall(r"id=['\"]([^'\"]+)['\"]", content))
            self.assertEqual(ref_ids - def_ids, set())

            # 3. 透過 Node.js 執行真實語法與全互動模擬點擊
            scripts = re.findall(r"<script>(.*?)</script>", content, flags=re.DOTALL)
            self.assertEqual(len(scripts), 1)

            js_harness = (
                """
                const elements = {};
                global.document = {
                  getElementById: (id) => {
                    if (!elements[id]) {
                      elements[id] = {
                        textContent: '', innerHTML: '', className: '', placeholder: '', value: '',
                        classList: { add: () => {}, remove: () => {} }
                      };
                    }
                    return elements[id];
                  }
                };
                """
                + scripts[0]
                + """
                setLang('en');
                if (!elements['ui-title'].textContent.includes('Folders')) throw new Error('EN switch failed');
                setLang('zh');
                if (!elements['ui-title'].textContent.includes('目錄')) throw new Error('ZH switch failed');
                setOS('win');
                if (!elements['d-cmd'].textContent.includes('Junction')) throw new Error('Win cmd failed');
                setOS('unix');
                if (!elements['d-cmd'].textContent.includes('ln -s')) throw new Error('Unix cmd failed');
                setHeatFilter('token');
                setHeatFilter('disk');
                setHeatFilter('all');
                setViewMode('before-list');
                setViewMode('episode-demo');
                setViewMode('rollback-script');
                if (!elements['rb-undo-code'].textContent.includes('mv ')) throw new Error('Rollback script failed');
                // 驗證全部 11 個 Demo 目錄皆完整出現在搬移腳本中 (未被 .slice(0, 8) 截斷)
                if (!elements['rb-apply-code'].textContent.includes('Windows_Backup_2024')) {
                  throw new Error('Rollback script truncated items beyond 8!');
                }
                setViewMode('after-tree');
                onSearchInput('voice');
                onSearchInput('nonexistent_xyz_123');
                onSearchInput('');
                console.log('UNIT_TEST_JS_RUNTIME_OK');
                """
            )
            js_file = Path(tmp) / "runtime_test.js"
            js_file.write_text(js_harness, encoding="utf-8")
            proc = subprocess.run(["node", str(js_file)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=f"Node runtime failed: {proc.stderr}")
            self.assertIn("UNIT_TEST_JS_RUNTIME_OK", proc.stdout)

    def test_unix_commands_never_put_tilde_inside_double_quotes(self):
        """回歸測試：bash 不會展開雙引號內的 ~，產生的 Unix 指令必須改用 $HOME（否則會在 CWD 建出名為 ~ 的資料夾）"""
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "sim.html"
            items = audit_mod.build_generic_demo_items()
            audit_mod.generate_html_report(items, out_html, default_lang="en")
            scripts = re.findall(r"<script>(.*?)</script>", out_html.read_text(encoding="utf-8"), flags=re.DOTALL)

            js_harness = (
                """
                const elements = {};
                global.document = {
                  getElementById: (id) => {
                    if (!elements[id]) {
                      elements[id] = {
                        textContent: '', innerHTML: '', className: '', placeholder: '', value: '',
                        classList: { add: () => {}, remove: () => {} }
                      };
                    }
                    return elements[id];
                  }
                };
                """
                + scripts[0]
                + """
                setOS('unix');
                setViewMode('after-tree');
                const single = elements['d-cmd'].textContent;
                setViewMode('rollback-script');
                const blocks = { single, apply: elements['rb-apply-code'].textContent, undo: elements['rb-undo-code'].textContent };
                for (const [name, text] of Object.entries(blocks)) {
                  if (text.includes('"~/')) throw new Error(name + ' contains quoted tilde: ' + text);
                  if (!text.includes('"$HOME/')) throw new Error(name + ' does not use $HOME: ' + text);
                }
                console.log('TILDE_QUOTING_OK');
                """
            )
            js_file = Path(tmp) / "tilde_test.js"
            js_file.write_text(js_harness, encoding="utf-8")
            proc = subprocess.run(["node", str(js_file)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=f"Node runtime failed: {proc.stderr}")
            self.assertIn("TILDE_QUOTING_OK", proc.stdout)

    def test_xss_script_breakout_quotes_and_empty_items_resilience(self):
        """驗證惡意/特殊字元資料夾名稱 (</script>, 單雙引號, 反斜線, HTML 標籤) 與空陣列 [] 之安全性"""
        with tempfile.TemporaryDirectory() as tmp:
            # 1. 空陣列 [] 測試
            empty_html = Path(tmp) / "empty.html"
            audit_mod.generate_html_report([], empty_html, default_lang="en")
            self.assertTrue(empty_html.exists())

            # 2. 含 </script>、單雙引號與 HTML 注入標籤的極端項目測試
            weird_name = """OldWorkspace/It's "quoted" \\path </script><img src=x onerror=alert(1)>"""
            cls = audit_mod.classify_folder(weird_name, False, [])
            weird_item = {
                "name": weird_name,
                "is_git": False,
                "has_space_or_cjk": True,
                "markers": [],
                **cls,
                "total_tokens": 500,
                "tree_tokens": 18,
                "ai_files": [],
                "reclaimable_mb": 0.0,
                "reclaimable_dirs": []
            }
            xss_html = Path(tmp) / "xss.html"
            audit_mod.generate_html_report([weird_item], xss_html, default_lang="zh")
            raw_html = xss_html.read_text(encoding="utf-8")

            # 確保 JSON 內的 </script> 已被安全跳脫為 <\/script>，不會截斷 HTML <script> 區塊
            scripts = re.findall(r"<script>(.*?)</script>", raw_html, flags=re.DOTALL)
            self.assertEqual(len(scripts), 1)

            js_test = (
                """
                const elements = {};
                global.document = {
                  getElementById: (id) => {
                    if (!elements[id]) {
                      elements[id] = {
                        textContent: '', innerHTML: '', className: '', placeholder: '', value: '',
                        classList: { add: () => {}, remove: () => {} }
                      };
                    }
                    return elements[id];
                  }
                };
                """
                + scripts[0]
                + """
                const encoded = encodeURIComponent(ALL_ITEMS[0].name);
                selectByEncoded(encoded);
                if (elements['left-pane'].innerHTML.includes('<img src=x')) {
                  throw new Error('Unescaped HTML tag injected into innerHTML!');
                }
                console.log('XSS_AND_QUOTES_SAFE_OK');
                """
            )
            js_path = Path(tmp) / "xss_runtime.js"
            js_path.write_text(js_test, encoding="utf-8")
            proc = subprocess.run(["node", str(js_path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=f"XSS/Quote test failed: {proc.stderr}")
            self.assertIn("XSS_AND_QUOTES_SAFE_OK", proc.stdout)


class TestZeroDowntimeSymlinkAndRollback(unittest.TestCase):
    """單元測試 7：驗證「搬移實體 + 原位留 Symlink 不斷鏈」與「一鍵無損還原後悔藥」"""

    def test_move_with_symlink_and_lossless_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_dir = root / "OldWorkspace" / "voice-kit"
            legacy_dir.mkdir(parents=True)
            (legacy_dir / "run.py").write_text("print('OK_FROM_VOICE_KIT')\n", encoding="utf-8")

            new_dir = root / "projects" / "media-studio" / "tools" / "voice-kit"
            new_dir.parent.mkdir(parents=True, exist_ok=True)

            # 1. 執行搬移 + 原位留 Symlink (Unix) 或 Directory Junction (Windows 免管理員權限)
            shutil.move(str(legacy_dir), str(new_dir))
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(legacy_dir), str(new_dir)], check=True, capture_output=True)
            else:
                os.symlink(str(new_dir), str(legacy_dir))
                self.assertTrue(legacy_dir.is_symlink())
            self.assertTrue(new_dir.is_dir())

            # 驗證舊路徑腳本呼叫 100% 正常運作
            r1 = subprocess.run([sys.executable, str(legacy_dir / "run.py")], capture_output=True, text=True)
            self.assertEqual(r1.returncode, 0)
            self.assertIn("OK_FROM_VOICE_KIT", r1.stdout)

            # 2. 執行一鍵無損還原 (Rollback)
            if os.name == "nt":
                os.rmdir(str(legacy_dir))
            else:
                os.unlink(str(legacy_dir))
            shutil.move(str(new_dir), str(legacy_dir))
            self.assertFalse(legacy_dir.is_symlink())
            self.assertTrue(legacy_dir.is_dir())

            r2 = subprocess.run([sys.executable, str(legacy_dir / "run.py")], capture_output=True, text=True)
            self.assertEqual(r2.returncode, 0)
            self.assertIn("OK_FROM_VOICE_KIT", r2.stdout)


class TestPublicFilesDeIdentification(unittest.TestCase):
    """單元測試 8：驗證所有公開版檔案 100% 去個人化（零本機使用者路徑與私人字眼洩漏）"""

    def test_no_personal_keywords_in_public_files(self):
        public_files = [
            REPO_ROOT / "LICENSE",
            REPO_ROOT / "README.md",
            REPO_ROOT / "README.zh-TW.md",
            REPO_ROOT / "skills" / "workspace-governance" / "SKILL.md",
            REPO_ROOT / "scripts" / "audit-workspace.py",
            REPO_ROOT / "examples" / "demo-report.html",
            REPO_ROOT / ".github" / "workflows" / "test.yml",
            REPO_ROOT / "tests" / "test_audit_workspace.py",
        ]
        # 動態檢查本機絕對路徑 (如 /Users/<user>) 與外部個人規則檔中的禁用詞，測試檔本身不留任何個人字串
        current_user = Path.home().name
        forbidden_tokens = list(audit_mod.PERSONAL_RULES.get("forbidden_personal_tokens", []))
        if current_user and current_user.lower() not in ("runner", "ubuntu", "root", "admin", "user"):
            forbidden_tokens.append(current_user)

        for pf in public_files:
            with self.subTest(file=pf.name):
                text = pf.read_text(encoding="utf-8")
                self.assertNotIn(str(Path.home()), text, f"Hardcoded home path leaked in {pf.name}")
                for tok in forbidden_tokens:
                    if re.match(r"^[a-zA-Z0-9_-]+$", tok):
                        pat = re.compile(r"\b" + re.escape(tok) + r"\b", re.IGNORECASE)
                        self.assertIsNone(pat.search(text), f"Forbidden personal token '{tok}' leaked in {pf.name}")
                    else:
                        self.assertNotIn(tok, text, f"Forbidden personal token '{tok}' leaked in {pf.name}")

    def test_current_repo_is_100_percent_pure(self):
        """驗證本開源專案根目錄 (REPO_ROOT) 通過 Anti-Dump 檢查，0 私人檔案殘留"""
        issues = audit_mod.check_repo_purity(REPO_ROOT)
        self.assertEqual(issues, [], f"Repo root is not pure: {issues}")

    def test_first_run_ux_default_output_does_not_trigger_anti_dump(self):
        """驗證外部使用者首次執行預設指令後，再執行 --check-repo . 不會自相矛盾報警"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "ai-first-workspace"
            repo.mkdir()
            # 模擬預設輸出路徑 dist/.cache/dry-run-report.html
            default_out = repo / "dist" / ".cache" / "dry-run-report.html"
            default_out.parent.mkdir(parents=True)
            default_out.write_text("<html></html>", encoding="utf-8")

            issues = audit_mod.check_repo_purity(repo)
            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
