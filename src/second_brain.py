"""
Core business logic for the Second Brain application.
Manages markdown notes with YAML frontmatter, PARA categorization,
wikilinks resolving, search, and indexing using only Python standard library.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class SecondBrainService:
    CATEGORIES = ["Inbox", "Projects", "Areas", "Resources", "Archives"]

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir).resolve()
        self.notes_dir = self.base_dir / "notes"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensures all PARA directories exist."""
        for cat in self.CATEGORIES:
            (self.notes_dir / cat).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
        """
        Parses YAML frontmatter without external libraries.
        Returns (metadata_dict, body_text).
        """
        metadata: Dict[str, Any] = {
            "title": "",
            "created": "",
            "updated": "",
            "type": "resource",
            "status": "active",
            "tags": [],
            "source": ""
        }

        # Check for standard YAML frontmatter bounded by ---
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        if not match:
            # If no frontmatter, extract first # Header as title
            body = content.strip()
            first_line = body.split("\n")[0] if body else ""
            if first_line.startswith("# "):
                metadata["title"] = first_line.replace("# ", "").strip()
            return metadata, body

        raw_yaml, body = match.group(1), match.group(2)

        for line in raw_yaml.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip().lower()
                val = val.strip()

                # Remove enclosing quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1].strip()

                if key == "tags":
                    # Handle tags in format [a, b, c] or a, b
                    if val.startswith("[") and val.endswith("]"):
                        val = val[1:-1]
                    tags = [t.strip().strip("'\"") for t in val.split(",") if t.strip()]
                    metadata["tags"] = tags
                else:
                    metadata[key] = val

        return metadata, body.strip()

    @staticmethod
    def render_markdown_to_html(md_text: str) -> str:
        """
        Converts markdown text to HTML, resolving [[WikiLinks]] into interactive links.
        Uses pure regex for zero-dependency operation.
        """
        import html
        
        # 1. Escape basic HTML entities to avoid XSS
        lines = md_text.splitlines()
        rendered_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    rendered_lines.append("<pre><code>")
                else:
                    in_code_block = False
                    rendered_lines.append("</code></pre>")
                continue

            if in_code_block:
                rendered_lines.append(html.escape(line))
                continue

            # Process inline elements for regular text
            safe_line = html.escape(line)

            # Headers
            if safe_line.startswith("### "):
                rendered_lines.append(f"<h3>{safe_line[4:]}</h3>")
                continue
            elif safe_line.startswith("## "):
                rendered_lines.append(f"<h2>{safe_line[3:]}</h2>")
                continue
            elif safe_line.startswith("# "):
                rendered_lines.append(f"<h1>{safe_line[2:]}</h1>")
                continue

            # Unordered lists
            if safe_line.strip().startswith("- ") or safe_line.strip().startswith("* "):
                item = safe_line.strip()[2:]
                rendered_lines.append(f"<li>{item}</li>")
                continue

            # Empty lines
            if not safe_line.strip():
                rendered_lines.append("")
                continue

            # Paragraph lines
            rendered_lines.append(f"<p>{safe_line}</p>")

        html_text = "\n".join(rendered_lines)

        # Wrap adjacent <li> in <ul>
        html_text = re.sub(r"((?:<li>.*?</li>\s*)+)", r"<ul>\1</ul>", html_text)

        # Bold & Italic
        html_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_text)
        html_text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html_text)
        html_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", html_text)

        # Resolve [[WikiLinks]] or [[Target|Alias]]
        def replace_wikilink(match: re.Match) -> str:
            raw_link = match.group(1).strip()
            if "|" in raw_link:
                target, label = raw_link.split("|", 1)
            else:
                target, label = raw_link, raw_link
            target_clean = html.unescape(target.strip())
            label_clean = label.strip()
            return f'<a href="javascript:void(0)" class="wikilink" data-target="{html.escape(target_clean)}">🔗 {label_clean}</a>'

        html_text = re.sub(r"\[\[(.*?)\]\]", replace_wikilink, html_text)

        return html_text

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Scans notes directory and returns parsed notes metadata with file paths."""
        notes = []
        for cat in self.CATEGORIES:
            cat_dir = self.notes_dir / cat
            if not cat_dir.exists():
                continue

            for file_path in cat_dir.glob("*.md"):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    metadata, body = self.parse_frontmatter(content)
                    
                    # Extract outgoing [[wikilinks]]
                    links = re.findall(r"\[\[(.*?)\]\]", body)
                    cleaned_links = [l.split("|")[0].strip() for l in links]

                    # Title fallback
                    title = metadata.get("title") or file_path.stem

                    notes.append({
                        "id": f"{cat}/{file_path.name}",
                        "filename": file_path.name,
                        "category": cat,
                        "title": title,
                        "created": metadata.get("created", ""),
                        "updated": metadata.get("updated", ""),
                        "type": metadata.get("type", "resource"),
                        "status": metadata.get("status", "active"),
                        "tags": metadata.get("tags", []),
                        "source": metadata.get("source", ""),
                        "links": cleaned_links,
                        "snippet": body[:180].replace("\n", " ").strip() + ("..." if len(body) > 180 else ""),
                        "path": str(file_path.relative_to(self.base_dir)).replace("\\", "/")
                    })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
        return notes

    def get_note(self, note_id_or_title: str) -> Optional[Dict[str, Any]]:
        """Finds note by relative ID ('Inbox/name.md') or by title."""
        all_notes = self.get_all_notes()
        
        # Check by ID
        for note in all_notes:
            if note["id"].lower() == note_id_or_title.lower() or note["title"].lower() == note_id_or_title.lower():
                full_path = self.base_dir / note["path"]
                content = full_path.read_text(encoding="utf-8")
                metadata, body = self.parse_frontmatter(content)
                html_body = self.render_markdown_to_html(body)
                
                # Find backlinks (notes pointing to this note)
                backlinks = [
                    {"id": n["id"], "title": n["title"], "category": n["category"]}
                    for n in all_notes
                    if any(target.lower() == note["title"].lower() for target in n.get("links", []))
                ]

                res = dict(note)
                res["raw_content"] = content
                res["body_markdown"] = body
                res["body_html"] = html_body
                res["backlinks"] = backlinks
                return res
        return None

    def search_notes(self, query: str = "", category: str = "", tag: str = "") -> List[Dict[str, Any]]:
        """Filters notes by query (title, content, tags), category, and tag."""
        notes = self.get_all_notes()
        results = []

        query = query.strip().lower()
        category = category.strip()
        tag = tag.strip().lower()

        for note in notes:
            # Filter by Category
            if category and category.lower() != "all" and note["category"].lower() != category.lower():
                continue

            # Filter by Tag
            if tag and tag.lower() != "all":
                note_tags = [t.lower() for t in note.get("tags", [])]
                if tag not in note_tags:
                    continue

            # Search query
            if query:
                # Read full content for deep search
                full_path = self.base_dir / note["path"]
                content = full_path.read_text(encoding="utf-8").lower() if full_path.exists() else ""
                title = note["title"].lower()
                tags_str = " ".join(note.get("tags", [])).lower()

                if query not in title and query not in tags_str and query not in content:
                    continue

            results.append(note)

        # Sort by updated date descending
        results.sort(key=lambda n: n.get("updated", "") or n.get("created", ""), reverse=True)
        return results

    def create_note(self, category: str, title: str, content: str, tags: List[str] = None, source: str = "") -> Dict[str, Any]:
        """Creates a new note file with proper frontmatter in the specified category."""
        if category not in self.CATEGORIES:
            category = "Inbox"

        today = datetime.now().strftime("%Y-%m-%d")
        tags = tags or ["draft"]
        source = source or "власний запис"

        # Sanitize filename
        safe_filename = re.sub(r'[\\/*?:"<>| ]', "-", title.lower().strip())
        safe_filename = re.sub(r"-+", "-", safe_filename).strip("-") or "untitled"
        filename = f"{safe_filename}.md"

        file_path = self.notes_dir / category / filename
        counter = 1
        while file_path.exists():
            file_path = self.notes_dir / category / f"{safe_filename}-{counter}.md"
            counter += 1

        formatted_tags = ", ".join(tags)
        full_markdown = f"""---
