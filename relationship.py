"""Relationship progression helpers for Luna's game-like companion layer."""

from __future__ import annotations

from mood import MoodResult


STAGES: tuple[tuple[float, str, str], ...] = (
    (0, "New connection", "We are just getting to know each other."),
    (20, "Friendly", "Easy conversation is growing."),
    (40, "Close friends", "There is a comfortable rhythm here."),
    (60, "Affectionate bond", "Warmth and trust are building."),
    (80, "Deep connection", "A strong, caring companion routine."),
)


def relationship_score(friendship: float, affection: float) -> float:
    """Combine the two visible dimensions into a stable 0–100 display score."""

    return max(0.0, min(100.0, (float(friendship) + float(affection)) / 2.0))


def relationship_stage(friendship: float, affection: float) -> tuple[str, str, float]:
    """Return ``(name, explanation, score)`` for current relationship stats."""

    score = relationship_score(friendship, affection)
    selected = STAGES[0]
    for stage in STAGES:
        if score >= stage[0]:
            selected = stage
    return selected[1], selected[2], score


def progress_bar(value: float, width: int = 10) -> str:
    """Render a compact text progress bar suitable for a Discord embed."""

    width = max(4, min(width, 20))
    filled = round(max(0.0, min(100.0, float(value))) / 100 * width)
    return "▰" * filled + "▱" * (width - filled)


def conversation_deltas(mood: MoodResult) -> tuple[float, float]:
    """Return small, capped game points for one explicit chat interaction.

    Friendship rewards showing up and talking.  Affection is deliberately a
    smaller, mood-aware game stat; it is not presented as proof of a real
    relationship and it never decays to pressure a user into returning.
    """

    if mood.mood == "sad":
        return 1.5, 0.25
    if mood.mood == "stressed":
        return 1.5, 0.25
    if mood.mood == "angry":
        return 1.25, 0.1
    if mood.mood == "romantic":
        return 1.0, 0.75
    if mood.mood == "joyful":
        return 1.25, 0.5
    if mood.mood == "tired":
        return 1.0, 0.25
    return 1.0, 0.25


def game_deltas(correct: bool | None = None) -> tuple[float, float]:
    """Return relationship points for participating in a couple game."""

    if correct is True:
        return 1.25, 0.75
    if correct is False:
        return 0.5, 0.25
    return 0.75, 0.5
