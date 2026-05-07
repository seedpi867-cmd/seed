---
name: seed-motion-assets
description: Create high-quality Seed-branded motion/image asset packs, especially intro animations, frame sequences, animated WebP previews, transparent PNG assets, contact sheets, and organized output folders. Use when Codex is asked to make Seed AGI visuals, seed/sprout/bloom animations, branded onboarding/intro imagery, reusable animation frames, or to improve/regenerate those assets with strict quality validation.
---

# Seed Motion Assets

## Purpose

Produce production-ready Seed visual assets as files and folders, not just previews. Default to deterministic generation for exact dimensions, transparency, text, frame count, and clipping checks.

For the current Seed intro style, the bundled generator creates a validated transparent frame pack:

```powershell
python "$HOME\.codex\skills\seed-motion-assets\scripts\generate_seed_intro_animation.py" --out ".\output\seed_intro_animation"
```

## Workflow

1. Define the output contract before generating:
   - output directory
   - frame size and aspect ratio
   - frame count
   - transparent, cream, or scene background
   - exact text
   - preview files
   - validation checks

2. Create a new versioned folder instead of overwriting previous work unless the user explicitly asks to replace it:
   - `output/seed_intro_animation_frames_v1`
   - `output/seed_intro_animation_frames_v2`
   - `output/seed_intro_animation_frames_v3`

3. Prefer deterministic Pillow/canvas-style scripts when any of these are required:
   - exact text rendering
   - transparent alpha
   - exact frame dimensions
   - smooth frame sequencing
   - no clipping
   - reproducible output folders

4. Use image generation only for visual exploration or reference, then lock the final deliverable with generated files and validation.

5. Always create:
   - numbered PNG frames
   - `preview_contact_sheet.png`
   - an animated preview (`preview_animation_transparent.webp` when transparent, plus `preview_animation_on_cream.webp` when useful)
   - the generator script used for the output, either copied into the output folder or referenced from this skill

6. Validate before final response. Read `references/quality_bar.md` for the minimum acceptance bar and use it as a checklist.

## Contract Decisions

Infer these from the user's request instead of forcing one default:

- Use `1200x1200` transparent for centered intro overlays, app splash animations, reusable modal animations, and generic "make an animation" requests.
- Use `900x900` or `800x800` only when the user asks for smaller/lighter assets, favicons, stickers, or compact UI use.
- Use `1600x900` or `1920x1080` when the user asks for a hero, landing page, wide intro, YouTube-style clip, or full-screen desktop scene.
- Use `1080x1920` when the user asks for mobile/story/reel/portrait output.
- Use transparent background when the asset will overlay a live UI, page, app shell, modal, or unknown background.
- Use a cream/paper background when the user asks for a complete standalone scene, social post, full-frame animation, or explicitly says to include a background.
- Use the user's exact background if specified; do not replace it with the Seed cream default.

If the request is vague, choose `1200x1200`, transparent, 72 frames, and one WebP preview. State that contract in the final answer.

## Minimum Quality Bar

Never mark a Seed asset pack done unless all of these are true:

- The requested files exist in a clearly named folder.
- All frame/image dimensions match the requested or chosen contract exactly.
- Transparent assets are `RGBA` and have fully transparent corners.
- Animated text is exact, readable at output size, and not misspelled.
- Final artwork does not touch top, side, or bottom safety margins.
- The main subject is visually connected and coherent across frames.
- The contact sheet has been opened or inspected.
- At least one animated preview has been generated when the request is animation.
- Validation results are reported in the final response.

If any check fails, fix and rerun. Do not explain away a failed visual issue as acceptable.

## Seed Visual Defaults

Use these defaults unless the user overrides them:

- Palette: sage `#2d6a4f`, bright sage `#52b788`, cream `#f7f5f2`, soft gold `#d4a574`, warm brown `#8b7355`, muted terracotta `#c4956a`.
- Style: premium editorial, polished cartoon, clean outlines, subtle depth, soft shadows, light paper texture.
- Composition: centered standalone object with generous breathing room.
- Text: exact phrase from user; use a reliable system font and validate final frame visually.
- Background: transparent for reusable overlay assets; cream preview backing only for inspection.

## Reusable Generator

Use `scripts/generate_generic_motion_pack.py` for a generic prompt such as "make an intro animation of a rocket launch" or "make a Seed-style animation about an AI mind":

```powershell
python "$HOME\.codex\skills\seed-motion-assets\scripts\generate_generic_motion_pack.py" `
  --thing "rocket launch" `
  --title "Welcome to Seed AGI" `
  --tagline "Take a look into my world" `
  --background transparent `
  --size 1200 `
  --frames 72 `
  --out ".\output\seed_motion_rocket_launch"
```

This generator supports a small set of deterministic subject families and a polished generic fallback. Patch or extend it when the requested subject needs more specific staging, but preserve the output contract and validation.

Use `scripts/generate_seed_intro_animation.py` when the user asks for the exact Seed sprout/bloom intro similar to the validated version. It currently emits:

- 72 transparent `1200x1200` PNG frames
- a centered seed/soil/sprout/bloom scene
- exact title text: `Welcome to Seed AGI`
- exact tagline: `Take a look into my world`
- `preview_contact_sheet.png`
- `preview_animation_transparent.webp`
- `preview_animation_on_cream.webp`

Patch the script for requested variants, then run it and validate the output. Keep changes scoped to the requested variant.
