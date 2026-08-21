from pathlib import Path
import random
import time

import pandas as pd

from model.game import (
    load_game_data,
    new_game,
    playable_cards,
    play_card,
    score_round,
)
from model.rules import offer_cards
from model.strategies.random import choose_card as random_strategy


def simulate_game(
    game_data,
    game_id=0,
    strategy=random_strategy,
    strategy_name="random",
    rule="free_choice",
    draw_n=7,
    category_count=1,
    cards_per_category=3,
    pass_probability=0.0,
    seed=None,
    log_choices=False,
):
    """
    Simulate one complete game.

    Rules controlling the choice set are passed to offer_cards().
    The player may voluntarily end a round according to pass_probability.
    """
    rng = random.Random(seed)
    state = new_game(game_data, game_id=game_id)
    plays = []

    action = 0
    rounds_played = 0

    max_demand = len(game_data["board"]["demand_grid"]) - 1
    max_satisfaction = len(game_data["board"]["satisfaction_budget"]) - 1

    while state["round"] <= game_data["board"]["max_rounds"]:
        turn = 0

        while True:
            offered = offer_cards(
                game_data["cards"],
                state,
                rule=rule,
                n=draw_n,
                category_count=category_count,
                cards_per_category=cards_per_category,
                rng=rng,
            )

            playable = playable_cards(
                offered,
                state,
                max_demand,
                max_satisfaction,
            )

            if not playable:
                break

            if log_choices:
                event = {
                    "game_id": game_id,
                    "seed": seed,
                    "strategy": strategy_name,
                    "rule": rule,
                    "draw_n": draw_n,
                    "category_count": category_count,
                    "cards_per_category": cards_per_category,
                    "pass_probability": pass_probability,
                    "round": state["round"],
                    "turn": turn,
                    "action": action,
                    "offered_cards": [
                        card["card_id"] for card in offered
                    ],
                    "playable_cards": [
                        card["card_id"] for card in playable
                    ],
                    "vp_before": state["vp"],
                    "budget_before": state["budget"],
                }

            if rng.random() < pass_probability:
                if log_choices:
                    plays.append({
                        **event,
                        "chosen_card": None,
                        "passed": True,
                        "vp_after_card": state["vp"],
                        "budget_after_card": state["budget"],
                    })
                action += 1
                break

            card = strategy(
                playable,
                state,
                rng,
            )

            play_card(
                card,
                state,
                game_data,
            )

            if log_choices:
                plays.append({
                    **event,
                    "chosen_card": card["card_id"],
                    "passed": False,
                    "vp_after_card": state["vp"],
                    "budget_after_card": state["budget"],
                })

            turn += 1
            action += 1

        score_round(state, game_data)
        rounds_played += 1

        if state["budget"] < 0:
            break

        state["round"] += 1

    final_state = {
        **state,
        "strategy": strategy_name,
        "rule": rule,
        "draw_n": draw_n,
        "category_count": category_count,
        "cards_per_category": cards_per_category,
        "pass_probability": pass_probability,
        "seed": seed,
        "rounds_played": rounds_played,
        "n_cards_played": len(state["played_cards"]),

        # Make set-valued columns easy to save as Parquet.
        "played_cards": sorted(state["played_cards"]),
        "excluded_ids": sorted(state["excluded_ids"]),
        "occupied_slots": sorted(state["occupied_slots"]),
    }

    return final_state, plays


def run_simulation(
    version,
    n_games=10_000,
    strategy=random_strategy,
    strategy_name="random",
    rule="free_choice",
    draw_n=7,
    category_count=1,
    cards_per_category=3,
    pass_probability=0.0,
    seed=42,
    save=True,
    log_choices=False,
):
    """
    Run one Monte Carlo condition for one game version.
    """
    version = Path(version)
    game_data = load_game_data(version)

    master_rng = random.Random(seed)

    games = []
    plays = []

    start = time.perf_counter()

    for game_id in range(n_games):
        game_seed = master_rng.randrange(2**32)

        final_state, game_plays = simulate_game(
            game_data,
            game_id=game_id,
            strategy=strategy,
            strategy_name=strategy_name,
            rule=rule,
            draw_n=draw_n,
            category_count=category_count,
            cards_per_category=cards_per_category,
            pass_probability=pass_probability,
            seed=game_seed,
            log_choices=log_choices,
        )

        games.append(final_state)
        plays.extend(game_plays)

        if (game_id + 1) % 1000 == 0:
            rate = (game_id + 1) / (time.perf_counter() - start)
            print(
                f"\r{game_id+1:,}/{n_games:,} games | {rate:,.0f} games/s",
                end="",
            )

    if n_games >= 1000:
        print()

    games = pd.DataFrame(games)
    plays = pd.DataFrame(plays)

    if save:
        results = version / "results"
        results.mkdir(exist_ok=True)

        games.to_parquet(results / "games.parquet", index=False)

        if log_choices:
            plays.to_parquet(results / "plays.parquet", index=False)

    return games, plays