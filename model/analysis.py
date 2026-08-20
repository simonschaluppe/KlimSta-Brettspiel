import pandas as pd


def game_summary(games):
    """
    Basic summary of simulated games.

    VP = victory points / CO2 score.
    Lower VP is better.
    """
    columns = [
        "vp",
        "budget",
        "n_cards_played",
        "rounds_played",
        "satisfaction",
        "thermal_protection",
        "electricity_demand",
        "electricity_generation",
        "storage",
        "grid_import",
    ]

    columns = [column for column in columns if column in games.columns]

    return games[columns].describe().T


def strategy_summary(games):
    """
    Compare final game outcomes between strategies.
    """
    metrics = [
        "vp",
        "budget",
        "n_cards_played",
        "rounds_played",
        "satisfaction",
        "thermal_protection",
        "electricity_demand",
        "electricity_generation",
        "storage",
        "grid_import",
    ]

    metrics = [metric for metric in metrics if metric in games.columns]

    if "strategy" not in games.columns:
        raise ValueError("games must contain a 'strategy' column")

    summary = games.groupby("strategy")[metrics].agg(
        ["mean", "median", "std"]
    )

    return summary


def card_occurrence(games):
    """
    Fraction of games in which each card was played at least once.
    """
    played = (
        games[["game_id", "played_cards"]]
        .explode("played_cards")
        .dropna()
        .rename(columns={"played_cards": "card"})
    )

    occurrence = (
        played.groupby("card")["game_id"]
        .nunique()
        .div(games["game_id"].nunique())
        .rename("occurrence")
        .reset_index()
    )

    return occurrence


def card_elite_occurrence(games, elite_share=0.05):
    """
    Fraction of elite games in which each card was played.

    Elite games are the games with the LOWEST VP.
    """
    n_elite = max(1, round(len(games) * elite_share))
    elite = games.nsmallest(n_elite, "vp")

    played = (
        elite[["game_id", "played_cards"]]
        .explode("played_cards")
        .dropna()
        .rename(columns={"played_cards": "card"})
    )

    occurrence = (
        played.groupby("card")["game_id"]
        .nunique()
        .div(elite["game_id"].nunique())
        .rename("elite_occurrence")
        .reset_index()
    )

    return occurrence


def card_enrichment(games, elite_share=0.05):
    """
    Compare card occurrence in elite games with occurrence in all games.

    enrichment = elite occurrence / overall occurrence

    1.0 = neutral
    >1  = overrepresented in good games
    <1  = underrepresented in good games
    """
    overall = card_occurrence(games)
    elite = card_elite_occurrence(games, elite_share=elite_share)

    result = overall.merge(elite, on="card", how="outer").fillna(0)

    result["enrichment"] = (
        result["elite_occurrence"] / result["occurrence"]
    )

    result["elite_difference"] = (
        result["elite_occurrence"] - result["occurrence"]
    )

    return result


def card_vp_lift(games):
    """
    Association between playing a card and final VP.

    Positive lift = better games, because lower VP is better.

    vp_lift =
        mean VP without card
        - mean VP with card
    """
    cards = sorted({
        card
        for played_cards in games["played_cards"]
        for card in played_cards
    })

    rows = []

    for card in cards:
        has_card = games["played_cards"].apply(lambda played: card in played)

        vp_with = games.loc[has_card, "vp"]
        vp_without = games.loc[~has_card, "vp"]

        rows.append({
            "card": card,
            "games_with_card": len(vp_with),
            "games_without_card": len(vp_without),
            "mean_vp_with": vp_with.mean(),
            "mean_vp_without": vp_without.mean(),
            "vp_lift": vp_without.mean() - vp_with.mean(),
        })

    return pd.DataFrame(rows)


def card_round_summary(plays):
    """
    When is each card typically played?
    Requires simulation with log_choices=True.
    """
    if plays.empty:
        return pd.DataFrame(
            columns=[
                "card",
                "times_played",
                "mean_round",
                "median_round",
            ]
        )

    return (
        plays.groupby("chosen_card")
        .agg(
            times_played=("chosen_card", "size"),
            mean_round=("round", "mean"),
            median_round=("round", "median"),
        )
        .reset_index()
        .rename(columns={"chosen_card": "card"})
    )


def card_opportunity_summary(plays):
    """
    How often was each card available and selected?

    Requires simulation with log_choices=True.

    selection_rate =
        times selected / times playable

    If offered_cards was logged, offered counts are included as well.
    """
    if plays.empty:
        return pd.DataFrame(
            columns=[
                "card",
                "offered",
                "playable",
                "selected",
                "selection_rate",
            ]
        )

    playable = (
        plays[["game_id", "action", "playable_cards"]]
        .explode("playable_cards")
        .dropna()
        .rename(columns={"playable_cards": "card"})
    )

    playable_counts = (
        playable.groupby("card")
        .size()
        .rename("playable")
    )

    selected_counts = (
        plays.groupby("chosen_card")
        .size()
        .rename("selected")
    )
    selected_counts.index.name = "card"

    result = pd.concat(
        [playable_counts, selected_counts],
        axis=1,
    ).fillna(0)

    if "offered_cards" in plays.columns:
        offered = (
            plays[["game_id", "action", "offered_cards"]]
            .explode("offered_cards")
            .dropna()
            .rename(columns={"offered_cards": "card"})
        )

        offered_counts = (
            offered.groupby("card")
            .size()
            .rename("offered")
        )

        result = pd.concat(
            [offered_counts, result],
            axis=1,
        ).fillna(0)

    result["selection_rate"] = (
        result["selected"] / result["playable"]
    )

    return result.reset_index()


def card_strategy_summary(plays):
    """
    Card selection frequencies by strategy.
    Requires simulation with log_choices=True.
    """
    if plays.empty or "strategy" not in plays.columns:
        return pd.DataFrame()

    counts = (
        plays.groupby(["strategy", "chosen_card"])
        .size()
        .rename("selected")
        .reset_index()
        .rename(columns={"chosen_card": "card"})
    )

    totals = (
        plays.groupby("strategy")
        .size()
        .rename("all_selections")
        .reset_index()
    )

    result = counts.merge(totals, on="strategy")
    result["selection_share"] = (
        result["selected"] / result["all_selections"]
    )

    return result


def add_card_names(table, game_data):
    """
    Add card name/category information from loaded game_data.

    Works even though Count creates several physical copies with the same id.
    """
    cards = (
        game_data["cards"]
        if isinstance(game_data["cards"], pd.DataFrame)
        else pd.DataFrame(game_data["cards"])
    )

    columns = ["id"]

    for column in [
        "Name",
        "Name EN",
        "Title",
        "Title EN",
        "Slot/Stapel",
    ]:
        if column in cards.columns:
            columns.append(column)

    info = (
        cards[columns]
        .drop_duplicates("id")
        .rename(columns={"id": "card"})
    )

    return table.merge(info, on="card", how="left")


def card_analysis(games, plays=None, game_data=None, elite_share=0.05):
    """
    Combined card-level analysis table.

    This is the main convenience function for notebook use.
    """
    result = card_enrichment(
        games,
        elite_share=elite_share,
    )

    result = result.merge(
        card_vp_lift(games),
        on="card",
        how="outer",
    )

    if plays is not None and not plays.empty:
        result = result.merge(
            card_round_summary(plays),
            on="card",
            how="outer",
        )

        result = result.merge(
            card_opportunity_summary(plays),
            on="card",
            how="outer",
        )

    if game_data is not None:
        result = add_card_names(result, game_data)

    return result.sort_values(
        "enrichment",
        ascending=False,
    ).reset_index(drop=True)
