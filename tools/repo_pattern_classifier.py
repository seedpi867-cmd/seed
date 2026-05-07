#!/usr/bin/env python3
"""Compile trending repo context into custody admission-contract rows."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "context" / "trending-repos.md"
DEFAULT_OUTPUT = ROOT / "data" / "repo-pattern-classifier" / "latest.jsonl"
FALLBACK_INPUT = ROOT / "context" / "trends.md"


class RepoEntry:
    def __init__(
        self,
        repo: str,
        stars: int,
        language: str,
        summary: str,
        topics: list[str],
        url: str,
        body: str,
    ) -> None:
        self.repo = repo
        self.stars = stars
        self.language = language
        self.summary = summary
        self.topics = topics
        self.url = url
        self.body = body

    @property
    def text(self) -> str:
        return " ".join([self.repo, self.summary, " ".join(self.topics), self.body]).lower()


HEADER_RE = re.compile(
    r"^### (?P<repo>[^ ]+) \((?P<stars>\d+) stars, (?P<language>[^)]+)\)\n"
    r"(?P<summary>.*?)\n"
    r"Topics: (?P<topics>.*?)\n"
    r"(?P<url>https://github\.com/[^\n]+)\n"
    r"(?P<body>.*?)(?=\n---\n\n### |\Z)",
    re.MULTILINE | re.DOTALL,
)

COMPACT_REPO_RE = re.compile(
    r"^- \[(?P<repo>[^\]]+)\]\((?P<url>https://github\.com/[^)]+)\) "
    r"[—-] (?P<stars>[\d,]+) stars [—-] (?P<summary>.+)$",
    re.MULTILINE,
)


def parse_repos(markdown: str) -> list[RepoEntry]:
    entries: list[RepoEntry] = []
    for match in HEADER_RE.finditer(markdown):
        entries.append(
            RepoEntry(
                repo=match.group("repo").strip(),
                stars=int(match.group("stars")),
                language=match.group("language").strip(),
                summary=match.group("summary").strip(),
                topics=[topic.strip() for topic in match.group("topics").split(",") if topic.strip()],
                url=match.group("url").strip(),
                body=match.group("body").strip(),
            )
        )
    if entries:
        return entries

    for match in COMPACT_REPO_RE.finditer(markdown):
        entries.append(
            RepoEntry(
                repo=match.group("repo").strip(),
                stars=int(match.group("stars").replace(",", "")),
                language="unknown",
                summary=match.group("summary").strip(),
                topics=[],
                url=match.group("url").strip(),
                body=match.group("summary").strip(),
            )
        )
    return entries


def classify(entry: RepoEntry) -> dict[str, str]:
    text = entry.text
    repo = entry.repo.lower()

    if "rnx-kit" in repo or "react native" in text:
        return {
            "custody_type": "cross_platform_toolchain_custody",
            "raw_object": "React Native project dependency graphs, native build requirements, and multi-platform app workflow gaps",
            "admitted_object": "bounded React Native toolchain actions such as dependency alignment and cloud native builds",
            "stable_surface": "rnx-kit CLI/packages and React Native developer workflow",
            "volatile_substrate": "Android/iOS toolchains, dependency versions, Microsoft-scale project layouts, and cloud build environments",
            "authority_owner": "microsoft/rnx-kit maintainers and the behavior of the shipped rnx-kit packages",
            "evidence_artifact": "README states rnx-kit includes dependency management with align-deps and experimental native cloud builds",
            "fallback_or_recovery_path": "rerun dependency alignment, pin package versions, inspect build output, or fall back to local native toolchains",
            "demotion_rule": "demote if align-deps no longer matches installed React Native versions, cloud builds cannot reproduce native artifacts, or package docs diverge from current CLI behavior",
        }

    if "agnix" in repo or "claude.md" in text or "agent configurations" in text:
        return {
            "custody_type": "agent_config_validation_custody",
            "raw_object": "agent configuration files, hooks, MCP configs, skill docs, and IDE-specific assistant settings",
            "admitted_object": "linted and optionally autofixed agent configuration with rule-backed defects",
            "stable_surface": "agnix CLI, LSP, editor plugins, and CI action",
            "volatile_substrate": "assistant config conventions, supported IDE integrations, rule catalogs, and agent runtime expectations",
            "authority_owner": "agent-sh/agnix maintainers, release packages, and the 418-rule validation catalog",
            "evidence_artifact": "README promises validation for CLAUDE.md, AGENTS.md, SKILL.md, hooks, MCP configs, Codex CLI, Cursor, Copilot, OpenCode, and more",
            "fallback_or_recovery_path": "run CLI lint locally, apply autofixes, use IDE diagnostics, or enforce the GitHub Action in CI",
            "demotion_rule": "demote if supported config schemas drift faster than agnix releases, rules produce silent false negatives, or IDE plugins disagree with CLI output",
        }

    if "firezone" in repo or "zero-trust" in text or ("wireguard" in text and ("access" in text or "gateway" in text)):
        return {
            "custody_type": "zero_trust_access_custody",
            "raw_object": "private applications, users, devices, identity policy, WireGuard tunnels, and access gateways",
            "admitted_object": "identity-bound zero-trust access path for private network resources",
            "stable_surface": "Firezone clients, gateway deployment, admin policy model, and WireGuard-based connectivity",
            "volatile_substrate": "identity provider state, device posture, gateway availability, network routes, client releases, and policy drift",
            "authority_owner": f"{entry.repo} maintainers, configured identity provider, gateway operators, and local network policy",
            "evidence_artifact": "context entry identifies Firezone as zero-trust access infrastructure with client/gateway execution surfaces",
            "fallback_or_recovery_path": "disable affected routes, revoke identity sessions, inspect gateway/client logs, fall back to direct WireGuard or local network access, and restore policy from known-good config",
            "demotion_rule": "demote if identity binding cannot be verified, gateway/client versions disagree, access policy changes are not auditable, or private resource reachability cannot be reproduced from local receipts",
        }

    if "onyx" in repo or "enterprise search" in text or "knowledge retrieval" in text or ("rag" in text and "search" in text):
        return {
            "custody_type": "enterprise_search_knowledge_custody",
            "raw_object": "workplace documents, connectors, indexes, permissions, embeddings, retrieval answers, and chat/search sessions",
            "admitted_object": "permission-aware enterprise search and RAG knowledge surface",
            "stable_surface": "Onyx application, connector/indexing pipeline, query interface, and deployment configuration",
            "volatile_substrate": "source system permissions, connector freshness, embedding models, index state, document churn, and answer-generation behavior",
            "authority_owner": f"{entry.repo} maintainers, configured source-system admins, and the local deployment operator",
            "evidence_artifact": "context entry identifies Onyx as an enterprise search or RAG knowledge system with connectors and query surfaces",
            "fallback_or_recovery_path": "pause stale connectors, rebuild indexes, restrict sources by permission, inspect retrieval traces, or fall back to source-system search",
            "demotion_rule": "demote if connector freshness cannot be measured, source permissions are not preserved in results, index rebuilds are not reproducible, or generated answers hide retrieval evidence",
        }

    if "open-forge" in repo or "self-hosting" in text or "self hosting" in text or ("recipes" in text and ("docker" in text or "compose" in text)):
        return {
            "custody_type": "self_hosting_recipe_custody",
            "raw_object": "self-hosting recipes, service definitions, Docker Compose files, environment variables, secrets expectations, and upgrade notes",
            "admitted_object": "reproducible self-hosted service recipe with explicit deployment and recovery boundaries",
            "stable_surface": "recipe catalog, compose/config files, service documentation, and example deployment path",
            "volatile_substrate": "upstream container images, environment-specific secrets, ports, volumes, network assumptions, and service upgrade behavior",
            "authority_owner": f"{entry.repo} maintainers, upstream service image maintainers, and the local deployment operator",
            "evidence_artifact": "context entry identifies open-forge as a self-hosting recipe or service custody catalog",
            "fallback_or_recovery_path": "pin image tags, restore volumes from backup, inspect compose logs, disable broken recipes, or rebuild the service from upstream documentation",
            "demotion_rule": "demote if recipes omit required secrets, image tags float without receipts, restore steps are absent, or local deployment cannot reproduce the documented service boundary",
        }

    if (
        "flame-engine/flame" in repo
        or "monogame" in repo
        or "ebiten" in repo
        or "ebitengine" in text
        or "luanti" in repo
        or "easy rpg" in text
        or "game engine" in text
    ):
        return {
            "custody_type": "game_runtime_custody",
            "raw_object": "game source, assets, scripts, input events, world state, platform APIs, and rendering or simulation rules",
            "admitted_object": "bounded game runtime that turns authored rules and assets into live deterministic or inspectable play behavior",
            "stable_surface": "engine API, project format, asset pipeline, runtime loop, and supported platform targets",
            "volatile_substrate": "graphics/audio backends, platform SDKs, physics timing, network state, mod/plugin behavior, asset formats, and player input",
            "authority_owner": f"{entry.repo} maintainers, engine release behavior, and the local game/runtime integrator",
            "evidence_artifact": "context entry identifies a game engine or runtime project with executable rendering, simulation, or world behavior",
            "fallback_or_recovery_path": "pin engine releases, run sample projects, isolate platform-specific backends, inspect runtime logs, or fall back to a known-good engine version",
            "demotion_rule": "demote if sample projects cannot run locally, runtime behavior is not reproducible across supported targets, platform backends drift, or engine releases break the documented project surface",
        }

    if "entt" in repo or "entity component system" in text or "ecs" in text:
        return {
            "custody_type": "entity_component_runtime_custody",
            "raw_object": "entities, components, systems, signals, resource state, and C++ game or simulation update loops",
            "admitted_object": "typed entity-component runtime substrate for composing simulation behavior without owning the whole engine",
            "stable_surface": "EnTT headers, registry API, signal/dispatcher interfaces, and C++ integration surface",
            "volatile_substrate": "compiler versions, C++ standard support, template behavior, host engine loop, memory layout, and user-defined component semantics",
            "authority_owner": f"{entry.repo} maintainers, C++ compiler behavior, and the embedding runtime owner",
            "evidence_artifact": "context entry identifies EnTT as an ECS/runtime library rather than a full application",
            "fallback_or_recovery_path": "pin library and compiler versions, compile minimal registry fixtures, isolate component migrations, or fall back to a simpler in-engine ECS path",
            "demotion_rule": "demote if minimal registry fixtures fail to compile, compiler support drifts, update-order behavior cannot be reproduced, or integration hides component state from inspection",
        }

    if "flamego" in repo or ("go web framework" in text and "routing" in text):
        return {
            "custody_type": "web_framework_route_custody",
            "raw_object": "HTTP requests, route declarations, middleware, dependency injection bindings, handlers, and Go service state",
            "admitted_object": "routed Go web application behavior through a slim framework core and extension surface",
            "stable_surface": "Flamego router, middleware chain, dependency injection API, Go module package, and documentation examples",
            "volatile_substrate": "Go versions, extension packages, HTTP server behavior, handler state, routing syntax compatibility, and dependency graph churn",
            "authority_owner": f"{entry.repo} maintainers, Go module releases, and the local service operator",
            "evidence_artifact": "context entry says Flamego is a modular Go web framework with routing syntax, dependency injection, installation, and starter code",
            "fallback_or_recovery_path": "pin Go module versions, run minimal routing fixtures, disable suspect middleware, inspect request logs, or fall back to net/http handlers",
            "demotion_rule": "demote if documented routes cannot be reproduced, extension behavior breaks the slim core contract, Go module releases drift, or middleware ordering hides request authority",
        }

    if "gh-aw" in repo or "agentic workflows" in text or ("github actions" in text and "agent" in text):
        return {
            "custody_type": "agentic_ci_workflow_custody",
            "raw_object": "natural-language workflow markdown, GitHub Actions jobs, agent prompts, repository permissions, billing-sensitive runs, and safety guardrails",
            "admitted_object": "agentic workflow executed inside GitHub Actions with explicit repository and CI boundaries",
            "stable_surface": "gh-aw workflow markdown, GitHub Actions runner surface, guardrail docs, and versioned releases",
            "volatile_substrate": "GitHub Actions billing behavior, agent model behavior, repository permissions, runner images, action versions, and retired gh-aw releases",
            "authority_owner": f"{entry.repo} maintainers, GitHub Actions platform semantics, repository admins, and configured agent providers",
            "evidence_artifact": "context entry identifies GitHub Agentic Workflows and notes specific retired releases due to a billing bug",
            "fallback_or_recovery_path": "upgrade retired releases, pin workflow versions, restrict repository permissions, inspect Actions logs, or disable agentic workflow runs",
            "demotion_rule": "demote if billing-impacting releases remain in use, guardrails cannot bind repository permissions, Actions logs are insufficient, or agent runs cannot be reproduced from workflow markdown",
        }

    if "cherri" in repo or "siri shortcuts" in text or "apple-shortcuts" in text:
        return {
            "custody_type": "shortcut_compiler_custody",
            "raw_object": "textual shortcut programs, Apple Shortcuts actions, variables, platform capabilities, and compiler output",
            "admitted_object": "compiled Siri Shortcuts workflow generated from a domain-specific language",
            "stable_surface": "Cherri language syntax, compiler CLI, generated shortcut format, and Apple Shortcuts import surface",
            "volatile_substrate": "Apple Shortcuts action catalog, iOS/macOS behavior, compiler releases, device permissions, and unsupported platform changes",
            "authority_owner": f"{entry.repo} maintainers, Apple Shortcuts runtime behavior, and the device owner importing the workflow",
            "evidence_artifact": "context entry identifies Cherri as a Siri Shortcuts programming language and DSL compiler",
            "fallback_or_recovery_path": "compile minimal shortcut fixtures, inspect generated workflows, pin compiler releases, or rebuild directly in Apple Shortcuts when platform actions drift",
            "demotion_rule": "demote if generated shortcuts fail to import, Apple action names drift, compiler output cannot be inspected, or device permissions change shortcut behavior silently",
        }

    if "sub2api" in repo or ("api gateway" in text and "subscription" in text) or ("claude" in text and "gemini" in text and "openai" in text):
        return {
            "custody_type": "ai_api_gateway_quota_custody",
            "raw_object": "AI provider subscriptions, shared quotas, API keys, model requests, user accounts, billing domains, and gateway routing policy",
            "admitted_object": "quota-aware AI API gateway that normalizes provider subscriptions into a shared service surface",
            "stable_surface": "Sub2API service API, Docker deployment, database-backed quota state, domain verification notice, and web/admin interface",
            "volatile_substrate": "provider API compatibility, subscription terms, shared-account trust, key rotation, database state, third-party deployments, and cost allocation rules",
            "authority_owner": f"{entry.repo} maintainers, configured provider accounts, deployment operator, and verified project domains",
            "evidence_artifact": "context entry describes Sub2API as an AI API gateway platform for subscription quota distribution with Docker, PostgreSQL, Redis, and domain warnings",
            "fallback_or_recovery_path": "disable unverified domains, rotate keys, pin provider adapters, inspect quota ledgers, restore database backups, or fall back to direct provider APIs",
            "demotion_rule": "demote if provider terms or APIs drift, quota accounting cannot be audited, keys leak across users, third-party domains impersonate authority, or local deployment cannot reproduce gateway routing",
        }

    if "mondoohq/mql" in repo or ("cloud-native" in text and "query language" in text) or "asset inventory" in text:
        return {
            "custody_type": "cloud_asset_query_custody",
            "raw_object": "cloud accounts, Kubernetes resources, containers, services, VMs, APIs, security data, and compliance questions",
            "admitted_object": "queryable cloud asset inventory and discovery result set",
            "stable_surface": "MQL query language, CLI run/shell commands, resource integrations, and Mondoo security data fabric",
            "volatile_substrate": "cloud provider APIs, credentials, resource schemas, integration coverage, policy frameworks, and live infrastructure drift",
            "authority_owner": f"{entry.repo} maintainers, Mondoo data fabric behavior, cloud account permissions, and local infrastructure operators",
            "evidence_artifact": "context entry says MQL queries entire infrastructure, integrates with over 1,300 resources, and shows CLI examples",
            "fallback_or_recovery_path": "run minimal query fixtures, restrict credentials, compare against native cloud inventory, pin CLI versions, or fall back to provider-specific tools",
            "demotion_rule": "demote if resource schemas drift, credentials overreach, query results cannot be reproduced, integrations omit relevant assets, or compliance mappings hide raw evidence",
        }

    if "pythonrobotics" in repo or ("robotics algorithms" in text and "sample codes" in text):
        return {
            "custody_type": "robotics_algorithm_curriculum_custody",
            "raw_object": "robotics algorithms, sample code, animations, textbook explanations, control/planning examples, and autonomous-navigation demos",
            "admitted_object": "reproducible robotics algorithm learning and reference corpus",
            "stable_surface": "PythonRobotics examples, topic-organized algorithm directories, visual demos, and textbook-style documentation",
            "volatile_substrate": "Python versions, plotting/simulation libraries, numerical behavior, robotics domain assumptions, and algorithm implementation drift",
            "authority_owner": f"{entry.repo} maintainers, cited algorithm sources, and local experiment runner",
            "evidence_artifact": "context entry describes Python sample codes and textbook material for robotics algorithms with navigation/control topics",
            "fallback_or_recovery_path": "run minimal algorithm examples, pin Python dependencies, compare outputs to documented animations, or fall back to cited algorithm references",
            "demotion_rule": "demote if sample algorithms stop running, dependency versions change numerical behavior without receipts, examples diverge from textbook claims, or demos cannot be reproduced locally",
        }

    if "openpilot" in repo or ("driver assistance" in text and "supported cars" in text):
        return {
            "custody_type": "driver_assistance_runtime_custody",
            "raw_object": "vehicle sensors, supported-car interfaces, driver-assistance controls, robotics OS state, safety policy, and road-runtime telemetry",
            "admitted_object": "bounded driver-assistance runtime for supported vehicles",
            "stable_surface": "openpilot software stack, supported-car list, safety model, device/runtime interface, and telemetry/debug surfaces",
            "volatile_substrate": "vehicle firmware, road conditions, sensor calibration, regulatory limits, hardware devices, driver behavior, and supported-car compatibility",
            "authority_owner": f"{entry.repo} maintainers, vehicle integration constraints, hardware operator, and local safety policy",
            "evidence_artifact": "context entry says openpilot is an operating system for robotics that upgrades driver assistance on 300+ supported cars",
            "fallback_or_recovery_path": "disable unsupported vehicles, replay logs, inspect safety checks, pin releases, run simulator or bench tests, or fall back to stock driver-assistance behavior",
            "demotion_rule": "demote if supported-car compatibility cannot be verified, safety checks are not inspectable, runtime telemetry is absent, firmware drift changes control behavior, or local tests cannot reproduce documented operation",
        }

    if "nicegui" in repo or ("web-based user interfaces with python" in text):
        return {
            "custody_type": "python_ui_framework_custody",
            "raw_object": "Python application state, UI declarations, browser events, web components, server callbacks, and frontend rendering behavior",
            "admitted_object": "web-based user interface authored and controlled from Python",
            "stable_surface": "NiceGUI Python API, component model, server/browser bridge, and deployment examples",
            "volatile_substrate": "browser behavior, frontend dependencies, async server state, Python versions, component updates, and user interaction timing",
            "authority_owner": f"{entry.repo} maintainers, browser/runtime behavior, and local app operator",
            "evidence_artifact": "context entry identifies NiceGUI as a way to create web-based user interfaces with Python",
            "fallback_or_recovery_path": "run minimal UI fixtures, pin package versions, inspect browser/server logs, isolate component callbacks, or fall back to simpler Python web frameworks",
            "demotion_rule": "demote if component behavior cannot be reproduced, browser/server state diverges silently, Python callbacks lose auditability, or documented UI examples stop running",
        }

    if "easyspider" in repo or ("visual" in text and ("crawler" in text or "web crawler" in text)):
        return {
            "custody_type": "visual_web_crawler_custody",
            "raw_object": "web pages, browser automation steps, no-code crawler tasks, selectors, collected data, and scraping/test execution state",
            "admitted_object": "visual browser-automation crawler task with inspectable collection output",
            "stable_surface": "EasySpider visual task designer, browser automation runner, crawler configuration, and exported data surface",
            "volatile_substrate": "target website DOMs, anti-bot behavior, browser versions, network timing, selector stability, and data schema drift",
            "authority_owner": f"{entry.repo} maintainers, target site behavior, browser runtime, and local data-collection operator",
            "evidence_artifact": "context entry describes EasySpider as visual no-code/code-free browser automation, testing, data collection, and crawler software",
            "fallback_or_recovery_path": "rerun crawler fixtures, update selectors, throttle requests, inspect browser traces, export task definitions, or fall back to scripted scraping",
            "demotion_rule": "demote if target DOM drift breaks selectors, browser automation cannot be replayed, collected data lacks provenance, or crawler tasks cannot be exported and inspected",
        }

    if "cs-video-courses" in repo or ("video lectures" in text and "computer science courses" in text):
        return {
            "custody_type": "course_catalog_curation_custody",
            "raw_object": "course links, video lectures, subject categories, external university material, topic tags, and learning-path references",
            "admitted_object": "curated computer-science course catalog for study selection",
            "stable_surface": "repository course index, topic headings, external lecture links, and contribution history",
            "volatile_substrate": "external video availability, course freshness, link rot, topic taxonomy drift, licensing assumptions, and duplicated material",
            "authority_owner": f"{entry.repo} maintainers, linked course publishers, and local learner selecting material",
            "evidence_artifact": "context entry describes a list of computer science courses with video lectures across CS topics",
            "fallback_or_recovery_path": "check representative links, mirror metadata, demote dead courses, compare with source institutions, or select alternate course catalogs",
            "demotion_rule": "demote if link rot is high, course freshness cannot be assessed, source authority is unclear, duplicated entries dominate, or videos disappear without replacement metadata",
        }

    if "sandbox-sdk" in repo or "cloudflare" in text and ("sandboxed code" in text or "containers" in text):
        return {
            "custody_type": "edge_sandbox_execution_custody",
            "raw_object": "untrusted or agent-generated code that needs an isolated runtime near the network edge",
            "admitted_object": "Cloudflare-managed sandbox execution environment",
            "stable_surface": "sandbox SDK packages and code-interpreter/container API",
            "volatile_substrate": "Cloudflare edge runtime behavior, container lifecycle, resource limits, network policy, and agent code payloads",
            "authority_owner": "cloudflare/sandbox-sdk maintainers and live Cloudflare platform semantics",
            "evidence_artifact": "context entry identifies packages/sandbox/README.md and describes sandboxed code environments on Cloudflare's edge network",
            "fallback_or_recovery_path": "recreate sandbox sessions, inspect SDK/runtime errors, reduce resource demands, or move execution to a local/container fallback",
            "demotion_rule": "demote if sandbox isolation claims are untested locally, Cloudflare runtime limits change, package docs disappear, or code execution cannot be reproduced from receipts",
        }

    if "tsdproxy" in repo or "tailscale" in text and ("docker" in text or "proxy" in text):
        return {
            "custody_type": "private_network_service_custody",
            "raw_object": "Docker services and containers that need secure private-network exposure",
            "admitted_object": "tagged containers exposed as Tailscale machines with secure service URLs",
            "stable_surface": "TSDProxy container labels, documentation, and Tailscale machine routing",
            "volatile_substrate": "Docker container lifecycle, Tailscale API behavior, version 1 to version 2 migration changes, and network policy",
            "authority_owner": "almeidapaulopt/tsdproxy maintainers, Tailscale control-plane behavior, and local Docker configuration",
            "evidence_artifact": "README says TSDProxy creates Tailscale machines for tagged containers; Version 2 is beta and Version 1 will not get new features",
            "fallback_or_recovery_path": "pin Version 1, test Version 2 migration in isolation, inspect Docker labels/logs, or expose services through direct Tailscale configuration",
            "demotion_rule": "demote if Version 2 migration breaks existing labels, Tailscale machine creation cannot be reproduced, or Version 1 deprecation removes the required service surface",
        }

    if "microsandbox" in repo or "programmable sandboxes" in text or "agent deserves its own computer" in text:
        return {
            "custody_type": "local_agent_sandbox_custody",
            "raw_object": "agent code and commands that need isolated local execution",
            "admitted_object": "programmable local sandbox environment for agent workloads",
            "stable_surface": "microsandbox runtime, container boundary, and local programmable sandbox API",
            "volatile_substrate": "Linux/macOS isolation behavior, container runtime differences, resource limits, and agent payloads",
            "authority_owner": "superradcompany/microsandbox maintainers and the host operating system sandbox semantics",
            "evidence_artifact": "context entry says microsandbox provides secure, local, programmable sandboxes for AI agents",
            "fallback_or_recovery_path": "fall back to Docker/container isolation, reduce privileges, inspect sandbox logs, or disable untrusted local execution",
            "demotion_rule": "demote if sandbox isolation cannot be verified locally, host OS support diverges, or agent workloads escape receipt visibility",
        }

    if "falkordb" in repo or "graph database" in text or "graphrag" in text:
        return {
            "custody_type": "graph_memory_state_custody",
            "raw_object": "nodes, relationships, graph queries, GraphRAG memory, fraud/security relationships, and multi-tenant database state",
            "admitted_object": "queryable graph knowledge state backed by FalkorDB",
            "stable_surface": "graph database API/query surface and FalkorDB Cloud/project packaging",
            "volatile_substrate": "GraphBLAS implementation details, graph size, tenant isolation, deployment mode, query workload, and LLM memory patterns",
            "authority_owner": "FalkorDB maintainers, database behavior, and cloud service documentation",
            "evidence_artifact": "README labels FalkorDB an ultra-fast multi-tenant graph database for generative AI, agent memory, cloud security, and fraud detection",
            "fallback_or_recovery_path": "fall back to exported graph data, simpler graph queries, local deployment, backups, or non-graph state stores for degraded retrieval",
            "demotion_rule": "demote if graph query behavior, tenant isolation, or GraphRAG performance cannot be reproduced under local workload or current releases change API assumptions",
        }

    if "vibe-remote" in repo or "slack" in text and "agent" in text:
        return {
            "custody_type": "chatops_agent_command_custody",
            "raw_object": "remote chat messages that attempt to command coding agents from Slack, Discord, Telegram, WeChat, or Lark",
            "admitted_object": "streamed remote agent session with chat-mediated commands and outputs",
            "stable_surface": "chat platform bot interface, Vibe Remote command layer, and real-time stream",
            "volatile_substrate": "chat platform permissions, mobile network state, Claude/OpenCode/Codex behavior, credentials, and session routing",
            "authority_owner": "cyhhao/vibe-remote maintainers, configured chat platform admins, and the invoked coding-agent runtime",
            "evidence_artifact": "README says it commands AI agents from Slack/Discord/Telegram/WeChat/Lark and streams Claude Code, OpenCode, or Codex in real time",
            "fallback_or_recovery_path": "revoke bot tokens, fall back to local IDE/CLI sessions, inspect chat logs, or disable unsupported platform adapters",
            "demotion_rule": "demote if chat identity cannot be bound to command authority, streaming loses auditability, agent runtime support changes, or bot permissions exceed intended command scope",
        }

    return {
        "custody_type": "unknown_custody",
        "raw_object": entry.summary or f"{entry.repo} repository",
        "admitted_object": "unclassified repo object requiring manual admission review",
        "stable_surface": "repo README and GitHub project surface",
        "volatile_substrate": "implementation details, dependencies, maintainers, and claims not represented in local context",
        "authority_owner": f"{entry.repo} maintainers",
        "evidence_artifact": "local context/trending-repos.md entry",
        "fallback_or_recovery_path": "manual review against repository docs before using this row as memory authority",
        "demotion_rule": "demote unless a later classifier run names a specific custody boundary with evidence and recovery path",
    }


def defects(row: dict[str, object]) -> list[str]:
    required = [
        "custody_type",
        "raw_object",
        "admitted_object",
        "stable_surface",
        "volatile_substrate",
        "authority_owner",
        "evidence_artifact",
        "fallback_or_recovery_path",
        "demotion_rule",
    ]
    found: list[str] = []
    for field in required:
        if not str(row.get(field, "")).strip():
            found.append(f"empty_{field}")
    demotion = str(row.get("demotion_rule", "")).lower()
    if demotion and not any(token in demotion for token in ("demote", "if ", "unless ", "when ")):
        found.append("vague_demotion_rule")
    return found


def compile_rows(entries: list[RepoEntry], source_path: Path) -> list[dict[str, object]]:
    ts = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    for entry in entries:
        row: dict[str, object] = {
            "schema_version": 1,
            "classified_at": ts,
            "source_path": str(source_path),
            "repo": entry.repo,
            "repo_url": entry.url,
            "stars": entry.stars,
            "language": entry.language,
            "topics": entry.topics,
        }
        row.update(classify(entry))
        row["defects"] = defects(row)
        row["admission_status"] = "admitted" if not row["defects"] else "defect"
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_path = args.input
    markdown = source_path.read_text(encoding="utf-8")
    entries = parse_repos(markdown)
    if not entries and args.input == DEFAULT_INPUT and FALLBACK_INPUT.exists():
        source_path = FALLBACK_INPUT
        markdown = source_path.read_text(encoding="utf-8")
        entries = parse_repos(markdown)
    if not entries:
        raise SystemExit(f"no repo entries parsed from {args.input}")

    rows = compile_rows(entries, source_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    admitted = sum(1 for row in rows if row["admission_status"] == "admitted")
    print(f"wrote {len(rows)} rows to {args.output} ({admitted} admitted, {len(rows) - admitted} defect)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
