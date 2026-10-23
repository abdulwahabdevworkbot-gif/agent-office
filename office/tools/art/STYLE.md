# Office art style

One look for every room, piece of furniture and character, so they sit together.

## Look

- **Soft flat isometric.** Clean vector shapes with rounded corners. No textures, noise or photo detail.
- **Shading:** a base tone, one shadow tone and one small highlight. Light comes from the upper left, where the windows are.
  - Top faces get the base tone ×1.00.
  - Right-front faces get ×0.86.
  - Left-front faces get ×0.72.
- **Lines:** thin colored outlines, never black. An outline is its fill × 0.55.
  - At room scale (1200×896) lines are 2 px.
  - At character scale (72×200) lines are 1.1 px.
- **Mood:** calm and airy, so the eye rests. There are few bright accents, used for things that matter: screens, plants, and the status effects.
- **Weight:** flat colors keep files small.
  - A room is at most about 60 KB (WebP).
  - A character frame is at most about 4 KB.
  - A mask is at most about 1.5 KB (8-bit PNG).
- **Text:** no brand names or logos in the art. Any text is short and in English, and it is better left out.

## Palette

The palette lives in `style.py`. Use those names rather than new hex values. If a color is missing, add it there.

## Night

Night is the day art with these changes:

- a cool overlay (`NIGHT_TINT`, multiply);
- dark windows with a few lit city windows;
- warm glows from lamps and screens.

Draw it from the same source, not by hand.

## Room geometry (do not change)

- The room canvas is 1200×896.
- The floor diamond, in % of the room, has these corners:
  - back B = (50, 40);
  - right R = (88, 65);
  - front F = (54, 94);
  - left L = (4, 63).
- `P(u, v, h)` in `style.py` maps the floor (u along B→R, v along B→L) to pixels. h is the height in pixels at 1508-wide scale.
- The walls stand on B–L (left wall, with windows) and B–R (right wall, with the door and boards).

Every furniture sprite keeps its file name, its canvas size and where its footprint sits in that canvas. The page places sprites by their top-left corner in % of the room, so a sprite that moves its footprint lands in the wrong spot.

## Characters

- Each frame is 72×200 with a transparent background.
- The feet touch the bottom rows and the head (or headwear) reaches the top rows. The page sizes a character by its full height.
- The waist and seat line sits at y ≈ 112 (56 % from the top). Seated characters show only the top 56 %.
- There are 4 facings, named as in the old sprites:
  - `front-left`, and `front-right`, which is its mirror;
  - `rear-right`, and `rear-left`, which is its mirror.
- Each frame has a mask PNG of the same size:
  - red 255 marks the hair, which the owner can recolor;
  - green 255 marks the main top garment, which can also be recolored;
  - alpha is 255 wherever the character is.
  - Outlines of those parts belong to the mask.
- Recoloring keeps each pixel's brightness relative to the part's average. A recolorable part should therefore be drawn in tones of one hue.
