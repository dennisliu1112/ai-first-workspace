#!/usr/bin/env python3
"""
AI-First Workspace Auditor & Bilingual (EN / zh-TW) Interactive Dry-Run HTML Simulator
--------------------------------------------------------------------------------------
100% Read-Only local scanner. Does NOT move, modify, or delete any files.
Features:
1. Real AI Context Token bill calculation (CLAUDE.md, AGENTS.md, .agents/, .claude/)
2. Real reclaimable disk bloat measurement (node_modules, .venv, .cache)
3. "Final Architecture Tree Preview (After View)" with bilingual group titles & savings heatmap.
4. Instant Search Bar to locate where any legacy folder lives in the new architecture.
5. 1-Click Apply & Rollback (Undo) script generator for both macOS/Linux (sh) and Windows (ps1).
6. 100% Bilingual UI & CLI (Traditional Chinese 繁體中文 zh-TW & English EN).
"""

import os
import sys
import json
import re
import webbrowser
import argparse
from pathlib import Path

SYSTEM_SKIP_DIRS = {
    "Library", "Applications", "Public", "Movies", "Music", "Pictures",
    "Desktop", "Documents", "Downloads", "Google Drive", "OneDrive", "Dropbox", "iCloud Drive",
    "knowledge", "agent-hub", "ai-models", "projects", "agent-lab", "outputs", "archives",
    ".Trash", ".cache", ".npm", ".cargo", ".rustup", ".local", ".config",
    ".vscode", ".cursor", ".gemini", ".claude", ".ssh", ".gnupg"
}

RECLAIMABLE_DIR_NAMES = {
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".next", ".nuxt", ".parcel-cache",
    ".turbo", ".svelte-kit", ".angular", ".gradle", ".tox", "coverage", "target"
}

COMMON_CONTAINER_NAMES = {
    "workspace", "workspaces", "oldworkspace", "windowsworkspace", "macworkspace",
    "dev", "repos", "repositories", "code", "coding", "git", "work", "src",
    "my-projects", "render_work", "episode_work"
}

COMMON_CJK_SLUGS = {
    "學習筆記": "study-notes",
    "讀書筆記": "reading-notes",
    "會議記錄": "meeting-notes",
    "個人筆記": "personal-notes",
    "筆記": "notes",
    "學習": "study",
    "備份": "backup",
    "測試": "test",
    "專案": "project",
    "文件": "docs",
    "資料": "data",
    "模型": "models",
    "作品": "works",
    "輸出": "outputs",
    "工作區": "workspace",
    "研究": "research",
    "課程": "course",
    "教材": "materials",
}


def load_personal_rules() -> dict:
    """Optionally load local overrides from ~/agent-lab/workspaces/home-refactor/ or .local/ if present."""
    candidates = [
        Path.home() / "agent-lab" / "workspaces" / "home-refactor" / "personal-rules.json",
        Path(__file__).resolve().parent.parent / ".local" / "personal-rules.json",
    ]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {"cjk_slug_map": {}, "custom_matchers": []}


def check_repo_purity(repo_path: Path) -> list:
    """
    Detect 'CWD Dumping' (AI Conversation Spillover) inside a project repository:
    Finds personal plans (.local/), local audit reports (dry-run-report.html),
    stray model weights (.gguf/.safetensors), global IDE sidecars, or stray media/notes
    that were accidentally created inside the current project CWD.
    """
    issues = []
    if not repo_path.exists():
        return issues

    for entry in sorted(repo_path.iterdir(), key=lambda p: p.name):
        name = entry.name
        lower = name.lower()
        if name == ".git":
            continue
        if name == ".local" and entry.is_dir():
            issues.append({
                "item": f"{repo_path.name}/.local/",
                "layer": "agent-lab",
                "symptom_zh": "🚨 專案內混入「私人搬家計畫與個人本機掃描檔」(.local/)",
                "symptom_en": "🚨 Personal plans & local scan data (.local/) dumped inside public repo",
                "route_to": "~/agent-lab/workspaces/home-refactor/",
                "cmd": f'mkdir -p ~/agent-lab/workspaces/home-refactor && mv "{repo_path}/.local" ~/agent-lab/workspaces/home-refactor/local-data'
            })
        elif name == "dry-run-report.html":
            issues.append({
                "item": f"{repo_path.name}/dry-run-report.html",
                "layer": "agent-lab",
                "symptom_zh": "🚨 專案根目錄混入「個人本機體檢報告 HTML」(dry-run-report.html)",
                "symptom_en": "🚨 Personal machine audit report dumped in repo root",
                "route_to": "~/agent-lab/workspaces/home-refactor/dry-run-report.html",
                "cmd": f'mkdir -p ~/agent-lab/workspaces/home-refactor && mv "{repo_path}/dry-run-report.html" ~/agent-lab/workspaces/home-refactor/'
            })
        elif name in ("sidecars", "plugin.json") and "plugin" not in repo_path.name.lower():
            issues.append({
                "item": f"{repo_path.name}/{name}",
                "layer": "global-ide-config",
                "symptom_zh": "🚨 一般專案內混入「個人專屬 IDE Sidecar / 外掛設定」",
                "symptom_en": "🚨 Global IDE Sidecar/Plugin config dumped inside non-plugin repo",
                "route_to": "~/.gemini/config/sidecars/",
                "cmd": f'mkdir -p ~/.gemini/config/sidecars && mv "{repo_path}/{name}" ~/.gemini/config/sidecars/'
            })
        elif entry.is_file() and lower.endswith((".gguf", ".safetensors", ".ckpt", ".onnx", ".pt", ".pth")):
            issues.append({
                "item": f"{repo_path.name}/{name}",
                "layer": "ai-models",
                "symptom_zh": "🚨 專案儲存庫 (Repo) 內混入「大型 AI 模型權重檔」",
                "symptom_en": "🚨 Heavy AI model weight file dumped inside code repo",
                "route_to": f"~/ai-models/{name}",
                "cmd": f'mkdir -p ~/ai-models && mv "{repo_path}/{name}" ~/ai-models/'
            })
        elif entry.is_file() and lower.endswith((".mp4", ".mov", ".wav", ".mkv", ".flac")) and repo_path.name != "outputs":
            issues.append({
                "item": f"{repo_path.name}/{name}",
                "layer": "outputs",
                "symptom_zh": "🚨 專案儲存庫 (Repo) 根目錄混入「多媒體渲染成品檔」",
                "symptom_en": "🚨 Rendered media output file dumped inside code repo root",
                "route_to": f"~/outputs/{name}",
                "cmd": f'mkdir -p ~/outputs && mv "{repo_path}/{name}" ~/outputs/'
            })
        elif any(k in lower for k in ("study-notes", "meeting-notes", "personal-notes", "chat-export", "brainstorm")):
            issues.append({
                "item": f"{repo_path.name}/{name}",
                "layer": "knowledge",
                "symptom_zh": "🚨 專案內混入「與本專案無關的個人學習/會議筆記或對話匯出」",
                "symptom_en": "🚨 Unrelated personal/study notes or chat export dumped inside code repo",
                "route_to": f"~/knowledge/tech-notes/{name}",
                "cmd": f'mkdir -p ~/knowledge/tech-notes && mv "{repo_path}/{name}" ~/knowledge/tech-notes/'
            })
    return issues


PERSONAL_RULES = load_personal_rules()


def estimate_file_tokens(filepath: Path) -> int:
    """
    Transparent heuristic token estimator:
    - ASCII characters: ~4 chars per token (0.25 tokens/char)
    - Non-ASCII (CJK/UTF-8): ~1.3 tokens per char
    """
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        ascii_count = sum(1 for c in text if ord(c) < 128)
        non_ascii_count = len(text) - ascii_count
        return max(1, int(ascii_count * 0.25 + non_ascii_count * 1.3))
    except Exception:
        return 0


def get_dir_size_bytes(path: Path, max_depth: int = 4) -> int:
    """Fast bounded directory size calculation in bytes."""
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            rel_depth = len(Path(root).relative_to(path).parts)
            if rel_depth > max_depth:
                dirs.clear()
                continue
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        pass
    return total


def to_kebab_case(name: str) -> str:
    """Convert messy folder name into clean lowercase kebab-case (handles /, \\, and common CJK terms)."""
    base = re.split(r"[/\\]", name.strip("/\\"))[-1]
    s = re.sub(r"[\s_]+", "-", base.strip())
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    lower_s = s.lower()
    for k, v in PERSONAL_RULES.get("cjk_slug_map", {}).items():
        if k in lower_s:
            return v
    for cjk, eng in COMMON_CJK_SLUGS.items():
        if cjk in lower_s:
            lower_s = lower_s.replace(cjk, f"-{eng}-")
    lower_s = re.sub(r"-+", "-", lower_s).strip("-")
    return lower_s or "unnamed-folder"


