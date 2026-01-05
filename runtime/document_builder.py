"""Document builder for incremental BMAD document construction.

This module provides utilities for building documents incrementally during
workflow execution, supporting append-only construction with section tracking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class DocumentSection:
    """A section within a document."""

    id: str
    title: str
    content: str
    level: int = 1
    completed: bool = False
    updated_at: Optional[str] = None


@dataclass
class Document:
    """A document being built incrementally."""

    name: str
    path: str
    title: str
    template: Optional[str] = None
    sections: List[DocumentSection] = field(default_factory=list)
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "title": self.title,
            "template": self.template,
            "sections": [
                {
                    "id": s.id,
                    "title": s.title,
                    "content": s.content,
                    "level": s.level,
                    "completed": s.completed,
                    "updated_at": s.updated_at,
                }
                for s in self.sections
            ],
            "frontmatter": self.frontmatter,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Document:
        """Create from dictionary."""
        sections = [
            DocumentSection(
                id=s["id"],
                title=s["title"],
                content=s["content"],
                level=s.get("level", 1),
                completed=s.get("completed", False),
                updated_at=s.get("updated_at"),
            )
            for s in data.get("sections", [])
        ]
        return cls(
            name=data["name"],
            path=data["path"],
            title=data["title"],
            template=data.get("template"),
            sections=sections,
            frontmatter=data.get("frontmatter", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def add_section(
        self,
        section_id: str,
        title: str,
        content: str,
        level: int = 1,
    ) -> None:
        """Add a new section to the document."""
        now = datetime.now(timezone.utc).isoformat()
        self.sections.append(
            DocumentSection(
                id=section_id,
                title=title,
                content=content,
                level=level,
                updated_at=now,
            )
        )
        self.updated_at = now

    def update_section(self, section_id: str, content: str) -> bool:
        """Update an existing section's content."""
        for section in self.sections:
            if section.id == section_id:
                section.content = content
                section.updated_at = datetime.now(timezone.utc).isoformat()
                self.updated_at = section.updated_at
                return True
        return False

    def append_to_section(self, section_id: str, content: str) -> bool:
        """Append content to an existing section."""
        for section in self.sections:
            if section.id == section_id:
                section.content += "\n\n" + content
                section.updated_at = datetime.now(timezone.utc).isoformat()
                self.updated_at = section.updated_at
                return True
        return False

    def mark_section_complete(self, section_id: str) -> bool:
        """Mark a section as complete."""
        for section in self.sections:
            if section.id == section_id:
                section.completed = True
                section.updated_at = datetime.now(timezone.utc).isoformat()
                self.updated_at = section.updated_at
                return True
        return False

    def get_section(self, section_id: str) -> Optional[DocumentSection]:
        """Get a section by ID."""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def render(self) -> str:
        """Render the document to markdown."""
        parts: List[str] = []

        # Frontmatter
        if self.frontmatter:
            parts.append("---")
            parts.append(yaml.dump(self.frontmatter, default_flow_style=False).strip())
            parts.append("---")
            parts.append("")

        # Title
        parts.append(f"# {self.title}")
        parts.append("")

        # Sections
        for section in self.sections:
            heading = "#" * (section.level + 1)
            parts.append(f"{heading} {section.title}")
            parts.append("")
            if section.content:
                parts.append(section.content)
                parts.append("")

        return "\n".join(parts)

    def save(self, base_dir: Path) -> Path:
        """Save the document to disk."""
        output_path = base_dir / self.path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.render(), encoding="utf-8")
        return output_path


class DocumentBuilder:
    """Builder for managing multiple documents in a workflow run."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.documents: Dict[str, Document] = {}
        self._load_state()

    def _state_path(self) -> Path:
        """Path to the document builder state file."""
        return self.run_dir / "documents_state.json"

    def _load_state(self) -> None:
        """Load document state from disk."""
        state_path = self._state_path()
        if state_path.exists():
            try:
                import json

                with open(state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, doc_data in data.get("documents", {}).items():
                    self.documents[name] = Document.from_dict(doc_data)
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save document state to disk."""
        import json

        state = {"documents": {name: doc.to_dict() for name, doc in self.documents.items()}}
        with open(self._state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def create_document(
        self,
        name: str,
        title: str,
        template: Optional[str] = None,
        frontmatter: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """Create a new document."""
        doc = Document(
            name=name,
            path=f"{name}.md",
            title=title,
            template=template,
            frontmatter=frontmatter or {},
        )
        self.documents[name] = doc
        self._save_state()
        return doc

    def get_document(self, name: str) -> Optional[Document]:
        """Get a document by name."""
        return self.documents.get(name)

    def get_or_create_document(
        self,
        name: str,
        title: str,
        template: Optional[str] = None,
    ) -> Document:
        """Get an existing document or create a new one."""
        if name in self.documents:
            return self.documents[name]
        return self.create_document(name, title, template)

    def add_content(
        self,
        document_name: str,
        section_id: str,
        section_title: str,
        content: str,
        level: int = 1,
    ) -> Document:
        """Add content to a document section.

        Creates the document if it doesn't exist.
        Creates the section if it doesn't exist.
        Appends to the section if it exists.
        """
        doc = self.get_or_create_document(document_name, document_name.replace("-", " ").title())

        existing = doc.get_section(section_id)
        if existing:
            doc.append_to_section(section_id, content)
        else:
            doc.add_section(section_id, section_title, content, level)

        self._save_state()
        return doc

    def save_all(self) -> List[Path]:
        """Save all documents to disk."""
        paths: List[Path] = []
        for doc in self.documents.values():
            path = doc.save(self.run_dir)
            paths.append(path)
        self._save_state()
        return paths

    def list_documents(self) -> List[str]:
        """List all document names."""
        return list(self.documents.keys())

    def get_progress(self) -> Dict[str, Any]:
        """Get progress summary for all documents."""
        progress: Dict[str, Any] = {}
        for name, doc in self.documents.items():
            total = len(doc.sections)
            completed = sum(1 for s in doc.sections if s.completed)
            progress[name] = {
                "total_sections": total,
                "completed_sections": completed,
                "percent": (completed / total * 100) if total > 0 else 0,
            }
        return progress


def parse_template(template_path: Path) -> List[DocumentSection]:
    """Parse a BMAD template file into sections.

    Templates typically have sections marked with headings.
    This extracts them as placeholders for content.
    """
    sections: List[DocumentSection] = []

    if not template_path.exists():
        return sections

    text = template_path.read_text(encoding="utf-8")

    # Skip frontmatter
    if text.startswith("---"):
        end_match = re.search(r"\n---\n", text[3:])
        if end_match:
            text = text[3 + end_match.end() :]

    # Parse headings
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    for i, match in enumerate(matches):
        level = len(match.group(1)) - 1  # Subtract 1 for document title
        title = match.group(2).strip()
        section_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

        # Get content until next heading
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Check if it's a placeholder
        is_placeholder = bool(
            re.search(r"\[.*?\]|\{.*?\}|TODO|TBD|PLACEHOLDER", content, re.IGNORECASE)
        )

        sections.append(
            DocumentSection(
                id=section_id,
                title=title,
                content="" if is_placeholder else content,
                level=max(1, level),
                completed=not is_placeholder and bool(content),
            )
        )

    return sections


def load_template_into_document(
    template_path: Path,
    document: Document,
) -> None:
    """Load a template's structure into a document."""
    sections = parse_template(template_path)
    document.template = str(template_path)
    for section in sections:
        if not document.get_section(section.id):
            document.sections.append(section)
