# Seed Motion Asset Quality Bar

Use this checklist before final delivery.

## Output Contract

Every completed asset pack must include:

- A versioned output folder.
- Numbered source frames or image files.
- A preview contact sheet.
- An animated preview for animation work.
- The script or generation method used.
- A short final report with changed/created paths and validation evidence.

## Required Validation

Run or implement checks for:

- file count matches contract
- dimensions match contract
- PNG alpha mode for transparent outputs, or intentional opaque background for backed scenes
- fully transparent corners for transparent frames
- opaque corners/background for non-transparent full-scene frames
- exact text content in the generator/source
- final frame safety margins
- no subject clipping in any frame
- stable centered composition across frames

For transparent PNG validation, inspect:

```python
from PIL import Image
im = Image.open("frame_01.png")
assert im.mode == "RGBA"
assert all(im.getpixel(p)[3] == 0 for p in [(0,0), (im.width-1,0), (0,im.height-1), (im.width-1,im.height-1)])
```

## Visual Inspection

Open the contact sheet before final response. Check:

- the object reads clearly at thumbnail size
- the animation has no jumps or disconnected parts
- the final frame is the strongest frame
- text is large enough and spelled exactly
- flower/leaf/seed forms are connected to the stem and seed
- no visible clipping, accidental full-width soil, or stray artifacts

## Minimum Design Standard

Outputs should be at least as polished as the validated Seed v8 intro:

- clean premium cartoon-editorial style
- warm natural palette
- transparent reusable overlay by default
- larger-than-thumbnail readability
- coherent staging from scene to scene
- contact sheet plus WebP preview
- deterministic reproducibility

## Background And Size Decisions

The minimum bar includes choosing the right container:

- Transparent overlay assets should not carry accidental cream pixels in the corners.
- Standalone full-scene assets should not have accidental transparent holes unless requested.
- The chosen size/aspect must fit the usage: square overlay, wide hero, portrait story, compact sticker, or app splash.
- If a generated subject is cramped, increase canvas size or reduce subject scale before delivery.
- If text is requested, choose a canvas large enough for the text to be legible without crowding the art.

If a new request would produce lower quality than this bar, increase canvas size, add frames, simplify the scene, or make a better generator before delivering.
