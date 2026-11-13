import numpy as np
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


def card_elite_sensitivity(games, elite_shares=(0.01, 0.05, 0.10)):
    """
    Card enrichment for several elite cutoffs.
    """
    tables = []

    for elite_share in elite_shares:
        table = card_enrichment(games, elite_share=elite_share)
        table["elite_share"] = elite_share
        tables.append(table)

    return pd.concat(tables, ignore_index=True)


def card_vp_lift(games):
    """
    Association between playing a card and final VP.

    Positive lift = better games, because lower VP is better.

    vp_lift =
        mean VP without card
        - mean VP with card

    If a card occurs in all games or no games, VP lift cannot be estimated
    and is returned as NaN.
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

        n_with = len(vp_with)
        n_without = len(vp_without)

        mean_with = vp_with.mean() if n_with else np.nan
        mean_without = vp_without.mean() if n_without else np.nan

        if n_with and n_without:
            lift = mean_without - mean_with
        else:
            lift = np.nan

        # CI requires at least two observations in both groups
        if n_with >= 2 and n_without >= 2:
            se = np.sqrt(
                vp_with.var(ddof=1) / n_with
                + vp_without.var(ddof=1) / n_without
            )

            ci_low = lift - 1.96 * se
            ci_high = lift + 1.96 * se
        else:
            ci_low = np.nan
            ci_high = np.nan

        rows.append({
            "card": card,
            "games_with_card": n_with,
            "games_without_card": n_without,
            "mean_vp_with": mean_with,
            "mean_vp_without": mean_without,
            "vp_lift": lift,
            "vp_lift_ci_low": ci_low,
            "vp_lift_ci_high": ci_high,
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
    How often was each logical card available and selected?

    Repeated physical copies of the same card count as ONE opportunity
    per decision.

    selection_rate =
        decisions where selected / decisions where playable
    """
    if plays.empty:
        return pd.DataFrame(
            columns=[
                "card",
                "offered_opportunities",
                "playable_opportunities",
                "selected",
                "selection_rate",
            ]
        )

    decision_columns = [
        column
        for column in ["strategy", "rule", "game_id", "action"]
        if column in plays.columns
    ]

    if "action" not in decision_columns:
        decision_columns += [
            column
            for column in ["round", "turn"]
            if column in plays.columns
        ]

    playable = (
        plays[decision_columns + ["playable_cards"]]
        .explode("playable_cards")
        .dropna(subset=["playable_cards"])
        .rename(columns={"playable_cards": "card"})
        .drop_duplicates(decision_columns + ["card"])
    )

    playable_counts = (
        playable.groupby("card")
        .size()
        .rename("playable_opportunities")
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
            plays[decision_columns + ["offered_cards"]]
            .explode("offered_cards")
            .dropna(subset=["offered_cards"])
            .rename(columns={"offered_cards": "card"})
            .drop_duplicates(decision_columns + ["card"])
        )

        offered_counts = (
            offered.groupby("card")
            .size()
            .rename("offered_opportunities")
        )

        result = pd.concat(
            [offered_counts, result],
            axis=1,
        ).fillna(0)

    result["selection_rate"] = (
        result["selected"] / result["playable_opportunities"]
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


def add_card_info(table, game_data):
    """
    Add stable card id, English label, category and copy count.
    """
    cards = pd.DataFrame(game_data["cards"])

    columns = [
        column
        for column in ["card_id", "label_en", "Slot/Stapel", "Count"]
        if column in cards.columns
    ]

    info = (
        cards[columns]
        .drop_duplicates("card_id")
        .rename(columns={
            "card_id": "card",
            "Slot/Stapel": "category",
            "Count": "copies",
        })
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
        result = add_card_info(result, game_data)

    return result.sort_values(
        "enrichment",
        ascending=False,
    ).reset_index(drop=True)


import matplotlib.pyplot as plt


def plot_game_distributions(games):
    """
    Overview of final game-state distributions.
    """
    columns = [
        ("embodied_emissions", "Embodied emissions"),
        ("thermal_protection", "Thermal protection"),
        ("electricity_demand", "Electricity demand"),
        ("storage", "Storage"),
        ("electricity_generation", "Electricity generation"),
        ("satisfaction", "Satisfaction"),
        ("budget", "Budget"),
        ("vp", "Victory points"),
    ]

    columns = [(col, label) for col, label in columns if col in games.columns]

    fig, axes = plt.subplots(
        1,
        len(columns),
        figsize=(2.6 * len(columns), 3),
        constrained_layout=True,
    )

    if len(columns) == 1:
        axes = [axes]

    for ax, (column, label) in zip(axes, columns):
        ax.hist(games[column], bins="auto")
        ax.set_title(label)
        ax.set_ylabel("Games")

    return fig, axes
def plot_vp_distribution(games, elite_share=0.05):
    """
    Final VP distribution with the elite threshold marked.
    Lower VP is better.
    """
    threshold = games["vp"].quantile(elite_share)

    fig, ax = plt.subplots(figsize=(7, 4))

    ax.hist(games["vp"], bins=50)
    ax.axvline(
        threshold,
        linestyle="--",
        label=f"Best {elite_share:.0%}",
    )

    ax.set_xlabel("Victory points")
    ax.set_ylabel("Games")
    ax.set_title("Distribution of final victory points")
    ax.legend()

    return fig, ax

def plot_state_vs_vp(games, variable="satisfaction"):
    """
    Mean VP by final state level.
    Lower VP is better.
    """
    data = (
        games.groupby(variable)["vp"]
        .agg(["mean", "median", "count"])
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(
        data[variable],
        data["mean"],
        marker="o",
        label="Mean VP",
    )

    ax.plot(
        data[variable],
        data["median"],
        marker="o",
        linestyle="--",
        label="Median VP",
    )

    ax.set_xlabel(variable.replace("_", " ").title())
    ax.set_ylabel("Victory points")
    ax.legend()

    return fig, ax

def plot_card_enrichment(card_results, label_column="label_en", min_occurrence=0.02):
    """
    Overall occurrence versus elite occurrence.

    Cards above the diagonal are overrepresented in elite games.
    """
    data = card_results.loc[
        card_results["occurrence"] >= min_occurrence
    ].copy()

    fig, ax = plt.subplots(figsize=(7, 6))

    ax.scatter(
        data["occurrence"],
        data["elite_occurrence"],
    )

    limit = max(
        data["occurrence"].max(),
        data["elite_occurrence"].max(),
    )

    ax.plot([0, limit], [0, limit], linestyle="--")

    for _, row in data.iterrows():
        label = row.get(label_column, row["card"])
        ax.annotate(
            label,
            (row["occurrence"], row["elite_occurrence"]),
            fontsize=8,
        )

    ax.set_xlabel("Occurrence in all games")
    ax.set_ylabel("Occurrence in elite games")
    ax.set_title("Card occurrence in all vs. elite games")

    return fig, ax


def plot_card_vp_lift(card_results, label_column="label_en", top_n=20):
    """
    Strongest positive and negative VP associations.

    Positive VP lift = better final VP in games containing the card.
    """
    data = (
        card_results
        .dropna(subset=["vp_lift"])
        .sort_values("vp_lift")
    )

    if len(data) > top_n:
        n_each = max(1, top_n // 2)
        data = pd.concat([
            data.head(n_each),
            data.tail(n_each),
        ]).drop_duplicates()

    labels = [
        row.get(label_column, row["card"])
        for _, row in data.iterrows()
    ]

    xerr = np.vstack([
        data["vp_lift"] - data["vp_lift_ci_low"],
        data["vp_lift_ci_high"] - data["vp_lift"],
    ])

    fig, ax = plt.subplots(figsize=(8, max(4, 0.3 * len(data))))

    ax.errorbar(
        data["vp_lift"],
        range(len(data)),
        xerr=xerr,
        fmt="o",
    )

    ax.axvline(0, linestyle="--")
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("VP lift (positive = better)")
    ax.set_title("Association between card play and final VP")

    return fig, ax
