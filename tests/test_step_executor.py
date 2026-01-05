"""Tests for BMAD step executor and document builder."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.document_builder import (
    Document,
    DocumentBuilder,
    parse_template,
)
from runtime.step_executor import (
    BmadStepExecutor,
    ConversationState,
    ConversationTurn,
    StepFileContent,
    build_step_prompt,
    find_step_files,
    parse_step_file,
)


class TestConversationState(unittest.TestCase):
    """Tests for ConversationState."""

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization round-trip."""
        state = ConversationState(
            run_id="test-123",
            workflow="prd",
            current_step_idx=2,
            current_step_id="step-03",
            steps_completed=["step-01", "step-02"],
            turns=[
                ConversationTurn(
                    role="user",
                    content="Hello",
                    step_id="step-01",
                    timestamp="2024-01-01T00:00:00Z",
                ),
                ConversationTurn(
                    role="assistant",
                    content="Hi there",
                    step_id="step-01",
                    timestamp="2024-01-01T00:00:01Z",
                ),
            ],
            documents={"prd.md": "# PRD\n\nContent here"},
            waiting_for_input=True,
            last_prompt="What would you like to add?",
        )

        data = state.to_dict()
        restored = ConversationState.from_dict(data)

        self.assertEqual(restored.run_id, "test-123")
        self.assertEqual(restored.workflow, "prd")
        self.assertEqual(restored.current_step_idx, 2)
        self.assertEqual(restored.current_step_id, "step-03")
        self.assertEqual(restored.steps_completed, ["step-01", "step-02"])
        self.assertEqual(len(restored.turns), 2)
        self.assertEqual(restored.turns[0].content, "Hello")
        self.assertEqual(restored.documents["prd.md"], "# PRD\n\nContent here")
        self.assertTrue(restored.waiting_for_input)

    def test_empty_state(self) -> None:
        """Test empty state creation."""
        state = ConversationState(
            run_id="empty",
            workflow="test",
            current_step_idx=0,
            current_step_id="step-01",
        )

        data = state.to_dict()
        self.assertEqual(data["steps_completed"], [])
        self.assertEqual(data["turns"], [])
        self.assertEqual(data["documents"], {})


class TestParseStepFile(unittest.TestCase):
    """Tests for step file parsing."""

    def test_parse_step_file_with_frontmatter(self) -> None:
        """Test parsing step file with YAML frontmatter."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""---
name: Initialize PRD
outputFile: prd.md
template: prd-template.md
---

# Step 01: Initialize PRD

**Your Role:** Product Manager facilitator

**Conversation Flow:**
1. Welcome the user
2. Ask about their product vision
3. Record key points

**Output:** prd.md
""")
            f.flush()
            path = Path(f.name)

        try:
            content = parse_step_file(path)
            self.assertEqual(content.title, "Step 01: Initialize PRD")
            self.assertIn("Product Manager", content.role)
            self.assertIn("Welcome the user", content.conversation_flow)
            self.assertIn("prd.md", content.outputs)
        finally:
            path.unlink()

    def test_parse_step_file_extracts_instructions(self) -> None:
        """Test that numbered instructions are extracted."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""# Step 02: Discovery

**Instructions:**
1. First do this
2. Then do that
3. Finally complete this

- Also this bullet point
""")
            f.flush()
            path = Path(f.name)

        try:
            content = parse_step_file(path)
            self.assertGreater(len(content.instructions), 0)
            self.assertIn("First do this", content.instructions)
        finally:
            path.unlink()


