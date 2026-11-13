from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


try:
    from card_colors import slot_colors, default_color
except ImportError:
    slot_colors = {
        "Abgabe": "#f7bdd3",
        "Dämmung": "#fddbab",
        "Dachnutzung": "#f6af79",
        "Fenster": "#d3edfa",
        "*Flexibilität": "#EAEEC0",
        "*Effizienz": "#9aa8cb",
        "Lüftung": "#9fd1ea",
        "Wärmeerzeugung": "#f08e9d",
        "*Zufriedenheit": "#DAF2D2",
    }
    default_color = "#cccccc"


SLOT_ORDER = [
    "Abgabe",
    "Dämmung",
    "Dachnutzung",
    "Fenster",
    "*Flexibilität",
    "*Effizienz",
    "Lüftung",
    "Wärmeerzeugung",
    "*Zufriedenheit",
]


@dataclass
class AnalysisConfig:
    version_dir: Path
    output_dir: Path | None = None
    final_round: int = 4
    top_percent: float = 0.01
    min_games: int = 100
    show_plots: bool = False
    save_plots: bool = True

    def __post_init__(self) -> None:
        self.version_dir = Path(self.version_dir)
        if self.output_dir is None:
            self.output_dir = self.version_dir / "analysis"
        else:
            self.output_dir = Path(self.output_dir)


@dataclass
class AnalysisResults:
    history: pd.DataFrame
    cards: pd.DataFrame
    final_games: pd.DataFrame
    plays_df: pd.DataFrame
    game_cards: pd.DataFrame
    best_percent: pd.DataFrame
    top_cards: pd.DataFrame
    card_results: pd.DataFrame