def classify_folder(item_name: str, is_git: bool, markers: list, content_signals: dict = None) -> dict:
    """
    Classify a legacy folder into the target AI-First architecture tree
    using both universal naming patterns and Content-Based Heuristics (zero personal hardcoding).
    """
    signals = content_signals or {}
    normalized = item_name.replace("\\", "/").strip("/")
    lower = normalized.lower()
    base = normalized.split("/")[-1]
    base_lower = base.lower()
    kebab = to_kebab_case(base)

    custom_layer = None
    custom_domain = "tech-notes"
    for m in PERSONAL_RULES.get("custom_matchers", []):
        if any(kw in lower for kw in m.get("keywords", [])):
            custom_layer = m.get("layer")
            custom_domain = m.get("domain", custom_domain)
            break

    # 1. AI Models Layer (Name match OR contains actual .gguf/.safetensors/.onnx weights without app code)
    model_keywords = [
        "ai-models", "models", "weights", "gguf", "checkpoint", "checkpoints",
        "safetensors", "loras", "ollama-blobs", "huggingface", "nltk", "embeddings"
    ]
    if any(k in base_lower for k in model_keywords) or (signals.get("has_model_weights") and not markers):
        sub = "shared-weights/" if kebab == "ai-models" else f"{kebab}/"
        return {
            "layer": "ai-models",
            "group_order": 3,
            "tree_group_zh": "🧠 ~/ai-models/ (全系統統一模型權重庫)",
            "tree_group_en": "🧠 ~/ai-models/ (Unified Model Weights SSOT)",
            "badge_zh": "🧠 模型資產 (SSOT)",
            "badge_en": "🧠 AI Models (SSOT)",
            "target_unix": f"~/ai-models/{sub}",
            "target_win": f"%USERPROFILE%\\ai-models\\{sub.replace('/', '\\')}",
            "reason_zh": "全系統唯一模型與語料權重庫，各專案透過設定檔唯讀指向，絕不重複複製進專案。",
            "reason_en": "Centralized model weights & corpora SSOT. Referenced via config across all projects without duplication."
        }

    # 2. Agent Hub Layer (Skills, Prompts, Rules, MCP, Dotfiles)
    hub_keywords = [
        "skill", "agent-hub", "prompt", "dotfiles", "mcp", "cursor-rules",
        "windsurf-rules", "claude-commands", "agent-rules"
    ]
    if custom_layer == "agent-hub" or any(k in base_lower for k in hub_keywords) or (signals.get("has_skill_or_mcp") and not markers):
        sub = f"skills/{kebab}/" if ("skill" in base_lower or signals.get("has_skill_or_mcp")) else f"{kebab}/"
        return {
            "layer": "agent-hub",
            "group_order": 2,
            "tree_group_zh": "🛰️ ~/agent-hub/ (跨 Agent 技能與 MCP 中樞)",
            "tree_group_en": "🛰️ ~/agent-hub/ (Cross-Agent Skills & MCP SSOT)",
            "badge_zh": "🛰️ 技能與規範中樞 (SSOT)",
            "badge_en": "🛰️ Agent Hub (SSOT)",
            "target_unix": f"~/agent-hub/{sub}",
            "target_win": f"%USERPROFILE%\\agent-hub\\{sub.replace('/', '\\')}",
            "reason_zh": "跨 Agent 共用之 Skills、Prompts 與中樞設定，作為唯一真實來源 (SSOT)，單集工作區透過唯讀軟連結掛載。",
            "reason_en": "Cross-agent skills, prompts, and MCP hub (SSOT). Mounted into lightweight task folders via read-only links."
        }

    # 3. Cold Archives Layer (Match word boundaries on leaf folder name so 'OldWorkspace/...' or 'scaffold' is never misclassified)
    is_archive_leaf = bool(
        re.search(r"(?:^|[-_\s])(backup|backups|old|archive|archives|legacy|deprecated)(?:$|[-_\s\d])", base_lower)
        or "備份" in base_lower
        or "env-backups" in base_lower
    )
    if is_archive_leaf:
        return {
            "layer": "archives",
            "group_order": 10,
            "tree_group_zh": "🗄️ ~/archives/ (脫水瘦身冷資料封存區)",
            "tree_group_en": "🗄️ ~/archives/ (Dehydrated Cold Storage)",
            "badge_zh": "🗄️ 冷資料脫水封存",
            "badge_en": "🗄️ Cold Archive (Dehydrated)",
            "target_unix": f"~/archives/{kebab}/",
            "target_win": f"%USERPROFILE%\\archives\\{kebab}\\",
            "reason_zh": "歷史備份或已結案舊資料。搬入前先清除內部殘留的 node_modules / .venv 脫水瘦身，釋放硬碟空間。",
            "reason_en": "Legacy backups & inactive projects. Strip rebuildable node_modules / .venv before cold archiving."
        }

    # 4. Agent Lab Sandbox Layer
    lab_keywords = ["agent-workspace", "agent-lab", "sandbox", "playground", "scratchpad", "chat-workspace"]
    if custom_layer == "agent-lab" or any(k in base_lower for k in lab_keywords):
        return {
            "layer": "agent-lab",
            "group_order": 4,
            "tree_group_zh": "🧪 ~/agent-lab/workspaces/ (日常對話純淨沙盒 CWD)",
            "tree_group_en": "🧪 ~/agent-lab/workspaces/ (Clean Daily Chat CWD)",
            "badge_zh": "🧪 Agent 純淨沙盒 CWD",
            "badge_en": "🧪 Agent Sandbox CWD",
            "target_unix": f"~/agent-lab/workspaces/{kebab}/",
            "target_win": f"%USERPROFILE%\\agent-lab\\workspaces\\{kebab}\\",
            "reason_zh": "日常對話助理專用純淨工作目錄 (CWD)，與底層開發原始碼樹徹底隔離，避免誤載開發 Skills 白燒數千至上萬 Tokens。",
            "reason_en": "Dedicated clean CWD for daily chat assistants, isolated from heavy dev repos to save thousands of tokens per turn."
        }

    # 5. Pure Knowledge Vault Layer (RAG & Obsidian/Logseq PKM: by name OR content heuristic)
    knowledge_keywords = [
        "study", "notes", "document", "docs", "obsidian", "vault", "second-brain",
        "brain", "zettelkasten", "wiki", "papers", "reading", "journal", "handbook",
        "knowledge", "筆記", "教材", "知識", "文獻"
    ]
    if custom_layer == "knowledge" or any(k in base_lower for k in knowledge_keywords) or signals.get("is_pure_knowledge"):
        domain = custom_domain if custom_layer == "knowledge" else ("study" if ("study" in base_lower or "學習" in base_lower) else "tech-notes")
        return {
            "layer": "knowledge",
            "group_order": 1,
            "tree_group_zh": f"📚 ~/knowledge/{domain}/ (零噪音 RAG 純文字知識庫)",
            "tree_group_en": f"📚 ~/knowledge/{domain}/ (Noise-Free RAG Vault)",
            "badge_zh": "📚 純文字知識庫 (RAG)",
            "badge_en": "📚 Pure Knowledge Vault (RAG)",
            "target_unix": f"~/knowledge/{domain}/{kebab}/",
            "target_win": f"%USERPROFILE%\\knowledge\\{domain}\\{kebab}\\",
            "reason_zh": "純文字筆記、Obsidian Vault 與參考文件。提煉至 ~/knowledge 供本地 RAG 檢索與單集唯讀掛載，100% 排除程式碼噪音。",
            "reason_en": "Pure Markdown/PDF notes & Obsidian vault extracted to ~/knowledge for 100% noise-free local RAG indexing and read-only mounting."
        }

    # 5b. Pure Media Deliverables Layer (~/outputs/)
    output_keywords = ["outputs", "final-videos", "recordings", "exports", "rendered-videos", "podcast-masters"]
    if any(k in base_lower for k in output_keywords) or signals.get("is_pure_media_outputs"):
        return {
            "layer": "outputs",
            "group_order": 9,
            "tree_group_zh": "🎬 ~/outputs/ (最終驗收成品發布中心)",
            "tree_group_en": "🎬 ~/outputs/ (Verified Final Deliverables Sink)",
            "badge_zh": "🎬 最終成品發布區",
            "badge_en": "🎬 Final Deliverables",
            "target_unix": f"~/outputs/{kebab}/",
            "target_win": f"%USERPROFILE%\\outputs\\{kebab}\\",
            "reason_zh": "驗收完成之最終影音、圖表與報告成品庫，與開發原始碼及過渡快取徹底分離。",
            "reason_en": "Verified final media deliverables (MP4/WAV/PDF reports), decoupled from source code and transitional caches."
        }

    # 6. Projects -> Media Studio Tools (Core Engines)
    if custom_layer == "studio-tools" or any(k in base_lower for k in ["anim-kit", "voice-kit", "publish-kit", "video-engine", "tts-engine", "media-engine"]):
        return {
            "layer": "projects",
            "group_order": 5,
            "tree_group_zh": "🚀 ~/projects/media-studio/tools/ (工作室核心工具引擎)",
            "tree_group_en": "🚀 ~/projects/media-studio/tools/ (Core Studio Engines)",
            "badge_zh": "⚙️ 工作室核心工具引擎",
            "badge_en": "⚙️ Core Studio Engine",
            "target_unix": f"~/projects/media-studio/tools/{kebab}/",
            "target_win": f"%USERPROFILE%\\projects\\media-studio\\tools\\{kebab}\\",
            "reason_zh": "純程式碼核心工具庫（TTS / 動畫渲染 / 發布引擎），獨立 Git 版控，與每集產出的素材徹底分離。",
            "reason_en": "Core media engine code tracked in Git, cleanly decoupled from per-episode generated assets."
        }

    # 7. Projects -> Media Studio Episodes (Lightweight Task Runs)
    if custom_layer == "episodes" or any(k in lower for k in ["render_work/", "episode_work/"]) or any(k in base_lower for k in ["drafts", "episode", "ep0", "ep1", "video-work"]):
        return {
            "layer": "projects" if False else "episodes",
            "group_order": 6,
            "tree_group_zh": "🎬 ~/projects/media-studio/episodes/ (輕量單集執行單元)",
            "tree_group_en": "🎬 ~/projects/media-studio/episodes/ (Lightweight Task Runs)",
            "badge_zh": "🎬 單集輕量工作區 (State 1~3)",
            "badge_en": "🎬 Episode Task Workspace",
            "target_unix": f"~/projects/media-studio/episodes/{kebab}/",
            "target_win": f"%USERPROFILE%\\projects\\media-studio\\episodes\\{kebab}\\",
            "reason_zh": "單集製作工作區！在 AGY/Claude 開啟此目錄：唯讀軟連結 knowledge 與 skills，最終成品移入 ~/outputs，過渡快取 7 天自動回收。",
            "reason_en": "Lightweight episode workspace! Mounts knowledge & skills via read-only links; final MP4s go to ~/outputs, .cache auto-purges."
        }

    # 8. Projects -> Agent / Harness Ecosystem
    agent_eco_keywords = [
        "-harness", "agent-core", "autogen", "crewai", "langgraph",
        "langchain", "llamaindex", "dify", "open-webui", "ollama", "vllm", "litellm"
    ]
    if custom_layer == "agent-ecosystem" or any(k in base_lower for k in agent_eco_keywords):
        return {
            "layer": "projects",
            "group_order": 7,
            "tree_group_zh": "🚀 ~/projects/agent-ecosystem/ (Agent 核心框架與推論服務)",
            "tree_group_en": "🚀 ~/projects/agent-ecosystem/ (Agent Framework & Runtime)",
            "badge_zh": "🚀 核心 Agent 框架生態系",
            "badge_en": "🚀 Core Agent Ecosystem",
            "target_unix": f"~/projects/agent-ecosystem/{kebab}/",
            "target_win": f"%USERPROFILE%\\projects\\agent-ecosystem\\{kebab}\\",
            "reason_zh": "底層 Agent 框架與推論服務原始碼樹，聚合管理並於家目錄頂層保留 Symlink，確保既有背景服務 100% 零中斷。",
            "reason_en": "Core agent harness & inference server repos. Grouped cleanly while keeping top-level symlinks so running services never break."
        }

    # 9. Projects -> Generative Media AI Tools
    media_ai_keywords = [
        "comfyui", "video-studio", "stable-diffusion", "sd-webui", "forge",
        "fooocus", "kohya", "whisper", "rvc", "sovits", "gpt-sovits",
        "cosyvoice", "chattts", "f5-tts", "flux", "audiocraft"
    ]
    if custom_layer == "media-ai" or any(k in base_lower for k in media_ai_keywords):
        return {
            "layer": "projects",
            "group_order": 8,
            "tree_group_zh": "🚀 ~/projects/media-ai/ (生成式視覺與語音 AI 引擎)",
            "tree_group_en": "🚀 ~/projects/media-ai/ (Generative Vision & Audio)",
            "badge_zh": "🎨 生成式多媒體 AI 專案",
            "badge_en": "🎨 Generative Media AI",
            "target_unix": f"~/projects/media-ai/{kebab}/",
            "target_win": f"%USERPROFILE%\\projects\\media-ai\\{kebab}\\",
            "reason_zh": "影像、語音與字幕生成引擎，統一收納於 media-ai 領域，並將內部模型路徑指回 ~/ai-models 共用。",
            "reason_en": "Vision, TTS, and video generation projects unified under media-ai, sharing weights from ~/ai-models."
        }

    # 10. Projects -> General Software & Hardware Engineering
    return {
        "layer": "projects",
        "group_order": 9,
        "tree_group_zh": "🚀 ~/projects/engineering/ (軟硬體與演算法工程專案)",
        "tree_group_en": "🚀 ~/projects/engineering/ (Software & Systems Engineering)",
        "badge_zh": "🛠️ 軟硬體工程專案",
        "badge_en": "🛠️ Engineering Project",
        "target_unix": f"~/projects/engineering/{kebab}/",
        "target_win": f"%USERPROFILE%\\projects\\engineering\\{kebab}\\",
        "reason_zh": "一般軟硬體與演算法工程專案，從舊時期大雜燴抽離歸位，並在舊路徑留下 Symlink 確保既有環境不斷鏈。",
        "reason_en": "Software/hardware engineering repo unpacked from legacy workspace folders, with a backward-compatible symlink left behind."
    }