class TestFindStepFiles(unittest.TestCase):
    """Tests for step file discovery."""

    def test_find_step_files_in_steps_dir(self) -> None:
        """Test finding step files in steps subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_dir = Path(tmpdir)
            steps_dir = workflow_dir / "steps"
            steps_dir.mkdir()

            (steps_dir / "step-01-init.md").write_text("# Step 1")
            (steps_dir / "step-02-discovery.md").write_text("# Step 2")
            (steps_dir / "step-03-complete.md").write_text("# Step 3")
            (steps_dir / "readme.md").write_text("Not a step")

            files = find_step_files(workflow_dir)

            self.assertEqual(len(files), 3)
            self.assertEqual(files[0].stem, "step-01-init")
            self.assertEqual(files[1].stem, "step-02-discovery")
            self.assertEqual(files[2].stem, "step-03-complete")

    def test_find_step_files_sorted_numerically(self) -> None:
        """Test that step files are sorted numerically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_dir = Path(tmpdir)
            steps_dir = workflow_dir / "steps"
            steps_dir.mkdir()

            (steps_dir / "step-10-ten.md").write_text("# 10")
            (steps_dir / "step-02-two.md").write_text("# 2")
            (steps_dir / "step-01-one.md").write_text("# 1")

            files = find_step_files(workflow_dir)

            self.assertEqual(files[0].stem, "step-01-one")
            self.assertEqual(files[1].stem, "step-02-two")
            self.assertEqual(files[2].stem, "step-10-ten")


class TestBuildStepPrompt(unittest.TestCase):
    """Tests for prompt building."""

    def test_build_step_prompt_includes_role(self) -> None:
        """Test that prompt includes role information."""
        content = StepFileContent(
            frontmatter={},
            title="Test Step",
            role="Business Analyst",
            instructions=["Do thing 1", "Do thing 2"],
            conversation_flow=["Ask question", "Record answer"],
            outputs=["output.md"],
            templates=["template.md"],
            next_step=None,
            raw_content="",
        )

        state = ConversationState(
            run_id="test",
            workflow="test",
            current_step_idx=0,
            current_step_id="step-01",
        )

        prompt = build_step_prompt(content, state, "User input here")

        self.assertIn("Test Step", prompt)
        self.assertIn("Business Analyst", prompt)
        self.assertIn("User input here", prompt)
        self.assertIn("output.md", prompt)

    def test_build_step_prompt_includes_conversation_history(self) -> None:
        """Test that prompt includes recent conversation turns."""
        content = StepFileContent(
            frontmatter={},
            title="Test Step",
            role="Assistant",
            instructions=[],
            conversation_flow=[],
            outputs=[],
            templates=[],
            next_step=None,
            raw_content="",
        )

        state = ConversationState(
            run_id="test",
            workflow="test",
            current_step_idx=0,
            current_step_id="step-01",
            turns=[
                ConversationTurn(
                    role="user",
                    content="Previous question",
                    step_id="step-01",
                    timestamp="2024-01-01T00:00:00Z",
                ),
            ],
        )

        prompt = build_step_prompt(content, state, None)

        self.assertIn("Previous conversation", prompt)
        self.assertIn("Previous question", prompt)


