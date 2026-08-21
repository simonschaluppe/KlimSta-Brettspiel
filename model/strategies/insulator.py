PRIORITY = {
    "Dämmung": 3,
    "Fenster": 2,
    "Lüftung": 1,
}

def choose_card(playable_cards, state, rng):

    def score(card):
        return (
            10 * PRIORITY.get(card["Slot/Stapel"], 0)
            + 3 * card["Wärmeschutz"]
            - 0.5 * card["Kosten"]
        )

    best_score = max(score(card) for card in playable_cards)

    return rng.choice([
        card
        for card in playable_cards
        if score(card) == best_score
    ])