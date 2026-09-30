"""Land-cover class definitions shared across the analysis pipeline.

Colours match the legend used throughout the project UI and PPT:
    Forest (green) · Water (blue) · Agriculture (yellow) · Urban/Built-up (red) · Others (grey)
"""
from __future__ import annotations

# Ordered class list
CLASSES = ["Forest", "Water", "Agriculture", "Urban", "Others"]

# RGB colours used to paint segmentation masks
CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "Forest": (46, 125, 50),       # #2E7D32
    "Water": (21, 101, 192),       # #1565C0
    "Agriculture": (251, 192, 45), # #FBC02D
    "Urban": (229, 57, 53),        # #E53935
    "Others": (158, 158, 158),     # #9E9E9E
}

# Hex versions for convenience (frontend uses the same palette)
CLASS_HEX: dict[str, str] = {
    "Forest": "#2E7D32",
    "Water": "#1565C0",
    "Agriculture": "#FBC02D",
    "Urban": "#E53935",
    "Others": "#9E9E9E",
}
