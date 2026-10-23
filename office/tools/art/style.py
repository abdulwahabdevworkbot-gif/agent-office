"""Shared palette and iso helper for the office art (see STYLE.md)."""

W, H = 1508, 1126            # drawing scale used by the room tools; final rooms are 1200x896
B, R, F, L = (50, 40), (88, 65), (54, 94), (4, 63)   # floor corners in % of the room


def P(u, v, h=0, w=W, hh=H):
    """Floor point (u along back->right, v along back->left, height h px at 1508 scale) -> pixel."""
    x = (1-u)*(1-v)*B[0] + u*(1-v)*R[0] + u*v*F[0] + (1-u)*v*L[0]
    y = (1-u)*(1-v)*B[1] + u*(1-v)*R[1] + u*v*F[1] + (1-u)*v*L[1]
    s = w / W
    return (x*w/100, y*hh/100 - h*s)


def shade(hexc, f):
    """Multiply a #rrggbb color by f (0..1 darkens, >1 lightens toward white)."""
    r, g, b = (int(hexc[i:i+2], 16) for i in (1, 3, 5))
    if f <= 1:
        r, g, b = (round(c*f) for c in (r, g, b))
    else:
        t = f - 1
        r, g, b = (round(c + (255-c)*t) for c in (r, g, b))
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


TOP, RIGHT_FACE, LEFT_FACE, OUTLINE, HILITE = 1.0, .86, .72, .55, 1.18

PAL = {
    # room
    "wall": "#f3eee6", "wall_side": "#e6ddd0", "baseboard": "#cdbfae", "trim": "#b9a993",
    "floor": "#e9d2ab", "floor_line": "#dcbf90", "floor_alt": "#eed9b6", "rug": "#cfe0d6",
    "glass": "#cfe6f5", "sky": "#a9d4f2", "cloud": "#ffffff", "city": "#bcd2e6",
    # accents
    "sage": "#8cc0a8", "teal": "#3e8e8a", "coral": "#f08a6c", "mustard": "#f2c14e",
    "lavender": "#b7a6e0", "navy": "#2f3b5c", "sky_accent": "#7fb6e6", "rose": "#e88aa6",
    "leaf": "#5fa36a", "leaf_dark": "#3f7f4e", "pot": "#d98f6a", "wood": "#c99a6b",
    "wood_dark": "#9c6f48", "metal": "#b8c0cc", "dark": "#3a4152", "screen": "#253048",
    "screen_glow": "#8fd3ff", "paper": "#fbfaf6",
    # rooms and furniture (room artist, see NOTES-rooms.md)
    "backdrop": "#161d2b", "wall_cap": "#ddd3c5", "frame": "#f7f4ee", "sun": "#f5e6c8",
    "sky_high": "#8fc4ea", "sky_low": "#d7ecf8", "city_far": "#d2e1ee", "city_near": "#a9c2da",
    "carpet": "#cfd6d3", "carpet_line": "#c3ccc8", "fabric": "#7f93b0", "desk": "#f4f1ea",
    "night_sky": "#1f2a48", "night_sky_low": "#33426a", "night_city": "#2b3757",
    "night_city_far": "#38466b", "lit_window": "#ffd98a",
    # people
    "skin": ["#fbe3cf", "#f2c9a5", "#e3ac80", "#c98e62", "#9e6b45", "#6e4a30"],
    "hair": ["#1e1b1a", "#3b2a20", "#6b4430", "#b9773e", "#e3c27a", "#c9c9c9"],
    "denim": "#4a6a9a", "chino": "#cdb28a", "trouser": "#3d4458", "shoe": "#2c2a2a",
    "thobe": "#f7f6f2", "abaya": "#23232a", "agal": "#1b1b1f", "shemagh_red": "#c8323c",
}

NIGHT_TINT = "#2a3160"       # multiply at ~35 %
NIGHT_GLOW = "#ffd9a0"       # warm lamp glow
