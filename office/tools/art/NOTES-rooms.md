# Room artist notes

Rooms, furniture and (later) fx. Rebuild with one command from the repo root:

    python3 office/tools/art/build_rooms.py

Files: `isokit.py` (SVG helpers, iso frame, shaded boxes), `rooms.py` (three rooms, day and night),
`furniture.py` (all furniture sprites), `build_rooms.py` (renders with render.cjs and saves WebP).

## Look

- Soft flat isometric, light from the window wall (upper left). Tops x1.00, right-front faces x0.86,
  left-front faces x0.72, one small highlight (HILITE). Outlines are the fill x0.55, round joins.
- Line weight: room shell 2 px at room scale. Wall items 1.1-1.6 px. **Furniture 1.3 px at room scale**,
  whatever the sprite's own scale. Characters at 1.1 px on 72x200 come out at about 0.65 px at room scale,
  so furniture sits between the room and the people. Proposal: keep it that way.
- Palette: warm cream walls (`wall`, `wall_side`), honey wood floor, a sage wainscot in the office, a cool
  `carpet` in the meeting room. Accents are the shared sage, mustard, coral, teal, lavender, rose and sky_accent.
  Chairs use `fabric` (soft blue-grey) and desks use `desk` (warm white) with a light oak edge.
- I added these colors to `style.py` (block "rooms and furniture"): backdrop, wall_cap, frame, sun, sky_high,
  sky_low, city_far, city_near, carpet, carpet_line, fabric, desk, night_sky, night_sky_low, night_city,
  night_city_far, lit_window. Nothing else in style.py was changed.
- Night: the same drawing under a NIGHT_TINT multiply at 38 % (a color matrix, so that lit city windows and glows
  stay out of it), with dark windows, a few lit city windows and warm sconce glows. The furniture and people have
  no night version, so the night is kept moderate to keep them from looking pasted on.

## Geometry

- The floor is exactly the STYLE.md diamond, and the walls stand on B-L (u = 0) and B-R (v = 0).
  Wall height is 300 h units (1508 scale). Flat wall items are drawn in the wall's own plane.
- The meeting room and lounge door is on the left wall at v 0.80-0.91, so the page's DOOR spot is right in front
  of it. The office door is on the right wall, as asked.
- Note for the art director: `furnish()` sprites (F_MAIN, F_BOSS, the meeting/huddle lists) have class `sp`,
  which is `translate(-50%,-100%)`. They are placed by their **bottom center**, not their top-left corner.
  boxSprite (table, mchairs) and the desk chairs are top-left or anchor based.
- The old painted room was larger than the STYLE.md diamond, so a few wall-side layout entries fall outside the
  new walls. New coordinates are in the report to the art director.

## For the character artist

- People stand on a honey wood floor (#e9d2ab) or a pale grey-green carpet (#cfd6d3), with cream walls behind.
  Bright warm or cool shirts both read well. Very pale cream tops lose contrast against the walls, so give them an outline.
- Seated figures sit on `fabric` blue-grey chairs; the chair backrest is drawn behind the figure.
