"""Strict centered business-window definitions for the formal PRR figures."""

# Fig.9--14 share the five-second formal window.  Fig.15 remains a separate
# ten-second traffic-mode study, so generic tooling must consult the manifest
# figure instead of treating this default as universally applicable.
FORMAL_ANALYSIS_DURATION_S = 5.0
FIG15_ANALYSIS_DURATION_S = 10.0


def formal_analysis_duration_s(figure: str) -> float:
    """Return the required strict business-window duration for one figure."""

    if str(figure) == "fig15":
        return FIG15_ANALYSIS_DURATION_S
    return FORMAL_ANALYSIS_DURATION_S
