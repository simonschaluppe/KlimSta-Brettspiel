def choose_card(playable_cards, state, rng):
    """
    Random baseline strategy:
    choose one of the currently playable cards at random.
    """
    return rng.choice(playable_cards)