title: "{title}"
created: {today}
updated: {today}
type: {category.lower()[:-1] if category.endswith('s') else category.lower()}
status: active
tags: [{formatted_tags}]
source: "{source}"
---

# {title}

{content.strip()}
"""
        file_path.write_text(full_markdown, encoding="utf-8")
        note_id = f"{category}/{file_path.name}"
        return self.get_note(note_id) or {"id": note_id, "title": title}

    def update_note(self, note_id: str, new_content: str) -> Optional[Dict[str, Any]]:
        """Updates content and the 'updated' timestamp of a note."""
        full_path = self.notes_dir / note_id
        if not full_path.exists():
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        metadata, body = self.parse_frontmatter(new_content)
        metadata["updated"] = today

        # Reconstruct markdown with updated frontmatter
        tags_str = ", ".join(metadata.get("tags", []))
        full_text = f"""---
title: "{metadata.get('title', 'Без назви')}"
created: {metadata.get('created', today)}
updated: {today}
type: {metadata.get('type', 'resource')}
status: {metadata.get('status', 'active')}
tags: [{tags_str}]
source: "{metadata.get('source', '')}"
---

{body}
"""
        full_path.write_text(full_text, encoding="utf-8")
        return self.get_note(note_id)

    def get_categories_stats(self) -> Dict[str, int]:
        """Returns note counts per PARA category."""
        counts = {cat: 0 for cat in self.CATEGORIES}
        for note in self.get_all_notes():
            cat = note.get("category")
            if cat in counts:
                counts[cat] += 1
        return counts

    def get_all_tags(self) -> Dict[str, int]:
        """Returns unique tags and their frequencies."""
        tags_count: Dict[str, int] = {}
        for note in self.get_all_notes():
            for t in note.get("tags", []):
                t_lower = t.lower()
                tags_count[t_lower] = tags_count.get(t_lower, 0) + 1
        return dict(sorted(tags_count.items(), key=lambda x: (-x[1], x[0])))

    def get_graph_data(self) -> Dict[str, Any]:
        """Returns nodes and edges for knowledge graph visualization."""
        notes = self.get_all_notes()
        nodes = []
        node_ids = set()

        for n in notes:
            nodes.append({
                "id": n["title"],
                "category": n["category"],
                "path": n["id"]
            })
            node_ids.add(n["title"].lower())

        edges = []
        for n in notes:
            src = n["title"]
            for target in n.get("links", []):
                edges.append({
                    "source": src,
                    "target": target,
                    "exists": target.lower() in node_ids
                })

        return {"nodes": nodes, "edges": edges}
