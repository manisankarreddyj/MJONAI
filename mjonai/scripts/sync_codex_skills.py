"""
Module: scripts/sync_codex_skills.py
Purpose: 从 skills/*.md 生成 Codex skill 包 (codex-skills/*/SKILL.md)。

Clean-room reimplementation from ai-berkshire/scripts/sync-codex-skills.py (MIT).
同步维护：skills/*.md 是单一事实源；codex-skills/ 由脚本自动生成。
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "mjonai" / "skills"
CODEX_SKILLS_DIR = REPO_ROOT / "codex-skills"


def _slug(name: str) -> str:
    """将 skill 名称转为目录名。"""
    return name.lower().replace(" ", "-").replace("/", "-")


def _extract_frontmatter(content: str) -> dict:
    """提取 Markdown frontmatter。"""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            try:
                import yaml
                return yaml.safe_load(content[3:end])
            except Exception:
                pass
    return {}


def _extract_description(content: str) -> str:
    """提取技能描述（第一段非空文本）。"""
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200] + ("..." if len(line) > 200 else "")
    return ""


def _parse_skill_markdown(path: Path) -> dict:
    """解析 skill Markdown 文件。"""
    content = path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(content)
    name = path.stem.replace("_", " ").title()
    if "name" in fm:
        name = fm["name"]
    return {
        "name": name,
        "slug": _slug(path.stem),
        "description": fm.get("description", _extract_description(content)),
        "category": fm.get("category", "General"),
        "version": fm.get("version", "1.0"),
        "tags": fm.get("tags", []),
        "content": content,
    }


def _render_codex_skill(skill: dict) -> str:
    """渲染 Codex skill 的 SKILL.md 内容。"""
    lines = []
    lines.append(f"# {skill['name']}")
    lines.append("")
    lines.append(skill["description"])
    lines.append("")
    lines.append("## Category")
    lines.append(f"`{skill['category']}`")
    lines.append("")
    lines.append("## Tags")
    lines.append("`" + "`, `".join(skill["tags"]) + "`" if skill["tags"] else "`(none)`")
    lines.append("")
    lines.append("## Usage")
    lines.append("")
    lines.append("```text")
    lines.append(f"使用 {skill['name'].lower()} 研究 {{公司名}}")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("*Generated from MJONAI skills/*.md — do not edit directly.*")
    return "\n".join(lines)


def sync_codex_skills():
    """主同步函数：skills/ -> codex-skills/"""
    if not SKILLS_DIR.exists():
        print(f"Skills directory not found: {SKILLS_DIR}", file=sys.stderr)
        return 1

    # 清理并重建 codex-skills 目录
    if CODEX_SKILLS_DIR.exists():
        shutil.rmtree(CODEX_SKILLS_DIR)
    CODEX_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    skills_processed = 0
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        skill = _parse_skill_markdown(md_file)
        skill_dir = CODEX_SKILLS_DIR / skill["slug"]
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = _render_codex_skill(skill)
        (skill_dir / "SKILL.md").write_text(skill["content"], encoding="utf-8")

        # 创建 skill.json 元数据
        meta = {
            "name": skill["name"],
            "slug": skill["slug"],
            "description": skill["description"],
            "category": skill["category"],
            "version": skill["version"],
            "tags": skill["tags"],
        }
        (skill_dir / "skill.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

        skills_processed += 1
        print(f"  ✓ {skill['name']} -> {skill_dir}")

    print(f"\n✅ Synced {skills_processed} skills to {CODEX_SKILLS_DIR}")
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sync MJONAI skills to Codex skills")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no files will be written")
        return 0

    return sync_codex_skills()


if __name__ == "__main__":
    sys.exit(main())