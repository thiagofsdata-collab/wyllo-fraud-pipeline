"""
Shared styles for the dashboard. Keeps the look consistent across pages.
"""

# Wyllo-ish palette — neutral with one accent color.
COLORS = {
    "primary":   "#5B6CFF",   # accent
    "good":      "#10B981",   # green for pass/healthy
    "warn":      "#F59E0B",   # amber for warning
    "bad":       "#EF4444",   # red for fail/at-risk
    "ink":       "#111827",
    "muted":     "#6B7280",
    "bg_soft":   "#F3F4F6",
}

# Medallion layer colors — used in charts and metric cards.
LAYER_COLORS = {
    "main_bronze": "#CD7F32",
    "main_silver": "#C0C0C0",
    "main_gold":   "#FFD700",
    "main_seeds":  "#8B7355",
}


def tier_color(score: float) -> str:
    """Map a 0-1 risk score to a tier color (matches seeds/risk_thresholds.csv)."""
    if score < 0.30:
        return COLORS["good"]
    if score < 0.60:
        return COLORS["warn"]
    return COLORS["bad"]


def tier_label(score: float) -> str:
    """Same mapping as tier_color but returns the tier name."""
    if score < 0.30:
        return "low"
    if score < 0.60:
        return "medium"
    if score < 0.85:
        return "high"
    return "critical"