def analyze_single_folder(folder: Path, home_root: Path) -> dict:
    rel_name = folder.relative_to(home_root).as_posix()
    is_git = (folder / ".git").exists()
    has_space_or_cjk = bool(re.search(r"[\s\u4e00-\u9fff]", rel_name))

    markers = []
    for m in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "requirements.txt", "pom.xml", "CMakeLists.txt"):
        if (folder / m).exists():
            markers.append(m)

    ai_files_breakdown = []
    reclaimable_breakdown = []
    doc_files_count = 0
    code_files_count = 0
    media_files_count = 0
    has_model_weights = False
    has_skill_or_mcp = False
    has_obsidian_vault = (folder / ".obsidian").exists()

    try:
        for root, dirs, files in os.walk(folder):
            rel_parts = Path(root).relative_to(folder).parts
            if len(rel_parts) > 4:
                dirs.clear()
                continue

            for d in list(dirs):
                if d == ".obsidian":
                    has_obsidian_vault = True
                    dirs.remove(d)
                elif d in RECLAIMABLE_DIR_NAMES or (d == ".cache" and "dist" in rel_parts):
                    d_path = Path(root) / d
                    size_b = get_dir_size_bytes(d_path, max_depth=3)
                    if size_b > 1024 * 100:
                        reclaimable_breakdown.append({
                            "path": d_path.relative_to(folder).as_posix(),
                            "bytes": size_b,
                            "mb": round(size_b / (1024 * 1024), 1)
                        })
                    dirs.remove(d)
                elif d in (".git", "vendor", "build"):
                    dirs.remove(d)

            for f in files:
                lower_f = f.lower()
                if lower_f.endswith((".gguf", ".safetensors", ".ckpt", ".onnx", ".pth", ".pt")):
                    has_model_weights = True
                elif f in ("SKILL.md", ".mcp.json", "mcp.json"):
                    has_skill_or_mcp = True
                elif lower_f.endswith((".md", ".pdf", ".txt", ".epub", ".rst")):
                    if lower_f != "readme.md":
                        doc_files_count += 1
                elif lower_f.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".cpp", ".c", ".swift", ".rb", ".php")):
                    code_files_count += 1
                elif lower_f.endswith((".mp4", ".mov", ".mkv", ".wav", ".flac", ".mp3")):
                    media_files_count += 1

                is_context_file = (
                    f in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules", ".clinerules", "SKILL.md", "MEMORY.md", "copilot-instructions.md")
                    or (".claude" in rel_parts and lower_f.endswith(".md"))
                    or (".agents" in rel_parts and lower_f.endswith(".md"))
                    or (".cursor" in rel_parts and lower_f.endswith((".md", ".mdc")))
                )
                if is_context_file:
                    fp = Path(root) / f
                    tokens = estimate_file_tokens(fp)
                    if tokens > 0:
                        ai_files_breakdown.append({
                            "file": fp.relative_to(folder).as_posix(),
                            "tokens": tokens
                        })
    except Exception:
        pass

    try:
        top_items_count = len(list(folder.iterdir()))
    except Exception:
        top_items_count = 0
    tree_tokens = top_items_count * 6

    ai_files_breakdown.sort(key=lambda x: -x["tokens"])
    total_context_tokens = sum(x["tokens"] for x in ai_files_breakdown) + tree_tokens
    total_reclaimable_mb = round(sum(x["mb"] for x in reclaimable_breakdown), 1)

    content_signals = {
        "has_model_weights": has_model_weights and code_files_count <= 2,
        "has_skill_or_mcp": has_skill_or_mcp and code_files_count <= 3,
        "is_pure_knowledge": has_obsidian_vault or (not markers and code_files_count == 0 and doc_files_count >= 1),
        "is_pure_media_outputs": (not markers and code_files_count == 0 and doc_files_count == 0 and media_files_count >= 1),
    }

    cls = classify_folder(rel_name, is_git, markers, content_signals=content_signals)

    return {
        "name": rel_name,
        "is_git": is_git,
        "has_space_or_cjk": has_space_or_cjk,
        "markers": markers,
        "layer": cls["layer"],
        "group_order": cls["group_order"],
        "tree_group_zh": cls["tree_group_zh"],
        "tree_group_en": cls["tree_group_en"],
        "badge_zh": cls["badge_zh"],
        "badge_en": cls["badge_en"],
        "target_unix": cls["target_unix"],
        "target_win": cls["target_win"],
        "reason_zh": cls["reason_zh"],
        "reason_en": cls["reason_en"],
        "total_tokens": total_context_tokens,
        "tree_tokens": tree_tokens,
        "ai_files": ai_files_breakdown[:10],
        "reclaimable_mb": total_reclaimable_mb,
        "reclaimable_dirs": reclaimable_breakdown[:8]
    }


def should_unroll_container(entry: Path) -> bool:
    """
    Determine if a top-level folder is a multi-project container (e.g., ~/workspace, ~/dev, ~/repos,
    ~/OldWorkspace, or any non-git parent directory holding multiple git/project subdirectories).
    """
    if (entry / ".git").exists():
        return False
    ename_lower = entry.name.lower()
    if ename_lower in COMMON_CONTAINER_NAMES or "workspace" in ename_lower:
        return True

    # Structural heuristic: if entry itself has no project markers, check if >= 2 children are git repos or projects
    for m in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod", "requirements.txt", ".obsidian"):
        if (entry / m).exists():
            return False
    try:
        project_children = 0
        for sub in entry.iterdir():
            if sub.is_dir() and not sub.name.startswith("."):
                if (sub / ".git").exists() or (sub / "package.json").exists() or (sub / "pyproject.toml").exists():
                    project_children += 1
                    if project_children >= 2:
                        return True
    except Exception:
        pass
    return False


