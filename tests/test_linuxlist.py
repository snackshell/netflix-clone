"""Tests for linuxlist. Run with: python3 -m unittest discover -s tests"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import linuxlist  # noqa: E402


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.entries = linuxlist.load_software()

    def test_dataset_loads_and_validates(self):
        self.assertGreater(len(self.entries), 50)

    def test_names_are_unique(self):
        names = [e["name"] for e in self.entries]
        self.assertEqual(len(names), len(set(names)))

    def test_every_category_is_used(self):
        used = {e["category"] for e in self.entries}
        self.assertEqual(used, set(linuxlist.CATEGORIES))


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.entries = linuxlist.load_software()

    def test_category_filter(self):
        result = linuxlist.filter_entries(self.entries, category="audio")
        self.assertTrue(result)
        self.assertTrue(all(e["category"] == "Audio" for e in result))

    def test_search_matches_tags(self):
        result = linuxlist.filter_entries(self.entries, search="tag editor")
        self.assertTrue(any(e["name"] == "Strawberry" for e in result))

    def test_search_requires_all_terms(self):
        result = linuxlist.filter_entries(self.entries, search="zzzznomatch")
        self.assertEqual(result, [])

    def test_foss_only(self):
        result = linuxlist.filter_entries(self.entries, foss_only=True)
        self.assertTrue(all(e["foss"] for e in result))
        self.assertNotIn("Obsidian", [e["name"] for e in result])

    def test_package_filter(self):
        result = linuxlist.filter_entries(self.entries, package="flatpak")
        self.assertTrue(result)
        self.assertTrue(all(e["package"] == "flatpak" for e in result))

    def test_results_are_sorted(self):
        result = linuxlist.filter_entries(self.entries)
        keys = [(e["category"].lower(), e["name"].lower()) for e in result]
        self.assertEqual(keys, sorted(keys))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.entries = linuxlist.load_software()

    def test_table_has_header_and_count(self):
        out = linuxlist.render_table(self.entries)
        self.assertIn("Name", out)
        self.assertIn("entries", out)

    def test_markdown_has_category_headings(self):
        out = linuxlist.render_markdown(self.entries)
        self.assertTrue(out.startswith("# Linux Software List"))
        self.assertIn("## Graphics", out)
        self.assertIn("**Krita**", out)

    def test_html_is_self_contained(self):
        out = linuxlist.render_html(self.entries)
        self.assertIn("<!DOCTYPE html>", out)
        self.assertIn("Krita", out)
        self.assertNotIn("<link", out)

    def test_html_escapes_content(self):
        entries = [
            {
                "name": "A & B",
                "category": "Utilities",
                "description": "<script>x</script>",
                "license": "MIT",
                "foss": True,
                "package": "apt",
                "tags": [],
            }
        ]
        out = linuxlist.render_html(entries)
        self.assertIn("A &amp; B", out)
        self.assertNotIn("<script>x</script>", out)

    def test_json_roundtrips(self):
        out = linuxlist.render_json(self.entries)
        self.assertEqual(len(json.loads(out)), len(self.entries))

    def test_empty_selection(self):
        self.assertIn("No matching", linuxlist.render_table([]))
        self.assertIn("No matching", linuxlist.render_html([]))


class ValidationTests(unittest.TestCase):
    def _write(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(payload, handle)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def _entry(self, **overrides):
        base = {
            "name": "Thing",
            "category": "Utilities",
            "description": "Does a thing.",
            "license": "MIT",
            "foss": True,
            "package": "apt",
            "tags": ["thing"],
        }
        base.update(overrides)
        return base

    def test_unknown_category_rejected(self):
        path = self._write([self._entry(category="Nonsense")])
        with self.assertRaises(linuxlist.DataError):
            linuxlist.load_software(path)

    def test_duplicate_name_rejected(self):
        path = self._write([self._entry(), self._entry()])
        with self.assertRaises(linuxlist.DataError):
            linuxlist.load_software(path)

    def test_missing_field_rejected(self):
        entry = self._entry()
        del entry["license"]
        path = self._write([entry])
        with self.assertRaises(linuxlist.DataError):
            linuxlist.load_software(path)

    def test_bad_json_rejected(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        handle.write("{not json")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        with self.assertRaises(linuxlist.DataError):
            linuxlist.load_software(handle.name)


class CliTests(unittest.TestCase):
    def test_main_returns_zero(self):
        self.assertEqual(linuxlist.main(["--foss", "--format", "json"]), 0)

    def test_main_reports_missing_dataset(self):
        self.assertEqual(linuxlist.main(["--data", "/nonexistent/x.json"]), 2)


if __name__ == "__main__":
    unittest.main()