class TestDocument(unittest.TestCase):
    """Tests for Document class."""

    def test_add_and_get_section(self) -> None:
        """Test adding and retrieving sections."""
        doc = Document(name="test", path="test.md", title="Test Doc")
        doc.add_section("intro", "Introduction", "Intro content", level=1)
        doc.add_section("body", "Body", "Body content", level=2)

        intro = doc.get_section("intro")
        self.assertIsNotNone(intro)
        self.assertEqual(intro.title, "Introduction")
        self.assertEqual(intro.content, "Intro content")

    def test_append_to_section(self) -> None:
        """Test appending content to a section."""
        doc = Document(name="test", path="test.md", title="Test Doc")
        doc.add_section("notes", "Notes", "First note")
        doc.append_to_section("notes", "Second note")

        section = doc.get_section("notes")
        self.assertIn("First note", section.content)
        self.assertIn("Second note", section.content)

    def test_render_markdown(self) -> None:
        """Test rendering document to markdown."""
        doc = Document(
            name="test",
            path="test.md",
            title="Test Document",
            frontmatter={"author": "Test"},
        )
        doc.add_section("intro", "Introduction", "Hello world", level=1)

        rendered = doc.render()

        self.assertIn("---", rendered)
        self.assertIn("author: Test", rendered)
        self.assertIn("# Test Document", rendered)
        self.assertIn("## Introduction", rendered)
        self.assertIn("Hello world", rendered)

    def test_save_document(self) -> None:
        """Test saving document to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = Document(name="test", path="output/test.md", title="Test")
            doc.add_section("content", "Content", "Hello")

            path = doc.save(Path(tmpdir))

            self.assertTrue(path.exists())
            content = path.read_text()
            self.assertIn("# Test", content)


class TestDocumentBuilder(unittest.TestCase):
    """Tests for DocumentBuilder class."""

    def test_create_and_get_document(self) -> None:
        """Test creating and retrieving documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DocumentBuilder(Path(tmpdir))
            builder.create_document("prd", "Product Requirements")

            doc = builder.get_document("prd")
            self.assertIsNotNone(doc)
            self.assertEqual(doc.title, "Product Requirements")

    def test_add_content_creates_document(self) -> None:
        """Test that add_content creates document if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DocumentBuilder(Path(tmpdir))
            builder.add_content("new-doc", "intro", "Introduction", "Content here")

            doc = builder.get_document("new-doc")
            self.assertIsNotNone(doc)
            section = doc.get_section("intro")
            self.assertIn("Content here", section.content)

    def test_save_all_documents(self) -> None:
        """Test saving all documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DocumentBuilder(Path(tmpdir))
            builder.create_document("doc1", "Document 1")
            builder.create_document("doc2", "Document 2")

            paths = builder.save_all()

            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertTrue(path.exists())

    def test_get_progress(self) -> None:
        """Test progress tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DocumentBuilder(Path(tmpdir))
            doc = builder.create_document("test", "Test")
            doc.add_section("s1", "Section 1", "Content")
            doc.add_section("s2", "Section 2", "Content")
            doc.mark_section_complete("s1")

            progress = builder.get_progress()

            self.assertEqual(progress["test"]["total_sections"], 2)
            self.assertEqual(progress["test"]["completed_sections"], 1)
            self.assertEqual(progress["test"]["percent"], 50.0)


class TestBmadStepExecutor(unittest.TestCase):
    """Tests for BmadStepExecutor."""

    def test_executor_creates_conversation_state(self) -> None:
        """Test that executor creates conversation state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            executor = BmadStepExecutor()

            manifest = {
                "run_id": "test-run",
                "workflow": {"module": "bmm", "workflow": "prd"},
                "steps": [],
            }

            step = {"step_id": "step-01", "name": "Init", "status": "pending"}
            context = {"manifest": manifest, "run_dir": run_dir}

            executor.execute(step, context)

            # When BMAD-METHOD is not found, result contains error
            result = step.get("result", {})
            # Either step_file is present (BMAD-METHOD found) or error is present
            self.assertTrue(
                "step_file" in result or "error" in result,
                f"Expected step_file or error in result: {result}",
            )

    def test_executor_handles_missing_workflow(self) -> None:
        """Test graceful handling of missing workflow directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            executor = BmadStepExecutor(bmad_root=Path("/nonexistent"))

            manifest = {
                "run_id": "test",
                "workflow": {"module": "fake", "workflow": "fake"},
            }

            step = {"step_id": "step-01", "status": "pending"}
            context = {"manifest": manifest, "run_dir": run_dir}

            executor.execute(step, context)

            self.assertEqual(step["status"], "completed")
            self.assertIn("error", step.get("result", {}))


class TestParseTemplate(unittest.TestCase):
    """Tests for template parsing."""

    def test_parse_template_extracts_sections(self) -> None:
        """Test that template sections are extracted."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""---
title: PRD Template
---

# Product Requirements Document

## Executive Summary
[TODO: Write summary]

## Problem Statement
Describe the problem here.

## User Stories
[Placeholder for user stories]
""")
            f.flush()
            path = Path(f.name)

        try:
            sections = parse_template(path)

            self.assertGreater(len(sections), 0)
            # Find executive summary section
            summary = next((s for s in sections if "summary" in s.id.lower()), None)
            self.assertIsNotNone(summary)
            self.assertFalse(summary.completed)  # Has placeholder
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