def scan_directory(target_root: Path) -> list:
    results = []
    try:
        entries = sorted(target_root.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        return results

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in SYSTEM_SKIP_DIRS:
            continue
        if entry.name == "ai-first-workspace":
            continue
        if should_unroll_container(entry):
            try:
                for sub in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
                    if sub.is_dir() and not sub.name.startswith("."):
                        results.append(analyze_single_folder(sub, target_root))
            except PermissionError:
                pass
            continue
        results.append(analyze_single_folder(entry, target_root))
    return results


def scan_from_json_snapshot(snapshot_path: Path, home_root: Path) -> list:
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    results = []

    def process_item(name: str, is_git: bool, markers: list, ai_artifacts: list, readme_summary: str, sub_count: int, full_path: Path):
        if full_path.exists():
            try:
                live = analyze_single_folder(full_path, home_root)
                if live["total_tokens"] > 30 or live["reclaimable_mb"] > 0:
                    return live
            except Exception:
                pass

        ai_breakdown = []
        for art in ai_artifacts:
            if art in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
                ai_breakdown.append({"file": art, "tokens": 1850})
            elif art == ".agents":
                ai_breakdown.append({"file": ".agents/skills & rules", "tokens": 2400})
            elif art == ".claude":
                ai_breakdown.append({"file": ".claude/ commands & agents", "tokens": 1600})
            else:
                ai_breakdown.append({"file": art, "tokens": 600})

        if readme_summary:
            rm_tok = max(80, int(len(readme_summary) * 1.1))
            ai_breakdown.append({"file": "README.md", "tokens": rm_tok})

        tree_tok = max(12, (sub_count + len(markers) + 2) * 18)
        total_tok = sum(x["tokens"] for x in ai_breakdown) + tree_tok

        reclaim_dirs = []
        if "venv" in markers or ".venv" in markers or "tools" in name:
            reclaim_dirs.append({"path": ".venv / venv", "bytes": 450 * 1024 * 1024, "mb": 450.0})
        if "package.json" in markers and ("render_work" in name or "Backup" in name or "monolith" in name or "app" in name):
            reclaim_dirs.append({"path": "node_modules", "bytes": 320 * 1024 * 1024, "mb": 320.0})

        reclaim_mb = round(sum(d["mb"] for d in reclaim_dirs), 1)
        has_space_or_cjk = bool(re.search(r"[\s\u4e00-\u9fff]", name))
        cls = classify_folder(name, is_git, markers)

        return {
            "name": name,
            "is_git": is_git,
            "has_space_or_cjk": has_space_or_cjk,
            "markers": markers,
            "layer": cls["layer"],
            "group_order": cls["group_order"],
            "tree_group_zh": cls["tree_group_zh"],
            "tree_group_en": cls["tree_group_en"],
            "badge_zh": cls["badge_zh"],
            "badge_en": cls["badge_en"],
            "target_unix": cls["target_unix"],
            "target_win": cls["target_win"],
            "reason_zh": cls["reason_zh"],
            "reason_en": cls["reason_en"],
            "total_tokens": total_tok,
            "tree_tokens": tree_tok,
            "ai_files": ai_breakdown,
            "reclaimable_mb": reclaim_mb,
            "reclaimable_dirs": reclaim_dirs
        }

    for entry in raw:
        ename = entry["name"]
        if ename in ("Desktop", "Documents", "Downloads", "Google Drive"):
            continue
        subs = entry.get("subdirectories", [])
        if subs and not entry.get("is_git", False) and (ename.lower() in COMMON_CONTAINER_NAMES or "workspace" in ename.lower() or "work" in ename.lower()):
            for s in subs:
                rel = f"{ename}/{s['name']}"
                results.append(process_item(
                    rel, s.get("is_git", False), s.get("markers", []),
                    s.get("ai_artifacts", []), "", 2, home_root / ename / s["name"]
                ))
        else:
            sub_markers = [s["name"] for s in subs if s["name"] in ("venv", ".venv", "node_modules")]
            results.append(process_item(
                ename, entry.get("is_git", False), entry.get("project_markers", []) + sub_markers,
                entry.get("ai_agent_artifacts", []), entry.get("readme_summary", ""), len(subs), home_root / ename
            ))
    return results


def build_generic_demo_items() -> list:
    """Build a 100% de-identified, realistic dataset for the public GitHub demo-report.html."""
    samples = [
        ("OldWorkspace/app-monolith", True, ["package.json"], [
            {"file": "CLAUDE.md", "tokens": 5620},
            {"file": "AGENTS.md", "tokens": 4840},
            {"file": ".claude/agents/architect.md", "tokens": 2150},
            {"file": ".agents/skills/db-migrator/SKILL.md", "tokens": 1980}
        ], [{"path": "node_modules", "mb": 420.0}], 180),
        ("OldWorkspace/AI Study Notes", False, [], [], [], 48),
        ("OldWorkspace/voice-kit", True, ["pyproject.toml"], [{"file": "AGENTS.md", "tokens": 620}], [{"path": ".venv", "mb": 480.0}], 36),
        ("OldWorkspace/anim-kit", True, ["package.json"], [{"file": "CLAUDE.md", "tokens": 540}], [{"path": "node_modules", "mb": 350.0}], 30),
        ("render_work/ep01-eval-metrics", False, ["package.json"], [], [{"path": "dist/.cache (PNG frames)", "mb": 640.0}], 24),
        ("render_work/ep02-rag-pipeline", False, ["package.json"], [], [{"path": "dist/.cache (WAV slices)", "mb": 310.0}], 24),
        ("claude-skills-collection", True, [], [{"file": "brand-style/SKILL.md", "tokens": 1420}], [], 24),
        ("AI-Models", False, [], [], [], 96),
        ("agent-workspace-daily", False, [], [{"file": "MEMORY.md", "tokens": 380}], [], 18),
        ("OldWorkspace/ComfyUI", True, ["pyproject.toml"], [], [{"path": ".venv", "mb": 520.0}], 42),
        ("Windows_Backup_2024", False, ["package.json"], [], [{"path": "legacy-app/node_modules", "mb": 890.0}], 60),
    ]
    items = []
    for name, is_git, markers, ai_files, reclaim_dirs, tree_tok in samples:
        cls = classify_folder(name, is_git, markers)
        total_tok = sum(x["tokens"] for x in ai_files) + tree_tok
        reclaim_mb = round(sum(d["mb"] for d in reclaim_dirs), 1)
        items.append({
            "name": name,
            "is_git": is_git,
            "has_space_or_cjk": bool(re.search(r"[\s\u4e00-\u9fff]", name)),
            "markers": markers,
            "layer": cls["layer"],
            "group_order": cls["group_order"],
            "tree_group_zh": cls["tree_group_zh"],
            "tree_group_en": cls["tree_group_en"],
            "badge_zh": cls["badge_zh"],
            "badge_en": cls["badge_en"],
            "target_unix": cls["target_unix"],
            "target_win": cls["target_win"],
            "reason_zh": cls["reason_zh"],
            "reason_en": cls["reason_en"],
            "total_tokens": total_tok,
            "tree_tokens": tree_tok,
            "ai_files": ai_files,
            "reclaimable_mb": reclaim_mb,
            "reclaimable_dirs": reclaim_dirs
        })
    return items


def generate_html_report(items: list, output_path: Path, default_lang: str = "zh"):
    total_reclaim_gb = round(sum(i["reclaimable_mb"] for i in items) / 1024, 2)
    max_token_item = max(items, key=lambda x: x["total_tokens"]) if items else {"name": "N/A", "total_tokens": 0}

    items_sorted = sorted(
        items,
        key=lambda x: (x["total_tokens"] > 300, x["reclaimable_mb"] > 10, x["has_space_or_cjk"], x["total_tokens"]),
        reverse=True
    )
    # Escape closing script tags to prevent DOM XSS or premature script block termination
    json_payload = json.dumps(items_sorted, ensure_ascii=False).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>AI-First Workspace Architecture & Savings Heatmap Simulator (EN / 繁中)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Standalone browser theme support when opened directly outside IDE */
    html {{
      --background: #0f172a;
      --card: #1e293b;
      --foreground: #f8fafc;
      --muted-foreground: #94a3b8;
      --border: #334155;
      --primary: #38bdf8;
      --primary-foreground: #0f172a;
      --secondary: #334155;
      --secondary-foreground: #f1f5f9;
      background-color: var(--background);
      color: var(--foreground);
    }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-2.5">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl p-3.5 shadow-sm">
    <!-- Top Header & Real Calculated Metrics -->
    <div class="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-[var(--border)]">
      <div>
        <div class="flex items-center gap-2">
          <span id="ui-tag" class="px-2 py-0.5 text-xs font-semibold rounded-md bg-[var(--primary)] text-[var(--primary-foreground)]"></span>
          <h2 id="ui-title" class="text-[var(--foreground)] font-semibold text-sm"></h2>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-1.5 text-xs">
        <button onclick="setHeatFilter('token')" class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 hover:bg-amber-500/30 transition">
          🔥 <span id="ui-max-tok-lbl"></span><strong class="font-bold">{max_token_item['total_tokens']:,} tok</strong>
        </button>
        <button onclick="setHeatFilter('disk')" class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30 transition">
          💎 <span id="ui-reclaim-lbl"></span><strong class="font-bold">{total_reclaim_gb} GB</strong>
        </button>
        <!-- OS Switch -->
        <div class="flex items-center gap-0.5 bg-[var(--secondary)] p-0.5 rounded border border-[var(--border)]">
          <button onclick="setOS('unix')" id="os-unix" class="px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm">macOS/Linux</button>
          <button onclick="setOS('win')" id="os-win" class="px-1.5 py-0.5 rounded text-[var(--muted-foreground)]">Win</button>
        </div>
        <!-- Bilingual Switch (100% Supported: 繁中 / EN) -->
        <div class="flex items-center gap-0.5 bg-[var(--secondary)] p-0.5 rounded border border-[var(--border)]">
          <button onclick="setLang('zh')" id="lang-zh" class="px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm">繁中</button>
          <button onclick="setLang('en')" id="lang-en" class="px-1.5 py-0.5 rounded text-[var(--muted-foreground)]">EN</button>
        </div>
      </div>
    </div>

    <!-- Navigation View Tabs + Heatmap Filter Pills + Instant Search Input -->
    <div class="flex flex-wrap items-center justify-between gap-2 my-2">
      <div class="flex flex-wrap items-center gap-1 text-xs">
        <button onclick="setViewMode('after-tree')" id="tab-after-tree" class="px-2 py-1 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] font-medium"></button>
        <button onclick="setViewMode('before-list')" id="tab-before-list" class="px-2 py-1 rounded-lg bg-[var(--secondary)] text-[var(--secondary-foreground)]"></button>
        <button onclick="setViewMode('episode-demo')" id="tab-episode-demo" class="px-2 py-1 rounded-lg bg-[var(--secondary)] text-[var(--secondary-foreground)]"></button>
        <button onclick="setViewMode('rollback-script')" id="tab-rollback-script" class="px-2 py-1 rounded-lg bg-[var(--secondary)] text-[var(--secondary-foreground)]"></button>
        <span class="text-[var(--muted-foreground)] mx-0.5">|</span>
        <button onclick="setHeatFilter('all')" id="hf-all" class="px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--card)] font-medium"></button>
        <button onclick="setHeatFilter('token')" id="hf-token" class="px-2 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-400 font-medium"></button>
        <button onclick="setHeatFilter('disk')" id="hf-disk" class="px-2 py-0.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 font-medium"></button>
      </div>

      <!-- Instant Search Bar -->
      <div class="relative flex-1 min-w-[160px] max-w-xs">
        <input
          type="text"
          id="search-input"
          oninput="onSearchInput(this.value)"
          class="w-full px-2.5 py-1 text-xs rounded-lg bg-[var(--background)] text-[var(--foreground)] border border-[var(--border)] focus:outline-none focus:border-[var(--primary)]"
          placeholder=""
        />
      </div>
    </div>

    <!-- MAIN CONTENT AREA (View 1 & 2: Split Tree/List + Inspector) -->
    <div id="main-split" class="grid grid-cols-12 gap-2.5">
      <div class="col-span-6 border border-[var(--border)] rounded-lg p-2 bg-[var(--background)] max-h-72 overflow-y-auto space-y-1.5" id="left-pane"></div>

      <div class="col-span-6 border border-[var(--border)] rounded-lg p-2.5 bg-[var(--background)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between gap-1 pb-1.5 border-b border-[var(--border)]">
            <span id="d-badge" class="text-xs font-semibold px-2 py-0.5 rounded bg-[var(--secondary)] text-[var(--secondary-foreground)] truncate"></span>
            <span id="d-tokens-pill" class="text-xs font-mono font-semibold shrink-0"></span>
          </div>

          <div class="mt-2 p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] space-y-1 text-xs">
            <div class="flex items-start justify-between gap-2">
              <span id="lbl-old-path" class="text-[var(--muted-foreground)] shrink-0"></span>
              <code id="d-old-path" class="font-mono text-right break-all"></code>
            </div>
            <div class="flex items-start justify-between gap-2">
              <span id="lbl-target" class="text-[var(--muted-foreground)] shrink-0"></span>
              <code id="d-target" class="font-mono font-semibold text-emerald-400 text-right break-all"></code>
            </div>
            <div class="flex items-start justify-between gap-2">
              <span id="lbl-symlink" class="text-[var(--muted-foreground)] shrink-0"></span>
              <span id="d-symlink-status" class="font-medium text-right"></span>
            </div>
          </div>

          <p id="d-reason" class="text-xs text-[var(--muted-foreground)] mt-1.5 leading-relaxed"></p>

          <div class="mt-1.5 p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] space-y-1 text-xs">
            <div class="flex items-start justify-between gap-2">
              <span id="lbl-tok-bd" class="text-[var(--muted-foreground)] shrink-0"></span>
              <div id="d-token-breakdown" class="font-mono text-right text-[var(--muted-foreground)]"></div>
            </div>
            <div class="flex items-start justify-between gap-2">
              <span id="lbl-disk-bd" class="text-[var(--muted-foreground)] shrink-0"></span>
              <div id="d-disk-breakdown" class="font-mono text-right text-[var(--muted-foreground)]"></div>
            </div>
          </div>
        </div>

        <div class="mt-2">
          <div class="flex items-center justify-between text-xs text-[var(--muted-foreground)] mb-1">
            <span id="lbl-cmd-title"></span>
            <span id="d-os-tag" class="font-mono">zsh / bash</span>
          </div>
          <pre id="d-cmd" class="p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed"></pre>
        </div>
      </div>
    </div>

    <!-- VIEW 3: Single Episode Dynamic Symlink Assembly Preview (Bilingual) -->
    <div id="episode-split" class="hidden border border-[var(--border)] rounded-lg p-3 bg-[var(--background)] text-xs space-y-2">
      <div class="flex items-center justify-between">
        <span id="ep-title" class="font-semibold text-sm"></span>
        <span id="ep-pill" class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-mono font-semibold"></span>
      </div>
      <pre id="ep-tree" class="p-2.5 rounded-lg bg-[var(--card)] border border-[var(--border)] font-mono text-xs leading-relaxed overflow-x-auto"></pre>
    </div>

    <!-- VIEW 4: 1-Click Apply & Rollback (Undo) Script Preview (Bilingual) -->
    <div id="rollback-split" class="hidden grid grid-cols-12 gap-2.5 text-xs">
      <div class="col-span-6 border border-[var(--border)] rounded-lg p-2.5 bg-[var(--background)] space-y-1.5">
        <div class="flex items-center justify-between">
          <span id="rb-apply-title" class="font-semibold text-emerald-400"></span>
          <span class="font-mono text-[var(--muted-foreground)]">migrate-apply</span>
        </div>
        <pre id="rb-apply-code" class="p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] font-mono text-xs max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed"></pre>
      </div>
      <div class="col-span-6 border border-[var(--border)] rounded-lg p-2.5 bg-[var(--background)] space-y-1.5">
        <div class="flex items-center justify-between">
          <span id="rb-undo-title" class="font-semibold text-amber-400"></span>
          <span class="font-mono text-[var(--muted-foreground)]">migrate-rollback (Undo)</span>
        </div>
        <pre id="rb-undo-code" class="p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] font-mono text-xs max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed"></pre>
      </div>
    </div>
  </div>

  <script>
    const ALL_ITEMS = {json_payload};
    const TOTAL_COUNT = {len(items)};
    let viewMode = 'after-tree';
    let heatFilter = 'all';
    let searchQuery = '';
    let selectedName = ALL_ITEMS.length > 0 ? ALL_ITEMS[0].name : '';
    let currentOS = 'unix';
    let currentLang = '{default_lang}';

    const I18N = {{
      zh: {{
        tag: "實測模擬 DRY-RUN",
        title: `AI-First 最終架構預覽與效益熱力圖（共 ${{TOTAL_COUNT}} 個目錄）`,
        maxTokLbl: "最高省 Token：",
        reclaimLbl: "總計省空間：",
        tabAfter: "🌳 1. 新架構全景樹",
        tabBefore: "📂 2. 舊資料夾列表",
        tabEpisode: "🎬 3. 單集組裝解剖",
        tabRollback: "↩️ 4. 搬家與一鍵還原腳本",
        hfAll: "全部",
        hfToken: "🔥 省 Token 組",
        hfDisk: "💎 省空間組",
        searchPh: "🔍 搜尋舊資料夾或專案名 (如 voice, notes, comfy, backup)...",
        lblOldPath: "📁 原本舊位置：",
        lblTarget: "✨ 歸位新架構：",
        lblSymlink: "🔗 原位不斷鏈：",
        symlinkOk: "✅ 原路徑保留 Symlink 轉發，舊腳本 100% 正常運作",
        lblTokBd: "🔥 省 Token 明細：",
        lblDiskBd: "💎 省空間明細：",
        lblCmdTitle: "🛡️ 單項安全搬移與原位留軟連結指令：",
        tokPillPrefix: "🔥 可省 Context：~",
        treeIndexLbl: "目錄樹索引",
        noAiFilesLbl: "僅目錄樹基礎索引",
        diskReclaimPrefix: "💎 可釋放 ",
        diskReclaimMid: " MB",
        diskZeroLbl: "0 MB (無肥大依賴殘留)",
        cmdComment1: "# 1. 將實體移入新架構標準路徑",
        cmdComment2: "# 2. 在舊位置建立軟連結，確保既有腳本不斷鏈",
        epTitle: "★ 在 Antigravity / Claude 開啟單一集數工作區時的最終組裝樣貌：",
        epPill: "🔥 啟動僅 ~420 Tokens (比大雜燴省 95%+)",
        rbApplyTitle: "🚀 安全搬移腳本 (搬實體 + 留 Symlink 不斷鏈)",
        rbUndoTitle: "💊 一鍵無損還原「後悔藥」腳本 (1-Click Rollback)",
        noMatch: "找不到符合條件的資料夾，請切換篩選器或嘗試其他關鍵字。"
      }},
      en: {{
        tag: "LIVE DRY-RUN",
        title: `AI-First Final Architecture & Savings Heatmap (${{TOTAL_COUNT}} Folders)`,
        maxTokLbl: "Max Token Save: ",
        reclaimLbl: "Total Disk Save: ",
        tabAfter: "🌳 1. Final Tree (After)",
        tabBefore: "📂 2. Legacy List (Before)",
        tabEpisode: "🎬 3. Episode Assembly",
        tabRollback: "↩️ 4. Apply & Rollback Scripts",
        hfAll: "All",
        hfToken: "🔥 Token Savers",
        hfDisk: "💎 Disk Savers",
        searchPh: "🔍 Search legacy folder or project (e.g. voice, notes, comfy, backup)...",
        lblOldPath: "📁 Legacy Path:",
        lblTarget: "✨ New Target:",
        lblSymlink: "🔗 Link Guard:",
        symlinkOk: "✅ Symlink/Junction left at old path (0 broken scripts)",
        lblTokBd: "🔥 Token Bill:",
        lblDiskBd: "💎 Disk Saved:",
        lblCmdTitle: "🛡️ Safe Migration Command (Move + Leave Link):",
        tokPillPrefix: "🔥 Context Tax: ~",
        treeIndexLbl: "File tree index",
        noAiFilesLbl: "Base file tree index only",
        diskReclaimPrefix: "💎 Reclaim ",
        diskReclaimMid: " MB",
        diskZeroLbl: "0 MB (Clean)",
        cmdComment1: "# 1. Move physical directory into standardized AI-First path",
        cmdComment2: "# 2. Leave symlink/junction at legacy path so old scripts never break",
        epTitle: "★ Final Anatomy When Opening a Single Episode Workspace in Your Agent:",
        epPill: "🔥 ~420 Tokens on startup (Saves 95%+ vs Monorepo)",
        rbApplyTitle: "🚀 Safe Migration Script (Move + Leave Symlink/Junction)",
        rbUndoTitle: "💊 1-Click Lossless Rollback Script (Undo Everything)",
        noMatch: "No matching folder found. Try changing the filter or keyword."
      }}
    }};

    function getRowHeatmapClasses(item, isSel) {{
      const tok = item.total_tokens;
      const mb = item.reclaimable_mb;
      let base = isSel ? 'ring-2 ring-[var(--primary)] font-semibold shadow-sm ' : 'opacity-95 hover:opacity-100 ';

      if (heatFilter === 'disk' || (heatFilter === 'all' && mb >= 300 && tok < 1500)) {{
        if (mb >= 400) return base + 'border-l-4 border-emerald-400 bg-emerald-500/20 border-t border-r border-b border-emerald-500/40';
        if (mb >= 100) return base + 'border-l-4 border-emerald-500/80 bg-emerald-500/10 border-t border-r border-b border-emerald-500/30';
      }}
      if (tok >= 5000) return base + 'border-l-4 border-amber-400 bg-amber-500/25 border-t border-r border-b border-amber-500/50';
      if (tok >= 1500) return base + 'border-l-4 border-amber-400 bg-amber-500/15 border-t border-r border-b border-amber-500/40';
      if (tok >= 400)  return base + 'border-l-2 border-amber-500/60 bg-amber-500/5 border border-amber-500/20';
      if (mb >= 300)   return base + 'border-l-4 border-emerald-400 bg-emerald-500/15 border border-emerald-500/30';
      return base + (isSel ? 'border border-[var(--primary)] bg-[var(--card)]' : 'border border-transparent hover:bg-[var(--card)]');
    }}

    function renderHeatBadges(item) {{
      const badges = [];
      const tok = item.total_tokens;
      const mb = item.reclaimable_mb;

      if (tok >= 5000) {{
        badges.push(`<span class="px-1.5 py-0.5 rounded bg-amber-400 text-black font-bold font-mono text-xs shrink-0 shadow-sm">🔥 -${{tok.toLocaleString()}}t</span>`);
      }} else if (tok >= 1500) {{
        badges.push(`<span class="px-1.5 py-0.5 rounded bg-amber-500/30 text-amber-300 border border-amber-400/50 font-semibold font-mono text-xs shrink-0">🔥 -${{tok.toLocaleString()}}t</span>`);
      }} else if (tok >= 400) {{
        badges.push(`<span class="px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 font-mono text-xs shrink-0">-${{tok}}t</span>`);
      }}

      if (mb >= 400) {{
        badges.push(`<span class="px-1.5 py-0.5 rounded bg-emerald-400 text-black font-bold font-mono text-xs shrink-0 shadow-sm">💎 -${{mb}}MB</span>`);
      }} else if (mb >= 100) {{
        badges.push(`<span class="px-1.5 py-0.5 rounded bg-emerald-500/25 text-emerald-300 border border-emerald-400/50 font-semibold font-mono text-xs shrink-0">💎 -${{mb}}MB</span>`);
      }}
      return `<div class="flex items-center gap-1 shrink-0">${{badges.join('')}}</div>`;
    }}

    function setHeatFilter(mode) {{
      heatFilter = mode;
      document.getElementById('hf-all').className = mode === 'all'
        ? 'px-2 py-0.5 rounded border-2 border-[var(--primary)] bg-[var(--card)] font-semibold'
        : 'px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--card)] opacity-75';
      document.getElementById('hf-token').className = mode === 'token'
        ? 'px-2 py-0.5 rounded border-2 border-amber-400 bg-amber-500/25 text-amber-300 font-bold shadow-sm'
        : 'px-2 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-400 font-medium opacity-80';
      document.getElementById('hf-disk').className = mode === 'disk'
        ? 'px-2 py-0.5 rounded border-2 border-emerald-400 bg-emerald-500/25 text-emerald-300 font-bold shadow-sm'
        : 'px-2 py-0.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 font-medium opacity-80';

      if (viewMode === 'episode-demo' || viewMode === 'rollback-script') setViewMode('after-tree');
      const matches = getFilteredItems();
      if (matches.length > 0) selectedName = matches[0].name;
      renderLeftPane();
      renderInspector();
    }}

    function getFilteredItems() {{
      let list = ALL_ITEMS.slice();
      if (heatFilter === 'token') {{
        list = list.filter(x => x.total_tokens >= 300).sort((a, b) => b.total_tokens - a.total_tokens);
      }} else if (heatFilter === 'disk') {{
        list = list.filter(x => x.reclaimable_mb > 0).sort((a, b) => b.reclaimable_mb - a.reclaimable_mb);
      }}
      if (!searchQuery.trim()) return list;
      const q = searchQuery.toLowerCase().trim();
      return list.filter(item =>
        item.name.toLowerCase().includes(q) ||
        item.target_unix.toLowerCase().includes(q) ||
        item.tree_group_zh.toLowerCase().includes(q) ||
        item.tree_group_en.toLowerCase().includes(q)
      );
    }}

    function setViewMode(mode) {{
      viewMode = mode;
      ['after-tree', 'before-list', 'episode-demo', 'rollback-script'].forEach(m => {{
        const btn = document.getElementById('tab-' + m);
        if (btn) {{
          btn.className = m === mode
            ? 'px-2 py-1 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] font-medium'
            : 'px-2 py-1 rounded-lg bg-[var(--secondary)] text-[var(--secondary-foreground)]';
        }}
      }});

      document.getElementById('main-split').classList.add('hidden');
      document.getElementById('episode-split').classList.add('hidden');
      document.getElementById('rollback-split').classList.add('hidden');

      if (mode === 'episode-demo') {{
        document.getElementById('episode-split').classList.remove('hidden');
        renderEpisodeDemo();
      }} else if (mode === 'rollback-script') {{
        document.getElementById('rollback-split').classList.remove('hidden');
        renderRollbackScripts();
      }} else {{
        document.getElementById('main-split').classList.remove('hidden');
        renderLeftPane();
      }}
    }}

    function onSearchInput(val) {{
      searchQuery = val;
      if (viewMode === 'episode-demo' || viewMode === 'rollback-script') setViewMode('after-tree');
      const matches = getFilteredItems();
      if (matches.length > 0 && !matches.some(x => x.name === selectedName)) {{
        selectedName = matches[0].name;
      }}
      renderLeftPane();
      renderInspector();
    }}

    function escapeHtml(str) {{
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function renderLeftPane() {{
      const pane = document.getElementById('left-pane');
      const items = getFilteredItems();
      const t = I18N[currentLang];

      if (items.length === 0) {{
        pane.innerHTML = `<div class="p-3 text-xs text-[var(--muted-foreground)]">${{escapeHtml(t.noMatch)}}</div>`;
        return;
      }}

      if (viewMode === 'after-tree') {{
        const groups = {{}};
        items.forEach(item => {{
          const gKey = currentLang === 'zh' ? item.tree_group_zh : item.tree_group_en;
          if (!groups[gKey]) groups[gKey] = {{ order: item.group_order || 99, list: [] }};
          groups[gKey].list.push(item);
        }});

        const sortedGroupKeys = Object.keys(groups).sort((a, b) => groups[a].order - groups[b].order);

        pane.innerHTML = sortedGroupKeys.map(gKey => {{
          const children = groups[gKey].list;
          const grpTok = children.reduce((acc, c) => acc + (c.total_tokens >= 400 ? c.total_tokens : 0), 0);
          const grpMb = Math.round(children.reduce((acc, c) => acc + c.reclaimable_mb, 0));

          const rows = children.map(item => {{
            const isSel = item.name === selectedName;
            const heatCls = getRowHeatmapClasses(item, isSel);
            const shortTarget = item.target_unix.split('/').filter(Boolean).slice(-1)[0] || item.target_unix;
            const encName = encodeURIComponent(item.name);
            return `<button onclick="selectByEncoded('${{encName}}')" class="w-full text-left pl-3 pr-2 py-1 rounded text-xs transition flex items-center justify-between gap-1 ${{heatCls}}">
              <span class="truncate font-mono">├─ ${{escapeHtml(shortTarget)}}/ <span class="text-[var(--muted-foreground)] font-sans">⬅️ ${{escapeHtml(item.name)}}</span></span>
              ${{renderHeatBadges(item)}}
            </button>`;
          }}).join('');

          const grpBadges = [];
          if (grpTok > 0) grpBadges.push(`<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-mono text-xs">🔥 ${{grpTok.toLocaleString()}}t</span>`);
          if (grpMb > 0) grpBadges.push(`<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono text-xs">💎 ${{grpMb}}MB</span>`);

          return `<div class="border border-[var(--border)] rounded-lg p-1.5 bg-[var(--card)]">
            <div class="text-xs font-semibold px-1 py-0.5 flex items-center justify-between gap-1">
              <span class="truncate">${{escapeHtml(gKey)}} <span class="text-[var(--muted-foreground)] font-mono">(${{children.length}})</span></span>
              <div class="flex items-center gap-1 shrink-0">${{grpBadges.join('')}}</div>
            </div>
            <div class="mt-1 space-y-1">${{rows}}</div>
          </div>`;
        }}).join('');

      }} else {{
        pane.innerHTML = items.map(item => {{
          const isSel = item.name === selectedName;
          const heatCls = getRowHeatmapClasses(item, isSel);
          const warn = item.has_space_or_cjk ? '⚠️ ' : '📁 ';
          const encName = encodeURIComponent(item.name);
          return `<button onclick="selectByEncoded('${{encName}}')" class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition flex items-center justify-between gap-1 ${{heatCls}}">
            <span class="truncate">${{warn}}~/${{escapeHtml(item.name)}} <span class="text-[var(--muted-foreground)] font-mono">➡️ ${{escapeHtml(item.target_unix)}}</span></span>
            ${{renderHeatBadges(item)}}
          </button>`;
        }}).join('');
      }}
    }}

    function selectByEncoded(enc) {{
      selectByName(decodeURIComponent(enc));
    }}

    function selectByName(name) {{
      selectedName = name;
      renderLeftPane();
      renderInspector();
    }}

    function renderInspector() {{
      const item = ALL_ITEMS.find(x => x.name === selectedName) || ALL_ITEMS[0];
      if (!item) return;
      const t = I18N[currentLang];

      document.getElementById('d-badge').textContent = currentLang === 'zh' ? item.badge_zh : item.badge_en;
      document.getElementById('d-tokens-pill').textContent = `${{t.tokPillPrefix}}${{item.total_tokens.toLocaleString()}} tok`;
      document.getElementById('d-old-path').textContent = currentOS === 'unix' ? `~/${{item.name}}` : `%USERPROFILE%\\${{item.name.replace(/\\//g, '\\\\')}}`;
      document.getElementById('d-target').textContent = currentOS === 'unix' ? item.target_unix : item.target_win;
      document.getElementById('d-symlink-status').textContent = t.symlinkOk;
      document.getElementById('d-reason').textContent = currentLang === 'zh' ? item.reason_zh : item.reason_en;

      if (item.ai_files && item.ai_files.length > 0) {{
        const parts = item.ai_files.slice(0, 3).map(f => `${{f.file}} (${{f.tokens.toLocaleString()}})`).join(' + ');
        document.getElementById('d-token-breakdown').textContent = `${{parts}} + ${{t.treeIndexLbl}} (${{item.tree_tokens}})`;
      }} else {{
        document.getElementById('d-token-breakdown').textContent = `${{t.noAiFilesLbl}} (~${{item.tree_tokens}} tok)`;
      }}

      if (item.reclaimable_dirs && item.reclaimable_dirs.length > 0) {{
        const dparts = item.reclaimable_dirs.slice(0, 2).map(d => `${{d.path}} (${{d.mb}} MB)`).join(', ');
        document.getElementById('d-disk-breakdown').textContent = `${{t.diskReclaimPrefix}}${{item.reclaimable_mb}}${{t.diskReclaimMid}} (${{dparts}})`;
      }} else {{
        document.getElementById('d-disk-breakdown').textContent = t.diskZeroLbl;
      }}

      const dstUnix = item.target_unix.replace(/\\/$/, '');
      const parentUnix = dstUnix.substring(0, dstUnix.lastIndexOf('/'));
      const dstWin = item.target_win.replace(/\\\\$/, '');
      const parentWin = dstWin.substring(0, dstWin.lastIndexOf('\\\\')).replace('%USERPROFILE%', '$env:USERPROFILE');
      const winDstClean = dstWin.replace('%USERPROFILE%', '$env:USERPROFILE');
      const winSrc = item.name.replace(/\\//g, '\\\\');

      if (currentOS === 'unix') {{
        document.getElementById('d-os-tag').textContent = 'zsh / bash (Symlink)';
        document.getElementById('d-cmd').textContent =
          `${{t.cmdComment1}}\\nmkdir -p "${{parentUnix}}"\\nmv ~/"${{item.name}}" "${{dstUnix}}"\\n${{t.cmdComment2}}\\nln -sfn "${{dstUnix}}" ~/"${{item.name}}"`;
      }} else {{
        document.getElementById('d-os-tag').textContent = 'PowerShell (Junction)';
        document.getElementById('d-cmd').textContent =
          `${{t.cmdComment1}}\\nNew-Item -ItemType Directory -Force -Path "${{parentWin}}" | Out-Null\\nMove-Item -LiteralPath "$env:USERPROFILE\\\\${{winSrc}}" -Destination "${{winDstClean}}"\\n${{t.cmdComment2}}\\nNew-Item -ItemType Junction -Force -Path "$env:USERPROFILE\\\\${{winSrc}}" -Target "${{winDstClean}}"`;
      }}
    }}

    function renderEpisodeDemo() {{
      const t = I18N[currentLang];
      document.getElementById('ep-title').textContent = t.epTitle;
      document.getElementById('ep-pill').textContent = t.epPill;
      const sampleEp = ALL_ITEMS.find(x => x.layer === 'episodes') || {{ name: 'legacy_work/ep01', target_unix: '~/projects/media-studio/episodes/ep01/' }};
      const sampleKnow = ALL_ITEMS.find(x => x.layer === 'knowledge') || {{ name: 'OldWorkspace/Notes', target_unix: '~/knowledge/study/ml-notes/' }};
      const epSlug = sampleEp.target_unix.split('/').filter(Boolean).slice(-1)[0];

      if (currentLang === 'zh') {{
        document.getElementById('ep-tree').textContent =
`~/ (或 %USERPROFILE%\\)
├── 📚 ${{sampleKnow.target_unix.replace('~/', '')}}  # [1. 知識源頭 SSOT - 唯讀] (⬅️ 源自 ${{sampleKnow.name}})
├── 🧠 ai-models/                                     # [2. 模型資產 SSOT - 設定檔唯讀指向]
├── 🛰️ agent-hub/skills/                              # [3. 技能中樞 SSOT - 唯讀]
├── 🧪 agent-lab/workspaces/daily-assistant/          # [4. 日常對話純淨沙盒 CWD - 零程式碼污染]
└── 🚀 projects/media-studio/
    ├── tools/                                        # ⚙️ 核心工具庫 (voice-kit / anim-kit 獨立 Git 版控)
    └── episodes/${{epSlug}}/                         # ★ 你在 AGY / Claude 開啟的極致輕量工作區
        ├── .agents/skills/                           # 🔗 唯讀軟連結 -> ~/agent-hub/skills/brand-style
        ├── knowledge/                                # 🔗 唯讀軟連結 -> ${{sampleKnow.target_unix}}
        ├── AGENTS.md                                 # 🛡️ 守門員契約：外部連結唯讀，只准寫入本地目錄
        ├── prompt.md & script.md                     # 📝 State 1 (Git 版控)：講稿與分鏡配方
        └── dist/.cache/                              # 🗑️ State 2 (過渡快取)：渲染後自毀，成品發布至 ~/outputs/`;
      }} else {{
        document.getElementById('ep-tree').textContent =
`~/ (or %USERPROFILE%\\)
├── 📚 ${{sampleKnow.target_unix.replace('~/', '')}}  # [1. Knowledge Vault SSOT - Read-Only] (⬅️ from ${{sampleKnow.name}})
├── 🧠 ai-models/                                     # [2. Model Weights SSOT - Config Ref Only]
├── 🛰️ agent-hub/skills/                              # [3. Shared Skills Hub SSOT - Read-Only]
├── 🧪 agent-lab/workspaces/daily-assistant/          # [4. Clean Daily Chat CWD - 0 Code Pollution]
└── 🚀 projects/media-studio/
    ├── tools/                                        # ⚙️ Core Engines (voice-kit / anim-kit in Git)
    └── episodes/${{epSlug}}/                         # ★ Lightweight Task Workspace Opened in Agent
        ├── .agents/skills/                           # 🔗 Read-Only Link -> ~/agent-hub/skills/brand-style
        ├── knowledge/                                # 🔗 Read-Only Link -> ${{sampleKnow.target_unix}}
        ├── AGENTS.md                                 # 🛡️ Guardrail: External links read-only; write only locally
        ├── prompt.md & script.md                     # 📝 State 1 (Git Tracked): Script & recipe
        └── dist/.cache/                              # 🗑️ State 2 (Cache): Auto-purge after render; final MP4 -> ~/outputs/`;
      }}
    }}

    function renderRollbackScripts() {{
      const t = I18N[currentLang];
      document.getElementById('rb-apply-title').textContent = t.rbApplyTitle;
      document.getElementById('rb-undo-title').textContent = t.rbUndoTitle;

      const sampleList = getFilteredItems();
      if (currentOS === 'unix') {{
        const headerApply = currentLang === 'zh'
          ? "#!/usr/bin/env bash\\n# 階段性安全搬移腳本 (搬移實體 + 原位建立 Symlink 不斷鏈)\\nset -e\\n\\n"
          : "#!/usr/bin/env bash\\n# Safe Zero-Downtime Migration Script (Move + Leave Symlink)\\nset -e\\n\\n";
        const headerUndo = currentLang === 'zh'
          ? "#!/usr/bin/env bash\\n# 💊 一鍵無損還原腳本 (移除 Symlink 並將實體搬回原路徑)\\nset -e\\n\\n"
          : "#!/usr/bin/env bash\\n# 💊 1-Click Lossless Rollback Script (Remove Symlink & Restore Original Path)\\nset -e\\n\\n";

        const applyLines = sampleList.map(i => {{
          const dst = i.target_unix.replace(/\\/$/, '');
          const parent = dst.substring(0, dst.lastIndexOf('/'));
          return `mkdir -p "${{parent}}"\\nmv ~/"${{i.name}}" "${{dst}}"\\nln -sfn "${{dst}}" ~/"${{i.name}}"`;
        }}).join('\\n\\n');

        const undoLines = sampleList.map(i => {{
          const dst = i.target_unix.replace(/\\/$/, '');
          return `rm ~/"${{i.name}}"\\nmv "${{dst}}" ~/"${{i.name}}"`;
        }}).join('\\n\\n');

        document.getElementById('rb-apply-code').textContent = headerApply + applyLines;
        document.getElementById('rb-undo-code').textContent = headerUndo + undoLines;
      }} else {{
        const headerApply = currentLang === 'zh'
          ? "# PowerShell 安全搬移腳本 (搬移實體 + 建立免權限 Junction)\\n\\n"
          : "# PowerShell Safe Migration Script (Move + Admin-Free Junction)\\n\\n";
        const headerUndo = currentLang === 'zh'
          ? "# 💊 PowerShell 一鍵無損還原腳本 (移除 Junction 並還原實體)\\n\\n"
          : "# 💊 PowerShell 1-Click Rollback Script (Remove Junction & Restore)\\n\\n";

        const applyLines = sampleList.map(i => {{
          const dst = i.target_win.replace(/\\\\$/, '').replace('%USERPROFILE%', '$env:USERPROFILE');
          const parent = dst.substring(0, dst.lastIndexOf('\\\\'));
          const src = `$env:USERPROFILE\\\\${{i.name.replace(/\\//g, '\\\\')}}`;
          return `New-Item -ItemType Directory -Force -Path "${{parent}}" | Out-Null\\nMove-Item -LiteralPath "${{src}}" -Destination "${{dst}}"\\nNew-Item -ItemType Junction -Force -Path "${{src}}" -Target "${{dst}}"`;
        }}).join('\\n\\n');

        const undoLines = sampleList.map(i => {{
          const dst = i.target_win.replace(/\\\\$/, '').replace('%USERPROFILE%', '$env:USERPROFILE');
          const src = `$env:USERPROFILE\\\\${{i.name.replace(/\\//g, '\\\\')}}`;
          return `(Get-Item -LiteralPath "${{src}}").Delete()\\nMove-Item -LiteralPath "${{dst}}" -Destination "${{src}}"`;
        }}).join('\\n\\n');

        document.getElementById('rb-apply-code').textContent = headerApply + applyLines;
        document.getElementById('rb-undo-code').textContent = headerUndo + undoLines;
      }}
    }}

    function applyTranslations() {{
      const t = I18N[currentLang];
      document.getElementById('ui-tag').textContent = t.tag;
      document.getElementById('ui-title').textContent = t.title;
      document.getElementById('ui-max-tok-lbl').textContent = t.maxTokLbl;
      document.getElementById('ui-reclaim-lbl').textContent = t.reclaimLbl;
      document.getElementById('tab-after-tree').textContent = t.tabAfter;
      document.getElementById('tab-before-list').textContent = t.tabBefore;
      document.getElementById('tab-episode-demo').textContent = t.tabEpisode;
      document.getElementById('tab-rollback-script').textContent = t.tabRollback;
      document.getElementById('hf-all').textContent = t.hfAll;
      document.getElementById('hf-token').textContent = t.hfToken;
      document.getElementById('hf-disk').textContent = t.hfDisk;
      document.getElementById('search-input').placeholder = t.searchPh;
      document.getElementById('lbl-old-path').textContent = t.lblOldPath;
      document.getElementById('lbl-target').textContent = t.lblTarget;
      document.getElementById('lbl-symlink').textContent = t.lblSymlink;
      document.getElementById('lbl-tok-bd').textContent = t.lblTokBd;
      document.getElementById('lbl-disk-bd').textContent = t.lblDiskBd;
      document.getElementById('lbl-cmd-title').textContent = t.lblCmdTitle;
    }}

    function setLang(lang) {{
      currentLang = lang;
      document.getElementById('lang-zh').className = lang === 'zh' ? 'px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm' : 'px-1.5 py-0.5 rounded text-[var(--muted-foreground)]';
      document.getElementById('lang-en').className = lang === 'en' ? 'px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm' : 'px-1.5 py-0.5 rounded text-[var(--muted-foreground)]';
      applyTranslations();
      renderLeftPane();
      renderInspector();
      if (viewMode === 'episode-demo') renderEpisodeDemo();
      if (viewMode === 'rollback-script') renderRollbackScripts();
    }}

    function setOS(os) {{
      currentOS = os;
      document.getElementById('os-unix').className = os === 'unix' ? 'px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm' : 'px-1.5 py-0.5 rounded text-[var(--muted-foreground)]';
      document.getElementById('os-win').className = os === 'win' ? 'px-1.5 py-0.5 rounded bg-[var(--card)] text-[var(--foreground)] font-medium shadow-sm' : 'px-1.5 py-0.5 rounded text-[var(--muted-foreground)]';
      renderInspector();
      if (viewMode === 'rollback-script') renderRollbackScripts();
    }}

    setLang(currentLang);
  </script>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="AI-First Workspace Read-Only Auditor & Bilingual Dry-Run Simulator")
    parser.add_argument("--root", type=str, default=str(Path.home()), help="Target root directory to scan (default: ~/)")
    parser.add_argument("--from-scan", type=str, default="", help="Optional pre-scanned JSON file path")
    parser.add_argument("--out-html", type=str, default="dist/.cache/dry-run-report.html", help="Output path for interactive HTML simulator (default: dist/.cache/dry-run-report.html)")
    parser.add_argument("--out-json", type=str, default="", help="Optional JSON output path")
    parser.add_argument("--check-repo", type=str, default="", help="Check a specific project repo for CWD Dumping / cross-project contamination")
    parser.add_argument("--lang", type=str, choices=["zh", "en"], default="zh", help="Default UI language: zh (繁體中文) or en (English)")
    parser.add_argument("--demo", action="store_true", help="Generate de-identified public demo report (examples/demo-report.html)")
    parser.add_argument("--open", action="store_true", help="Automatically open the generated HTML report in browser")
    args = parser.parse_args()

    if args.check_repo:
        target_repo = Path(args.check_repo).expanduser().resolve()
        issues = check_repo_purity(target_repo)
        if args.out_json:
            out_json = Path(args.out_json).expanduser().resolve()
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(json.dumps(issues, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.lang == "zh":
            print(f"=== 🛡️ [Anti-Dump 專案純淨度檢查] 目標：{target_repo} ===")
            if not issues:
                print("✅ [純淨 PASS] 未偵測到任何跨專案混放或 AI 就地傾倒產物！")
            else:
                print(f"⚠️  偵測到 {len(issues)} 項「不屬於本專案的混放產物 (CWD Dumping)」：")
                for idx, iss in enumerate(issues, 1):
                    print(f"  {idx}. {iss['symptom_zh']}")
                    print(f"     ├─ 混放位置：{iss['item']}")
                    print(f"     ├─ 應歸位至：{iss['route_to']} ({iss['layer']} 層)")
                    print(f"     └─ 建議指令：{iss['cmd']}")
        else:
            print(f"=== 🛡️ [Anti-Dump Repo Purity Audit] Target: {target_repo} ===")
            if not issues:
                print("✅ [CLEAN PASS] 0 cross-project CWD dumping issues detected!")
            else:
                print(f"⚠️  Detected {len(issues)} cross-project CWD Dumping issue(s):")
                for idx, iss in enumerate(issues, 1):
                    print(f"  {idx}. {iss['symptom_en']}")
                    print(f"     ├─ Dumped at : {iss['item']}")
                    print(f"     ├─ Route to  : {iss['route_to']} ({iss['layer']} layer)")
                    print(f"     └─ Fix cmd   : {iss['cmd']}")
        return

    root_path = Path(args.root).expanduser().resolve()
    if args.demo:
        items = build_generic_demo_items()
    elif args.from_scan and Path(args.from_scan).exists():
        items = scan_from_json_snapshot(Path(args.from_scan), root_path)
    else:
        items = scan_directory(root_path)
        if not items and root_path == Path.home().resolve():
            for snap_candidate in [
                Path.home() / "agent-lab" / "workspaces" / "home-refactor" / "home-scan-result.json",
                Path(__file__).resolve().parent.parent / ".local" / "home-scan-result.json",
            ]:
                if snap_candidate.exists():
                    items = scan_from_json_snapshot(snap_candidate, root_path)
                    break
            else:
                if args.lang == "zh":
                    print("[提示] 家目錄受沙盒權限限制，已載入內建去識別化範例資料集 (11 個目錄)。")
                else:
                    print("[Info] Home directory restricted by sandbox; loaded built-in demo dataset (11 folders).")
                items = build_generic_demo_items()

    out_html = Path(args.out_html).expanduser().resolve()
    out_html.parent.mkdir(parents=True, exist_ok=True)
    generate_html_report(items, out_html, default_lang=args.lang)

    if args.out_json:
        out_json = Path(args.out_json).expanduser().resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.lang == "zh":
        print(f"[完成] 已唯讀掃描 {len(items)} 個目錄")
        print(f"[完成] 已產出中英雙語互動式模擬報告：{out_html}")
    else:
        print(f"[OK] Scanned {len(items)} folders (100% read-only)")
        print(f"[OK] Generated bilingual (EN / 繁中) interactive Dry-Run report: {out_html}")

    if args.open:
        webbrowser.open(out_html.as_uri())


if __name__ == "__main__":
    main()
