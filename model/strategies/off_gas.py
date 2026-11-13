def choose_card(playable_cards, state, rng):

    def score(card):

        heating_bonus = 0

        if card["Heizsystem"] in {
            "BIO",
            "FW",
            "GG",
            "WP",
            "ABWWP",
        }:
            heating_bonus = 100

        return (
            heating_bonus
            + 4 * card["Wärmeschutz"]
            + 2 * card["Stromproduktion"]
            - 2 * card["Strombedarf"]
            - 0.5 * card["Kosten"]
        )

    best_score = max(score(card) for card in playable_cards)

    return rng.choice([
        card
        for card in playable_cards
        if score(card) == best_score
    ])