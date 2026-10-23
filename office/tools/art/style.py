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

# ---- people (chars.py, see NOTES-chars.md): named skin, hair and cloth tones for the characters
PEOPLE = {
    "skin": {"porcelain": "#fbe3cf", "fair": "#f6d3b5", "light": "#f2c9a5", "olive_l": "#e9bc94", "warm": "#e3ac80",
             "tan": "#d39a6a", "medium": "#c98e62", "brown": "#b07a50", "deep": "#9e6b45", "deeper": "#7e5236",
             "darkest": "#6e4a30"},
    "hair": {"black": "#2b2628", "black_cool": "#262a33", "dark_brown": "#3d2b22", "brown": "#6b4430", "caramel": "#a8714a",
             "ginger": "#c26a34", "blonde": "#e8c77e", "grey": "#b9b9bc", "silver": "#cfcfd2", "white": "#ebe9e4"},
    "cloth": {"thobe": "#f7f6f2", "thobe_warm": "#f1ede4", "abaya": "#2a2a32", "shemagh": "#c8323c", "gold": "#e0b553",
              "leather": "#8a5a34", "leather_dk": "#5a3d2a", "cognac": "#9a5a2e", "navy": "#34406a", "navy_dk": "#3a4560",
              "navy_turban": "#2e4a7d", "cream": "#f4ede2", "rose": "#d8a0a6", "nude": "#d9b9a0", "terracotta": "#d98a6a",
              "olive": "#7d8458", "sky": "#a9c8e8", "trouser": "#3d4458", "lilac": "#e4dcef", "green": "#3f8a5a",
              "djellaba": "#b49a7a", "babouche": "#e8c24a", "teal": "#2f8f8a", "maroon": "#8c2f45", "jasmine": "#fbf7ee",
              "grey": "#8b8f99", "shirt_white": "#f3f5f8", "charcoal": "#3c4252", "frame": "#3a3a44", "mustard": "#e2b04a",
              "emerald": "#2f8a66", "pink": "#e79ab4", "sage": "#8cb8a4", "denim": "#4a6a9a", "denim_dk": "#3a5280",
              "sneaker": "#f4f1ea", "jade": "#5fb08a", "qipao": "#b8323c", "lip_red": "#c4424a", "lip_rose": "#c9727c",
              "ink": "#2e3038", "slate": "#5c6b86", "oat": "#e8d6bf", "stone": "#b8b2a6", "lavender": "#c3aedf",
              "silk": "#f6f3ee", "barong": "#efe5cc", "barong_emb": "#c9b285", "dusk_blue": "#8fb3cf", "blush": "#e9a9b7",
              "ankara": "#d9692f", "ankara_band": "#2f8f8a", "indigo": "#4a6fa5", "kemis": "#f8f6f0", "kente_gold": "#e8b83a",
              "leaf": "#5f9a6e", "tweed": "#8a6a4a", "shirt_blue": "#e3ecf4", "moss": "#4a6a4a", "chino": "#cdb28a",
              "beret": "#b8323c", "nordic_blue": "#4f78a8", "royal": "#3a5a9a", "coral": "#ef8a72", "bowler": "#5a4030",
              "magenta": "#c04a7a", "camel": "#c9a27a", "burgundy": "#8a3040", "sea": "#2f8f9a", "tortoise": "#8a5a4a"},
}