def load_version(version_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    version_dir = Path(version_dir)

    history_path = version_dir / "History.parquet"
    cards_path = version_dir / "cards.pkl"

    if not history_path.exists():
        raise FileNotFoundError(f"Missing file: {history_path}")

    if not cards_path.exists():
        raise FileNotFoundError(f"Missing file: {cards_path}")

    history = pd.read_parquet(history_path)
    cards = pd.read_pickle(cards_path)

    validate_inputs(history, cards)

    return history, cards


def validate_inputs(history: pd.DataFrame, cards: pd.DataFrame) -> None:
    required_history_cols = {
        "game_id",
        "runde",
        "sp",
        "budget",
        "played_cards_log",
    }

    required_card_cols = {
        "id",
        "Name",
        "Slot/Stapel",
        "Kosten",
    }

    missing_history = required_history_cols - set(history.columns)
    missing_cards = required_card_cols - set(cards.columns)

    if missing_history:
        raise ValueError(f"History.parquet is missing columns: {sorted(missing_history)}")

    if missing_cards:
        raise ValueError(f"cards.pkl is missing columns: {sorted(missing_cards)}")

    if cards["id"].duplicated().any():
        duplicated = cards.loc[cards["id"].duplicated(), "id"].tolist()
        raise ValueError(f"Duplicate card IDs found: {duplicated[:10]}")


def get_final_games(history: pd.DataFrame, final_round: int = 4) -> pd.DataFrame:
    final_games = (
        history
        .loc[history["runde"].eq(final_round)]
        .drop_duplicates(subset="game_id")
        .copy()
    )

    if final_games.empty:
        raise ValueError(f"No games found for runde == {final_round}")

    if not final_games["game_id"].is_unique:
        raise ValueError("Final games still contain duplicate game_id values.")

    return final_games


def normalize_played_cards_log(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []

    if isinstance(value, float) and np.isnan(value):
        return []

    if isinstance(value, np.ndarray):
        value = value.tolist()

    if not isinstance(value, list):
        return []

    return value


def build_plays_df(final_games: pd.DataFrame, cards: pd.DataFrame) -> pd.DataFrame:
    tmp = final_games[["game_id", "sp", "played_cards_log"]].copy()
    tmp["played_cards_log"] = tmp["played_cards_log"].apply(normalize_played_cards_log)

    plays_df = (
        tmp
        .explode("played_cards_log", ignore_index=True)
        .dropna(subset=["played_cards_log"])
    )

    if plays_df.empty:
        raise ValueError("No played cards found in played_cards_log.")

    plays_df["card_id"] = plays_df["played_cards_log"].apply(
        lambda entry: entry.get("card_id")
    )

    plays_df["played_round"] = plays_df["played_cards_log"].apply(
        lambda entry: entry.get("runde")
    )

    plays_df = (
        plays_df
        .drop(columns="played_cards_log")
        .merge(
            cards[["id", "Name", "Slot/Stapel", "Kosten"]].drop_duplicates("id"),
            left_on="card_id",
            right_on="id",
            how="left",
            validate="many_to_one",
        )
        .drop(columns="id")
    )

    return plays_df


def build_game_cards(plays_df: pd.DataFrame) -> pd.DataFrame:
    return (
        plays_df[
            [
                "game_id",
                "card_id",
                "Name",
                "Slot/Stapel",
                "Kosten",
                "sp",
                "played_round",
            ]
        ]
        .drop_duplicates(["game_id", "card_id", "played_round"])
        .copy()
    )


def get_best_percent(final_games: pd.DataFrame, top_percent: float = 0.01) -> pd.DataFrame:
    n = max(1, round(len(final_games) * top_percent))

    return (
        final_games
        .nlargest(n, "sp")
        .copy()
    )


def add_card_names_to_best_games(
    best_percent: pd.DataFrame,
    cards: pd.DataFrame,
) -> pd.DataFrame:
    id_to_name = cards.set_index("id")["Name"].to_dict()

    best_percent = best_percent.copy()

    def extract_names(log: Any) -> list[str]:
        entries = normalize_played_cards_log(log)
        return [
            id_to_name.get(entry.get("card_id"), f"Unknown card ID {entry.get('card_id')}")
            for entry in entries
        ]

    best_percent["all_installed_cards"] = (
        best_percent["played_cards_log"].apply(extract_names)
    )

    return best_percent


def compute_top_cards(best_percent: pd.DataFrame, cards: pd.DataFrame) -> pd.DataFrame:
    exploded = (
        best_percent[["game_id", "all_installed_cards"]]
        .explode("all_installed_cards")
        .dropna(subset=["all_installed_cards"])
        .rename(columns={"all_installed_cards": "Karte"})
    )

    top_cards = (
        exploded
        .groupby("Karte", as_index=False)
        .agg(Anzahl=("game_id", "nunique"))
        .sort_values("Anzahl", ascending=False)
        .reset_index(drop=True)
    )

    top_cards = (
        top_cards
        .merge(
            cards[["Name", "Slot/Stapel"]].drop_duplicates("Name"),
            left_on="Karte",
            right_on="Name",
            how="left",
        )
        .drop(columns="Name")
    )

    top_cards["Anteil_Top_Percent"] = top_cards["Anzahl"] / len(best_percent)

    return top_cards


def compute_card_results(
    game_cards: pd.DataFrame,
    final_games: pd.DataFrame,
) -> pd.DataFrame:
    n_games = len(final_games)
    total_sp = final_games["sp"].sum()

    card_results = (
        game_cards
        .groupby(
            ["card_id", "Name", "Slot/Stapel", "Kosten"],
            dropna=False,
        )
        .agg(
            games_with_card=("game_id", "nunique"),
            sp_sum_with_card=("sp", "sum"),
            mean_sp_with_card=("sp", "mean"),
            mean_played_round=("played_round", "mean"),
        )
        .reset_index()
    )

    card_results["games_without_card"] = (
        n_games - card_results["games_with_card"]
    )

    card_results["mean_sp_without_card"] = np.where(
        card_results["games_without_card"] > 0,
        (
            total_sp - card_results["sp_sum_with_card"]
        ) / card_results["games_without_card"],
        np.nan,
    )

    card_results["sp_uplift"] = (
        card_results["mean_sp_with_card"]
        - card_results["mean_sp_without_card"]
    )

    card_results["play_rate"] = (
        card_results["games_with_card"] / n_games
    )

    return card_results.sort_values(
        ["sp_uplift", "games_with_card"],
        ascending=False,
    )


def ensure_output_dir(config: AnalysisConfig) -> Path:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_tables(results: AnalysisResults, output_dir: Path) -> None:
    results.final_games.to_csv(output_dir / "final_games.csv", index=False)
    results.plays_df.to_csv(output_dir / "plays_df.csv", index=False)
    results.game_cards.to_csv(output_dir / "game_cards.csv", index=False)
    results.best_percent.to_csv(output_dir / "best_percent.csv", index=False)
    results.top_cards.to_csv(output_dir / "top_cards_top_percent.csv", index=False)
    results.card_results.to_csv(output_dir / "card_results.csv", index=False)


def finish_plot(
    fig: plt.Figure,
    output_path: Path | None,
    show: bool,
) -> None:
    fig.tight_layout()

    if output_path is not None:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_sp_distribution(
    final_games: pd.DataFrame,
    output_path: Path | None = None,
    show: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.hist(
        final_games["sp"],
        bins=range(int(final_games["sp"].min()), int(final_games["sp"].max()) + 2),
        edgecolor="black",
        alpha=0.85,
    )

    ax.set_title("Distribution of final victory points")
    ax.set_xlabel("Final SP")
    ax.set_ylabel("Number of games")
    ax.grid(axis="y", alpha=0.2)

    finish_plot(fig, output_path, show)


def plot_sp_zufriedenheit_heatmap(
    final_games: pd.DataFrame,
    output_path: Path | None = None,
    show: bool = False,
) -> None:
    matrix = pd.crosstab(
        final_games["zufriedenheit"],
        final_games["sp"],
    )

    fig, ax = plt.subplots(figsize=(11, 6))

    image = ax.imshow(
        matrix,
        aspect="auto",
        origin="lower",
    )

    ax.set_title("Games by satisfaction and final SP")
    ax.set_xlabel("Final SP")
    ax.set_ylabel("Zufriedenheit")

    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=90, fontsize=7)

    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)

    fig.colorbar(image, ax=ax, label="Number of games")

    finish_plot(fig, output_path, show)


def plot_top_cards(
    top_cards: pd.DataFrame,
    output_path: Path | None = None,
    show: bool = False,
    top_n: int = 30,
) -> None:
    plot_data = (
        top_cards
        .head(top_n)
        .sort_values("Anzahl")
        .copy()
    )

    bar_colors = (
        plot_data["Slot/Stapel"]
        .map(slot_colors)
        .fillna(default_color)
    )

    fig, ax = plt.subplots(figsize=(9, max(7, 0.35 * len(plot_data))))

    ax.barh(
        plot_data["Karte"],
        plot_data["Anzahl"],
        color=bar_colors,
        edgecolor="black",
        linewidth=0.4,
    )

    ax.set_title("Most frequent cards in top games")
    ax.set_xlabel("Occurrences in top games")
    ax.set_ylabel("Card")
    ax.grid(axis="x", alpha=0.2)

    finish_plot(fig, output_path, show)


def plot_card_effect_scatter(
    card_results: pd.DataFrame,
    output_path: Path | None = None,
    show: bool = False,
    min_games: int = 100,
    annotate: bool = True,
) -> None:
    plot_data = (
        card_results
        .loc[card_results["games_with_card"] >= min_games]
        .dropna(subset=["sp_uplift", "Kosten", "Name", "Slot/Stapel", "games_with_card"])
        .copy()
    )

    if plot_data.empty:
        return

    size_scale = 5
    plot_data["marker_size"] = (
        plot_data["Kosten"].clip(lower=0) * size_scale + 5
    ) ** 2

    fig, ax = plt.subplots(figsize=(14, 10))

    for slot, group in plot_data.groupby("Slot/Stapel", sort=False):
        ax.scatter(
            group["sp_uplift"],
            group["games_with_card"],
            color=slot_colors.get(slot, default_color),
            edgecolor="black",
            linewidth=0.5,
            s=group["marker_size"],
            alpha=0.85,
            label=slot,
        )

    if annotate:
        for _, row in plot_data.iterrows():
            ax.annotate(
                row["Name"],
                xy=(row["sp_uplift"], row["games_with_card"]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                rotation=45,
                rotation_mode="anchor",
            )

    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title("Card occurrence and effect on final victory points")
    ax.set_xlabel("SP uplift: mean SP with card − mean SP without card")
    ax.set_ylabel("Number of games in which card was played")
    ax.grid(alpha=0.2)

    ax.legend(
        title="Slot",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
    )

    finish_plot(fig, output_path, show)


def build_card_index(plays_df: pd.DataFrame) -> pd.DataFrame:
    card_index = (
        plays_df[["card_id", "Name", "Slot/Stapel"]]
        .drop_duplicates()
        .copy()
    )

    card_index["slot_sort"] = pd.Categorical(
        card_index["Slot/Stapel"],
        categories=SLOT_ORDER,
        ordered=True,
    )

    return (
        card_index
        .sort_values(["slot_sort", "Name"])
        .reset_index(drop=True)
    )


def plot_round_card_boxplots(
    plays_df: pd.DataFrame,
    output_path: Path | None = None,
    show: bool = False,
) -> None:
    card_index = build_card_index(plays_df)
    positions = np.arange(len(card_index))

    slot_groups = (
        card_index
        .reset_index()
        .groupby("Slot/Stapel", sort=False, observed=True)
        .agg(
            start=("index", "min"),
            end=("index", "max"),
        )
        .reset_index()
    )

    fig, axes = plt.subplots(
        nrows=4,
        ncols=1,
        figsize=(22, 16),
        sharex=True,
        sharey=True,
        squeeze=False,
    )

    axes = axes.flatten()

    for ax, round_number in zip(axes, [1, 2, 3, 4]):
        distributions = []
        valid_positions = []
        valid_slots = []
        missing_cards = []

        for position, card in card_index.iterrows():
            values = (
                plays_df.loc[
                    plays_df["card_id"].eq(card["card_id"])
                    & plays_df["played_round"].eq(round_number),
                    "sp",
                ]
                .dropna()
                .to_numpy()
            )

            if len(values) > 0:
                distributions.append(values)
                valid_positions.append(position)
                valid_slots.append(card["Slot/Stapel"])
            else:
                missing_cards.append((position, card["Slot/Stapel"]))

        if distributions:
            boxplot = ax.boxplot(
                distributions,
                positions=valid_positions,
                widths=0.65,
                patch_artist=True,
                showfliers=False,
                showmeans=True,
                medianprops={"color": "black", "linewidth": 1.2},
                meanprops={
                    "marker": "o",
                    "markerfacecolor": "white",
                    "markeredgecolor": "black",
                    "markersize": 4,
                },
                whiskerprops={"color": "black", "linewidth": 0.8},
                capprops={"color": "black", "linewidth": 0.8},
            )

            for box, slot in zip(boxplot["boxes"], valid_slots):
                box.set_facecolor(slot_colors.get(slot, default_color))
                box.set_edgecolor("black")
                box.set_alpha(0.85)

        ymin, ymax = ax.get_ylim()
        marker_y = ymin + 0.05 * (ymax - ymin) if ymax > ymin else 0

        for position, slot in missing_cards:
            ax.plot(
                position,
                marker_y,
                marker="x",
                color=slot_colors.get(slot, default_color),
                markersize=5,
                alpha=0.7,
            )

        ax.set_title(f"Round {round_number}")
        ax.set_ylabel("Final SP")
        ax.grid(axis="y", alpha=0.2)

        for _, group in slot_groups.iterrows():
            start = group["start"]
            end = group["end"]
            slot = group["Slot/Stapel"]

            ax.axvline(
                end + 0.5,
                color="grey",
                linewidth=0.7,
                alpha=0.5,
            )

            midpoint = (start + end) / 2

            ax.text(
                midpoint,
                0.97,
                slot,
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=9,
                fontweight="bold",
                color=slot_colors.get(slot, default_color),
            )

    axes[-1].set_xticks(positions)
    axes[-1].set_xticklabels(
        card_index["Name"],
        rotation=45,
        ha="right",
        fontsize=8,
    )
    axes[-1].set_xlabel("Card")

    fig.suptitle(
        "Final-SP distribution by card and playing round",
        fontsize=15,
    )

    finish_plot(fig, output_path, show)


def run_analysis(
    version_dir: str | Path,
    *,
    top_percent: float = 0.01,
    min_games: int = 100,
    show_plots: bool = False,
    save_plots: bool = True,
) -> AnalysisResults:
    config = AnalysisConfig(
        version_dir=Path(version_dir),
        top_percent=top_percent,
        min_games=min_games,
        show_plots=show_plots,
        save_plots=save_plots,
    )

    output_dir = ensure_output_dir(config)

    history, cards = load_version(config.version_dir)
    final_games = get_final_games(history, config.final_round)
    plays_df = build_plays_df(final_games, cards)
    game_cards = build_game_cards(plays_df)

    best_percent = get_best_percent(final_games, config.top_percent)
    best_percent = add_card_names_to_best_games(best_percent, cards)

    top_cards = compute_top_cards(best_percent, cards)
    card_results = compute_card_results(game_cards, final_games)

    results = AnalysisResults(
        history=history,
        cards=cards,
        final_games=final_games,
        plays_df=plays_df,
        game_cards=game_cards,
        best_percent=best_percent,
        top_cards=top_cards,
        card_results=card_results,
    )

    save_tables(results, output_dir)

    if config.save_plots or config.show_plots:
        plot_sp_distribution(
            final_games,
            output_dir / "01_sp_distribution.png" if config.save_plots else None,
            config.show_plots,
        )

        if "zufriedenheit" in final_games.columns:
            plot_sp_zufriedenheit_heatmap(
                final_games,
                output_dir / "02_sp_zufriedenheit_heatmap.png" if config.save_plots else None,
                config.show_plots,
            )

        plot_top_cards(
            top_cards,
            output_dir / "03_top_cards.png" if config.save_plots else None,
            config.show_plots,
        )

        plot_card_effect_scatter(
            card_results,
            output_dir / "04_card_effect_scatter.png" if config.save_plots else None,
            config.show_plots,
            min_games=config.min_games,
        )

        plot_round_card_boxplots(
            plays_df,
            output_dir / "05_round_card_boxplots.png" if config.save_plots else None,
            config.show_plots,
        )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze Monte Carlo runs for The Renovation Game."
    )

    parser.add_argument(
        "version_dir",
        type=Path,
        help="Directory containing History.parquet and cards.pkl.",
    )

    parser.add_argument(
        "--top-percent",
        type=float,
        default=0.01,
        help="Share of best final games to analyse. Default: 0.01.",
    )

    parser.add_argument(
        "--min-games",
        type=int,
        default=100,
        help="Minimum number of card plays for effect plots. Default: 100.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Show plots interactively.",
    )

    parser.add_argument(
        "--no-save-plots",
        action="store_true",
        help="Do not save plots to the analysis directory.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_analysis(
        args.version_dir,
        top_percent=args.top_percent,
        min_games=args.min_games,
        show_plots=args.show,
        save_plots=not args.no_save_plots,
    )


if __name__ == "__main__":
    main()