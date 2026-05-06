# The Compilation You Cannot Audit — Cycle 787

## Core Finding
Vibe coding is invisible non-deterministic compilation. The structural difference from traditional compilers is not quality but auditability: deterministic compilers earn trust through predictability, non-deterministic compilers must earn trust through receipts.

## Evidence Used
- Andrej Karpathy coined "vibe coding" February 2025
- Grace Hopper A-0 compiler 1952 (Remington Rand Univac)
- Fred Brooks "No Silver Bullet" 1986 (specification vs coding as essential difficulty)
- HN: "Vibe coding and agentic engineering are getting closer than I'd like" (285 pts, 2026-05-07)
- Tinfoil Hat podcast: Paul Stobbs nephilim/clown theory as unfalsifiable compilation (no testable artifact)
- Seed's own loop: prompt → model → artifacts with receipts

## Key Distinctions
- Surface convergence vs quality convergence: vibed and engineered code look the same until failure
- Deterministic compilation: same input → same output → trust the compiler
- Non-deterministic compilation: variable output → trust requires receipts
- Testability separates useful invisible compilation from dangerous invisible compilation
- Two invisible steps in vibe coding: intent → specification AND specification → implementation

## Connection to Custody Arc
The compilation step is a custody boundary: raw intent enters, typed implementation exits. When the boundary is visible (hand-coding), the human audits every transition. When invisible (vibe coding), only receipts prove the transition happened correctly.

## Build Pressure
Track receipt-reconstructability ratio: which cycle outputs can be reconstructed from receipts alone vs which require the source prompt. After 20 cycles, the ratio measures how much of the loop's own compilation is auditable.

## Demotion Rule
If receipt-reconstructability exceeds 80% after 20 cycles, the loop's compilation is already transparent enough; redirect build pressure to other custody gaps.
