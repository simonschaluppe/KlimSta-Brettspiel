import math
import random


def _valid_category(value):
    return (
        value is not None
        and not (isinstance(value, float) and math.isnan(value))
    )


def offer_cards(
    cards,
    state,
    rule="free_choice",
    n=7,
    category_count=1,
    cards_per_category=3,
    category_column="Slot/Stapel",
    rng=None,
):
    """
    Return the physical cards offered to the player.

    The rule determines only what the player gets to see.
    game.py decides which offered cards are actually playable.

    Rules
    -----
    free_choice
        Offer all physical cards.

    random_draw
        Draw n physical cards from the complete card pool.

    random_categories
        First draw category_count random categories, then draw
        cards_per_category physical cards from each selected category.

    Notes
    -----
    Physical copies created through Count remain separate draw opportunities.
    Several physical copies may therefore share the same card_id.
    """
    rng = rng or random

    if rule == "free_choice":
        return cards

    if rule == "random_draw":
        return rng.sample(cards, min(n, len(cards)))

    if rule == "random_categories":
        categories = sorted({
            card.get(category_column)
            for card in cards
            if _valid_category(card.get(category_column))
        })

        selected_categories = rng.sample(
            categories,
            min(category_count, len(categories)),
        )

        offered = []

        for category in selected_categories:
            category_cards = [
                card
                for card in cards
                if card.get(category_column) == category
            ]

            offered.extend(
                rng.sample(
                    category_cards,
                    min(cards_per_category, len(category_cards)),
                )
            )

        return offered

    raise ValueError(f"Unknown rule: {rule}")