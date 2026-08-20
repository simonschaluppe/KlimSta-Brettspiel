import random


def offer_cards(cards, state, rule="free_choice", n=7, rng=None):
    """
    Return the cards offered to the player.

    The rule only determines what the player gets to see.
    game.py decides which of these cards are actually playable.

    Rules
    -----
    free_choice
        All cards are offered.

    random_draw
        Draw n random physical cards from all decks.

    Examples
    --------
    offer_cards(cards, state, rule="free_choice")
    offer_cards(cards, state, rule="random_draw", n=7, rng=rng)
    """
    rng = rng or random

    if rule == "free_choice":
        return cards

    if rule == "random_draw":
        return rng.sample(cards, min(n, len(cards)))

    raise ValueError(f"Unknown rule: {rule}")
