#!/usr/bin/env python3
"""Fixture checks for the enterprise-search local query fixture."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fixture = load_module("enterprise_search_query_fixture_target", ROOT / "tools" / "enterprise_search_query_fixture.py")


class EnterpriseSearchQueryFixtureTest(unittest.TestCase):
    def test_ready_surface_passes_expected_hit_and_demotion_assertions(self):
        receipt = fixture.run_fixture(
            {
                "status": "ready",
                "fixture": {
                    "surface": "query_fixture",
                    "repo": "unionyxx/uniOS",
                    "queries": [
                        {"query": "unios evidence recovery"},
                        {"query": "unios demotion rule"},
                    ],
                },
            }
        )
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["repo"], "unionyxx/uniOS")
        self.assertEqual(receipt["assertion_count"], 2)
        self.assertTrue(all(assertion["top_hit_passed"] for assertion in receipt["assertions"]))
        self.assertTrue(all(assertion["demotion_passed"] for assertion in receipt["assertions"]))

    def test_blocked_surface_stays_blocked(self):
        receipt = fixture.run_fixture({"status": "blocked", "reason": "no current enterprise-search row"})
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("enterprise search surface probe", receipt["next_action"])


if __name__ == "__main__":
    unittest.main()
