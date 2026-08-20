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
    seed=None,
    log_choices=False,
):
    """
    Simulate one game.

    Returns
    -------
    final_state : dict
        Final game state.

    plays : list[dict]
        One row per card choice, including offered, playable and chosen cards.
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

        while state["budget"] >= 0:

            offered = offer_cards(
                game_data["cards"],
                state,
                rule=rule,
                n=draw_n,
                rng=rng,
            )

            playable = playable_cards(offered, state, max_demand,max_satisfaction)

            if not playable:
                break

            chosen = strategy(playable, state, rng)

            turn += 1
            action += 1


            play_card(
                chosen,
                state,
                game_data,
            )

            if log_choices:
                vp_before = state["vp"]
                budget_before = state["budget"]
                plays.append({
                    "game_id": game_id,
                    "seed": seed,
                    "strategy": strategy_name,
                    "rule": rule,
                    "round": state["round"],
                    "turn": turn,
                    "action": action,

                    # Repeated ids are intentional when the deck contains
                    # several physical copies of the same logical card.
                    "offered_cards": [card["card_id"] for card in offered],
                    "playable_cards": [card["card_id"] for card in playable],
                    "chosen_card": chosen["card_id"],

                    "vp_before": vp_before,
                    "vp_after_card": state["vp"],
                    "budget_before": budget_before,
                    "budget_after_card": state["budget"],
                })

        score_round(state, game_data)
        rounds_played += 1

        if state["budget"] < 0:
            break

        state["round"] += 1

    final_state = {
        **state,
        "strategy": strategy_name,
        "rule": rule,
        "seed": seed,
        "rounds_played": rounds_played,
        "n_cards_played": len(state["played_cards"]),

        # Make set-valued columns easier to save.
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
    seed=42,
    save=True,
    log_choices=False,
):
    """
    Run a Monte Carlo simulation for one game version.

    Notebook example
    ----------------
    games, plays = run_simulation(
        "../Versionen/paper_draft_v1",
        n_games=10_000,
        rule="random_draw",
        draw_n=7,
    )
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
            seed=game_seed,
            log_choices=log_choices,
        )

        games.append(final_state)
        plays.extend(game_plays)
        if (game_id + 1) % 1000 == 0:
            print(f"\r{game_id+1:,}/{n_games:,} games | {(game_id+1)/(time.perf_counter()-start):,.0f} games/s", end="")

    games = pd.DataFrame(games)
    plays = pd.DataFrame(plays)

    if save:
        results = version / "results"
        results.mkdir(exist_ok=True)

        games.to_parquet(results / "games.parquet", index=False)
        plays.to_parquet(results / "plays.parquet", index=False)

    return games, plays
