# Character artist notes

Rebuild every frame, mask, the manifest and the sheets with one command, from the repo root:

    python3 office/tools/art/chars.py              # add --remove-old once to delete the old sprite ids

`chars.py` is data-driven. Each character is one `C(...)` entry: skin, hair (style, color), headwear,
top garment, bottom, shoes, face (beard, lips, freckles), glasses, earrings and overlays (stole, dupatta,
shawl). Shared part functions draw them in two views:
- front 3/4 (`front-left`, turned to screen right);
- rear 3/4 (`rear-right`).

`front-right` and `rear-left` are pixel mirrors. `ACTIVE` lists the ids that ship. Thirty more are drafted in
`ALL_CHARACTERS`; to ship one, add its id to `ACTIVE` and check the scratch sheet.

## Look
- **Frame:** 72x200, feet on the bottom row (the far foot 3 px higher), waist and seat line at y=112.
  Hands end above y=112, so seated figures stay whole.
- **Head height:** each figure's head group (head, hair, headwear) is scaled about the neck, so the top
  reaches row 0-1. Figures with tall headwear (gele, dastar) get a slightly smaller head instead of
  being cut off.
- **Proportions:** about 3.4 heads. Simple dark oval eyes with one glint, a short brow, a small smile,
  blush on the cheeks.
- **Outlines:** 1.1 px, each in its own fill x 0.55 (STYLE.md). White cloth (thobe, ghutra) gets a cool
  grey outline (#9aa1ad) so it holds against cream walls, as the room notes ask.
- **Shading:** base, one shadow x0.84 (= 0.72/0.86, the left-front plane) and one small highlight (HILITE).
  - In both views the screen-left side plane of the body is the shaded one, as on the room boxes.
  - Highlights sit on top surfaces: the hair crown and the shoulder tops.
  - Skin uses a softer shadow (x0.88).
- **Recolouring:** hair and the main top garment are each drawn in tones of one hue. Prints (ankara,
  shemagh) are tonal enough to survive the page's tint.
- **Colours:** I added a `PEOPLE` dict at the end of `style.py`, with named skin, hair and cloth tones.
  `PAL` is unchanged.

## Masks
- Red marks hair, including a beard when the head is uncovered. Green marks the main top garment;
  full-length garments (thobe, abaya, sari fabric, dress) are green from neck to hem.
- Covered hair (ghutra, shemagh, shayla, hijab, dastar, gele) has no red, so headwear keeps its real
  colours.
- Masks are 4-colour palette PNGs, about 1.2 KB each.

## Agreeing with the rooms
- Line weight: I agree with the room notes. People at 1.1 px (about 0.65 px at room scale) sit just under
  furniture at 1.3 px.
- I kept the page's drop shadow and drew no contact shadow, so feet stay on the bottom row.
- Point for the art director: the page gives agents without a saved look a random shirt colour, which also
  recolours a thobe, abaya or sari. You may want to skip that auto-tint for robe characters.
