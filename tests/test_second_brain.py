"""
Automated verification tests for Second Brain system.
Uses standard library unittest.
Covers: loading, frontmatter parsing, search, tag filters, wikilinks,
empty results, creation, and persistence across service restarts.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from src.second_brain import SecondBrainService


class TestSecondBrainCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We test against the real repository notes
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.service = SecondBrainService(cls.repo_root)

    def test_01_notes_loading_and_count(self):
        """Verifies that at least 8 notes exist across categories."""
        notes = self.service.get_all_notes()
        self.assertGreaterEqual(len(notes), 8, "Expected at least 8 notes in repository")
        
        categories_found = {n["category"] for n in notes}
        self.assertIn("Inbox", categories_found)
        self.assertIn("Projects", categories_found)
        self.assertIn("Areas", categories_found)
        self.assertIn("Resources", categories_found)
        self.assertIn("Archives", categories_found)

    def test_02_frontmatter_parsing(self):
        """Verifies YAML frontmatter metadata extraction."""
        note = self.service.get_note("Карта знань з архітектури СКС")
        self.assertIsNotNone(note)
        self.assertEqual(note["title"], "Карта знань з архітектури СКС")
        self.assertEqual(note["status"], "active")
        self.assertIn("architecture", note["tags"])
        self.assertIn("moc", note["tags"])

    def test_03_search_by_keyword(self):
        """Verifies full-text and title keyword search."""
        # Search for hardware / tpu
        results = self.service.search_notes(query="систолічних")
        self.assertGreater(len(results), 0, "Should find note mentioning systolic arrays")
        self.assertTrue(any("прискорювачі" in r["title"].lower() for r in results))

    def test_04_filter_by_tag(self):
        """Verifies filtering notes by specific tag."""
        cloud_notes = self.service.search_notes(tag="cloud")
        self.assertGreaterEqual(len(cloud_notes), 1)
        for n in cloud_notes:
            self.assertIn("cloud", [t.lower() for t in n["tags"]])

    def test_05_wikilinks_and_backlinks(self):
        """Verifies wikilink parsing and backlink association."""
        # In our data, moc links to cloud service models and specialized memory
        cloud_note = self.service.get_note("Хмарні моделі обслуговування")
        self.assertIsNotNone(cloud_note)
        
        backlink_titles = [b["title"] for b in cloud_note["backlinks"]]
        self.assertIn("Карта знань з архітектури СКС", backlink_titles)
        self.assertIn("Ієрархія пам'яті спеціалізованих систем", backlink_titles)

    def test_06_empty_search_handling(self):
        """Verifies that non-existent query gracefully returns an empty list."""
        results = self.service.search_notes(query="non_existent_symbol_xyz_12345")
        self.assertEqual(results, [])

        tag_results = self.service.search_notes(tag="unknown_tag_09876")
        self.assertEqual(tag_results, [])

    def test_07_persistence_and_restart(self):
        """Simulates note creation, service shutdown, restart, and state persistence."""
        temp_dir = tempfile.mkdtemp(prefix="second_brain_test_")
        try:
            # Instance 1: Create note
            srv1 = SecondBrainService(temp_dir)
            created = srv1.create_note(
                category="Inbox",
                title="Тестова нотатка персистентності",
                content="Вміст для перевірки збереження після перезапуску сервера.",
                tags=["test", "persistence"],
                source="автотест"
            )
            self.assertIsNotNone(created)

            # Instance 2 (Simulating server restart reading from same path)
            srv2 = SecondBrainService(temp_dir)
            recovered = srv2.get_note("Тестова нотатка персистентності")
            self.assertIsNotNone(recovered, "Note should be persisted across service restarts")
            self.assertEqual(recovered["title"], "Тестова нотатка персистентності")
            self.assertEqual(recovered["category"], "Inbox")
            self.assertIn("persistence", recovered["tags"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_08_markdown_and_wikilink_html_rendering(self):
        """Verifies markdown formatting and interactive wikilink tag generation."""
        md = "## Заголовок\nТекст з [[Хмарні моделі обслуговування]] та **жирним** шрифтом."
        html = SecondBrainService.render_markdown_to_html(md)
        self.assertIn("<h2>Заголовок</h2>", html)
        self.assertIn("<strong>жирним</strong>", html)
        self.assertIn('class="wikilink"', html)
        self.assertIn('data-target="Хмарні моделі обслуговування"', html)


if __name__ == "__main__":
    unittest.main()
