#!/usr/bin/env python3
"""Focused fixture checks for repo-pattern classifier and eligibility reader."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


classifier = load_module("repo_pattern_classifier_fixture_target", ROOT / "tools" / "repo_pattern_classifier.py")
eligibility = load_module("repo_pattern_eligibility_fixture_target", ROOT / "tools" / "repo_pattern_eligibility_reader.py")
action_selector = load_module("repo_pattern_action_fixture_target", ROOT / "tools" / "repo_pattern_action_selector.py")
query_fixture = load_module("enterprise_search_query_fixture_target", ROOT / "tools" / "enterprise_search_query_fixture.py")
robotics_probe = load_module("robotics_path_probe_fixture_target", ROOT / "tools" / "robotics_path_probe.py")


def fixture_markdown(repos: list[tuple[str, int, str, str, str, str]]) -> str:
    chunks = []
    for repo, stars, language, summary, topics, body in repos:
        chunks.append(
            "\n".join(
                [
                    f"### {repo} ({stars} stars, {language})",
                    summary,
                    f"Topics: {topics}",
                    f"https://github.com/{repo}",
                    "",
                    body,
                ]
            )
        )
    return "\n\n---\n\n".join(chunks)


class RepoPatternFixtureTest(unittest.TestCase):
    def compile_fixture(self, repos: list[tuple[str, int, str, str, str, str]]):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trending-repos.md"
            path.write_text(fixture_markdown(repos), encoding="utf-8")
            entries = classifier.parse_repos(path.read_text(encoding="utf-8"))
            return classifier.compile_rows(entries, path)

    def test_game_runtime_rows_are_actionable(self):
        rows = self.compile_fixture(
            [
                ("flame-engine/flame", 10000, "Dart", "A minimalist Flutter game engine", "game-engine, flutter", "game engine runtime"),
                ("MonoGame/MonoGame", 11000, "C#", "One framework for creating games", "game-development", "runtime and content pipeline"),
                ("hajimehoshi/ebiten", 12000, "Go", "Ebitengine is a dead simple 2D game engine", "game-engine", "rendering and input runtime"),
                ("luanti-org/luanti", 13000, "C++", "Voxel game engine", "game-engine, voxel", "world runtime and mods"),
                ("skypjack/entt", 14000, "C++", "Gaming meets modern C++", "ecs, gamedev", "entity component system runtime"),
            ]
        )
        self.assertEqual([row["admission_status"] for row in rows], ["admitted"] * 5)
        custody_types = {row["repo"]: row["custody_type"] for row in rows}
        self.assertEqual(custody_types["skypjack/entt"], "entity_component_runtime_custody")
        self.assertEqual(custody_types["flame-engine/flame"], "game_runtime_custody")
        decisions = [eligibility.decide(row) for row in rows]
        self.assertEqual({decision["eligibility"] for decision in decisions}, {"current_infrastructure"})

    def test_current_go_rows_are_actionable(self):
        rows = self.compile_fixture(
            [
                ("flamego/flamego", 621, "Go", "A fantastic modular Go web framework with routing", "dependency-injection, web-framework", "go get github.com/flamego/flamego"),
                ("github/gh-aw", 4424, "Go", "GitHub Agentic Workflows", "actions, codex", "run agentic workflows in GitHub Actions; retired releases due to billing bug"),
                ("electrikmilk/cherri", 1487, "Go", "Siri Shortcuts Programming Language", "compiler, domain-specific-language", "Apple Shortcuts DSL compiler"),
                ("Wei-Shaw/sub2api", 18229, "Go", "AI API Gateway Platform for Subscription Quota Distribution", "claude, openai, gemini", "Docker PostgreSQL Redis subscription quota distribution"),
                ("mondoohq/mql", 398, "Go", "open source, cloud-native, graph-based query language", "aws, azure, gcp", "query entire infrastructure with mql run and shell"),
            ]
        )
        decisions = [eligibility.decide(row) for row in rows]
        self.assertEqual([row["admission_status"] for row in rows], ["admitted"] * 5)
        self.assertEqual({decision["eligibility"] for decision in decisions}, {"current_infrastructure"})

    def test_current_python_rows_are_actionable(self):
        rows = self.compile_fixture(
            [
                ("AtsushiSakai/PythonRobotics", 29420, "Python", "Python sample codes and textbook for robotics algorithms.", "algorithm, autonomous-navigation, control", "robotics algorithms sample codes"),
                ("commaai/openpilot", 60842, "Python", "openpilot is an operating system for robotics. Currently, it upgrades the driver assistance system on 300+ supported cars.", "driver-assistance-systems, robotics", "supported cars telemetry safety runtime"),
                ("zauberzeug/nicegui", 15759, "Python", "Create web-based user interfaces with Python. The nice way.", "frontend, gui, interface", "Python UI components and browser bridge"),
                ("NaiboWang/EasySpider", 43754, "JavaScript", "A visual no-code/code-free web crawler/spider", "crawler, data-collection, frontend", "visual browser automation crawler tasks"),
                ("Developer-Y/cs-video-courses", 81031, "?", "List of Computer Science courses with video lectures.", "algorithms, computer-science", "video lectures and course catalog"),
            ]
        )
        decisions = [eligibility.decide(row) for row in rows]
        self.assertEqual([row["admission_status"] for row in rows], ["admitted"] * 5)
        self.assertEqual({decision["eligibility"] for decision in decisions}, {"current_infrastructure"})

    def test_action_selector_inherits_matching_surface(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "AtsushiSakai/PythonRobotics",
                    "repo_url": "https://github.com/AtsushiSakai/PythonRobotics",
                    "custody_type": "robotics_algorithm_curriculum_custody",
                    "reasons": ["evidence_recovery_and_demotion_present"],
                }
            ]
        }
        surface_receipt = {
            "source_action": {
                "selected_repo": "AtsushiSakai/PythonRobotics",
                "custody_type": "robotics_algorithm_curriculum_custody",
            },
            "route_plan": {"selected_surface": "study"},
        }
        action = action_selector.select_action(payload, surface_receipt, Path("/tmp/robotics-path-probe/latest.json"))
        self.assertEqual(action["selected_repo"], "AtsushiSakai/PythonRobotics")
        self.assertEqual(action["selected_surface"], "study")
        self.assertEqual(action["next_action"], "study selected repo")

    def test_action_selector_ignores_stale_surface(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "AtsushiSakai/PythonRobotics",
                    "repo_url": "https://github.com/AtsushiSakai/PythonRobotics",
                    "custody_type": "robotics_algorithm_curriculum_custody",
                    "reasons": [],
                }
            ]
        }
        surface_receipt = {
            "source_action": {
                "selected_repo": "other/repo",
                "custody_type": "enterprise_search_knowledge_custody",
            },
            "route_plan": {"selected_surface": "fixture"},
        }
        action = action_selector.select_action(payload, surface_receipt, Path("/tmp/robotics-path-probe/latest.json"))
        self.assertIsNone(action["selected_surface"])
        self.assertEqual(action["surface_source"], "ignored")

    def test_action_selector_demotes_missing_priority_custody(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ]
        }
        action = action_selector.select_action(payload, None, Path("/tmp/robotics-path-probe/latest.json"))
        self.assertEqual(action["status"], "blocked")
        self.assertIsNone(action["selected_repo"])
        self.assertEqual(action["candidate_count"], 1)
        self.assertEqual(action["demoted_candidate_count"], 1)
        self.assertEqual(action["demoted_candidates"][0]["repo"], "unionyxx/uniOS")

    def test_action_selector_selects_enterprise_search_after_repo_matched_query_fixture(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ]
        }
        query_receipt = query_fixture.run_fixture(
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
        action = action_selector.select_action(
            payload,
            None,
            Path("/tmp/robotics-path-probe/latest.json"),
            query_receipt,
            Path("/tmp/enterprise-search-query-fixture/latest.json"),
        )
        self.assertEqual(action["status"], "selected")
        self.assertEqual(action["selected_repo"], "unionyxx/uniOS")
        self.assertEqual(action["selected_surface"], "query_fixture")
        self.assertEqual(action["next_action"], "query_fixture selected repo")
        self.assertEqual(action["query_fixture_source"], "/tmp/enterprise-search-query-fixture/latest.json")

    def test_action_selector_prefers_fresh_enterprise_fixture_over_prior_surface(self):
        payload = {
            "generated_at": "2026-05-07T03:00:00+00:00",
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ],
        }
        surface_receipt = {
            "source_action": {
                "selected_repo": "unionyxx/uniOS",
                "custody_type": "enterprise_search_knowledge_custody",
            },
            "route_plan": {"selected_surface": "study"},
        }
        query_receipt = query_fixture.run_fixture(
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
        query_receipt["generated_at"] = "2026-05-07T03:01:00+00:00"
        action = action_selector.select_action(
            payload,
            surface_receipt,
            Path("/tmp/robotics-path-probe/latest.json"),
            query_receipt,
            Path("/tmp/enterprise-search-query-fixture/latest.json"),
        )
        self.assertEqual(action["selected_surface"], "query_fixture")
        self.assertEqual(action["surface_source"], "/tmp/enterprise-search-query-fixture/latest.json")
        self.assertEqual(action["next_action"], "query_fixture selected repo")

    def test_action_selector_demotes_enterprise_search_on_mismatched_query_fixture(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ]
        }
        query_receipt = query_fixture.run_fixture(
            {
                "status": "ready",
                "fixture": {
                    "surface": "query_fixture",
                    "repo": "other/search",
                    "queries": [
                        {"query": "search evidence recovery"},
                        {"query": "search demotion rule"},
                    ],
                },
            }
        )
        action = action_selector.select_action(
            payload,
            None,
            Path("/tmp/robotics-path-probe/latest.json"),
            query_receipt,
            Path("/tmp/enterprise-search-query-fixture/latest.json"),
        )
        self.assertEqual(action["status"], "blocked")
        self.assertEqual(action["demoted_candidate_count"], 1)
        self.assertIn("different repo", action["demoted_candidates"][0]["reason"])

    def test_action_selector_demotes_enterprise_search_on_failed_query_fixture(self):
        payload = {
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ]
        }
        query_receipt = {
            "status": "failed",
            "repo": "unionyxx/uniOS",
            "surface": "query_fixture",
            "assertions": [
                {"top_hit_passed": False, "demotion_passed": True},
            ],
        }
        action = action_selector.select_action(
            payload,
            None,
            Path("/tmp/robotics-path-probe/latest.json"),
            query_receipt,
            Path("/tmp/enterprise-search-query-fixture/latest.json"),
        )
        self.assertEqual(action["status"], "blocked")
        self.assertEqual(action["demoted_candidate_count"], 1)
        self.assertIn("status is failed", action["demoted_candidates"][0]["reason"])

    def test_action_selector_demotes_enterprise_search_on_stale_query_fixture(self):
        payload = {
            "generated_at": "2026-05-07T02:44:32+00:00",
            "decisions": [
                {
                    "eligibility": "current_infrastructure",
                    "repo": "unionyxx/uniOS",
                    "repo_url": "https://github.com/unionyxx/uniOS",
                    "custody_type": "enterprise_search_knowledge_custody",
                    "reasons": ["evidence_recovery_and_demotion_present", "executable_surface"],
                }
            ],
        }
        query_receipt = query_fixture.run_fixture(
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
        query_receipt["generated_at"] = "2026-05-07T02:40:00+00:00"
        action = action_selector.select_action(
            payload,
            None,
            Path("/tmp/robotics-path-probe/latest.json"),
            query_receipt,
            Path("/tmp/enterprise-search-query-fixture/latest.json"),
        )
        self.assertEqual(action["status"], "blocked")
        self.assertEqual(action["demoted_candidate_count"], 1)
        self.assertIn("older than the current eligibility receipt", action["demoted_candidates"][0]["reason"])

    def test_action_selector_blocks_missing_eligibility_input(self):
        action = action_selector.missing_input_action(Path("/tmp/missing-eligibility/latest.json"))
        self.assertEqual(action["status"], "blocked")
        self.assertIn("eligibility input missing", action["reason"])
        self.assertEqual(action["next_action"], "run repo_pattern_eligibility_reader.py before selecting a repo action")

    def test_enterprise_search_query_fixture_passes_expected_hits_and_demotions(self):
        surface_payload = {
            "status": "ready",
            "selected_surface": "query_fixture",
            "fixture": {
                "surface": "query_fixture",
                "repo": "unionyxx/uniOS",
                "queries": [
                    {"query": "unios evidence recovery"},
                    {"query": "unios demotion rule"},
                ],
            },
        }
        receipt = query_fixture.run_fixture(surface_payload)
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["assertion_count"], 2)
        for assertion in receipt["assertions"]:
            self.assertTrue(assertion["top_hit_passed"])
            self.assertTrue(assertion["demotion_passed"])

    def test_enterprise_search_query_fixture_blocks_without_ready_surface(self):
        receipt = query_fixture.run_fixture({"status": "blocked", "reason": "no enterprise row"})
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("enterprise search surface probe", receipt["next_action"])

    def test_robotics_probe_preserves_selected_query_fixture_surface(self):
        action = {
            "status": "selected",
            "selected_repo": "unionyxx/uniOS",
            "custody_type": "enterprise_search_knowledge_custody",
            "selected_surface": "query_fixture",
        }
        body = {"route": "write_or_build"}
        candidates = robotics_probe.build_candidates(action, body)
        route = robotics_probe.search(candidates)
        self.assertEqual(route["status"], "found")
        self.assertEqual(route["selected_surface"], "query_fixture")


if __name__ == "__main__":
    unittest.main()
