def choose_card(playable_cards, state, rng):

    def score(card):
        return (
            4 * card["Stromproduktion"]
            + 3 * card["Stromspeicher"]
            - 3 * card["Strombedarf"]
            - 0.5 * card["Kosten"]
        )

    best_score = max(score(card) for card in playable_cards)

    best_cards = [
        card
        for card in playable_cards
        if score(card) == best_score
    ]

    return rng.choice(best_cards)