PRIORITY = {
    "Nutzungsqualität": 3,
    "Lüftung": 2,
    "Fenster": 1,
}


def choose_card(playable_cards, state, rng):
    """Prioritize measures that improve user comfort and amenities."""

    def score(card):
        category = str(card["Slot/Stapel"]).lstrip("*")

        return (
            10 * PRIORITY.get(category, 0)
            + card.get("Zufriedenheit", 0)
        )

    best_score = max(score(card) for card in playable_cards)

    best_cards = [
        card
        for card in playable_cards
        if score(card) == best_score
    ]

    return rng.choice(best_cards)