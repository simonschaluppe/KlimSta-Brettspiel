import random

import pandas as pd

from model.game import load_game_data, new_game, playable_cards, play_card, score_round, storage_index
from model.rules import offer_cards


HEATING_LABELS = {
    0: "Gas",
    1: "Biomass",
    2: "District heating",  
    3: "Green gas",
    4: "Heat pump",
}


def start_manual(version, rule="free_choice", draw_n=7, seed=42):
    """Start a manual game session."""
    game_data = load_game_data(version)

    return {
        "game_data": game_data,
        "state": new_game(game_data, game_id="manual"),
        "rule": rule,
        "draw_n": draw_n,
        "rng": random.Random(seed),
        "offered": [],
        "playable": [],
        "round_start_cards": set(),
    }


def state_table(session):
    """Current game state as a small readable table."""
    state = session["state"]

    values = {
        "Round": state["round"],
        "Budget": state["budget"],
        "VP (lower is better)": state["vp"],
        "Embodied emissions": state["embodied_emissions"],
        "Thermal protection": state["thermal_protection"],
        "Heating system": HEATING_LABELS.get(state["heating_system"], state["heating_system"]),
        "Heat-pump efficiency": state["hp_efficiency"],
        "Electricity demand": state["electricity_demand"],
        "Electricity generation": state["electricity_generation"],
        "Storage": state["storage"],
        "Satisfaction": state["satisfaction"],
        "Grid import": state["grid_import"],
    }

    return pd.DataFrame({"value": values})


def state_table(session):
    """Current game state with the corresponding per-round effects."""
    state = session["state"]
    board = session["game_data"]["board"]

    # Current lookup effects
    embodied_vp = board["embodied_vp"][state["embodied_emissions"]]

    heating_vp = board["heating_vp"][
        state["heating_system"]
    ][state["thermal_protection"]]

    demand_grid = board["demand_grid"][state["electricity_demand"]]
    production_grid = board["production_grid"][state["electricity_generation"]]

    storage_grid = board["storage_grid"][storage_index(state)]
    satisfaction_budget = board["satisfaction_budget"][state["satisfaction"]]

    hp_efficiency = (
        None
        if state["hp_efficiency"] == -1
        else state["hp_efficiency"] + 1
    )

    values = {
        "Round": state["round"],
        "Budget": state["budget"],
        "VP (lower is better)": state["vp"],

        "Embodied emissions":
            f'{state["embodied_emissions"]} ({embodied_vp:+} VP/round)',

        "Thermal protection":
            f'{state["thermal_protection"]} ({heating_vp:+} heating VP/round)',

        "Heating system":
            HEATING_LABELS.get(
                state["heating_system"],
                state["heating_system"],
            ),

        "Heat-pump efficiency":
            hp_efficiency,

        "Electricity demand":
            f'{state["electricity_demand"]} ({demand_grid:+} grid import/round)',

        "Electricity generation":
            f'{state["electricity_generation"]} ({production_grid:+} grid import/round)',

        "Storage":
            f'{state["storage"]} ({storage_grid:+} grid import/round)',

        "Satisfaction":
            f'{state["satisfaction"]} ({satisfaction_budget:+} budget/round)',

        "Grid import":
            state["grid_import"],
    }

    return pd.DataFrame({"value": values})

def board_table(session):
    """Show the currently occupied single-card slots."""
    game_data = session["game_data"]
    state = session["state"]

    labels = {
        card["card_id"]: card.get("label_en", card["card_id"])
        for card in game_data["cards"]
    }

    rows = []

    for slot, card_id in zip(
        game_data["single_slots"],
        state["slots"],
    ):
        rows.append({
            "slot": slot,
            "card_id": card_id,
            "card": labels.get(card_id, "") if card_id else "",
        })

    return pd.DataFrame(rows)

def draw_options(session):
    """
    Apply the selected card-access rule and determine playable cards.

    Uses the same offer_cards() and playable_cards() functions as simulation.
    """
    game_data = session["game_data"]
    state = session["state"]

    offered = offer_cards(
        game_data["cards"],
        state,
        rule=session["rule"],
        n=session["draw_n"],
        rng=session["rng"],
    )

    max_demand = len(game_data["board"]["demand_grid"]) - 1
    max_satisfaction = len(game_data["board"]["satisfaction_budget"]) - 1

    playable = playable_cards(
        offered,
        state,
        max_demand,
        max_satisfaction,
    )

    session["offered"] = offered
    session["playable"] = playable

    return options_table(session)


def options_table(session):
    """
    Present currently playable cards.

    Duplicate physical copies are combined. `copies_offered` shows how many
    equivalent physical copies were present.
    """
    playable = session["playable"]

    if not playable:
        return pd.DataFrame()

    rows = []

    for card in playable:
        rows.append({
            "card_id": card["card_id"],
            "label_en": card.get("label_en", card["card_id"]),
            "category": card["Slot/Stapel"],
            "cost": card["Kosten"],
            "embodied": card["BauEmissionen"],
            "demand": card["Strombedarf"],
            "generation": card["Stromproduktion"],
            "storage": card["Stromspeicher"],
            "thermal_protection": card["Wärmeschutz"],
            "satisfaction": card["Zufriedenheit"],
            "hp_efficiency": card["Wärmepumpen-Effizienz"],
            "immediate_vp": card["SofortCO2"],
            "immediate_budget": card["SofortBudget"],
            "heating_system": card["Heizsystem"],
        })

    table = pd.DataFrame(rows)

    counts = table.groupby("card_id").size().rename("copies_offered")

    table = (
        table.drop_duplicates("card_id")
        .merge(counts, on="card_id")
        .reset_index(drop=True)
    )

    table.insert(0, "choice", range(1, len(table) + 1))

    return table


def play_choice(session, choice):
    state = session["state"]
    game_data = session["game_data"]
    table = options_table(session)

    if table.empty:
        raise ValueError("No playable cards. Call draw_options() first.")

    if isinstance(choice, int):
        matches = table.loc[table["choice"] == choice]
        if matches.empty:
            raise ValueError(f"Unknown choice number: {choice}")
        card_id = matches.iloc[0]["card_id"]
    else:
        card_id = choice

    matches = [
        card for card in session["playable"]
        if card["card_id"] == card_id
    ]

    if not matches:
        raise ValueError(f"Card is not currently playable: {card_id}")

    card = matches[0]

    before = {
        "budget": state["budget"],
        "vp": state["vp"],
        "embodied_emissions": state["embodied_emissions"],
        "thermal_protection": state["thermal_protection"],
        "electricity_demand": state["electricity_demand"],
        "electricity_generation": state["electricity_generation"],
        "storage": state["storage"],
        "satisfaction": state["satisfaction"],
        "hp_efficiency": state["hp_efficiency"],
        "heating_system": state["heating_system"],
    }

    play_card(card, state, game_data)

    card_summary = pd.DataFrame([{
        "card_id": card["card_id"],
        "card": card.get("label_en", card["card_id"]),
        "cost": card["Kosten"],
        "embodied": card["BauEmissionen"],
        "demand": card["Strombedarf"],
        "generation": card["Stromproduktion"],
        "storage": card["Stromspeicher"],
        "thermal_protection": card["Wärmeschutz"],
        "satisfaction": card["Zufriedenheit"],
        "hp_efficiency": card["Wärmepumpen-Effizienz"],
        "immediate_vp": card["SofortCO2"],
        "immediate_budget": card["SofortBudget"],
        "heating_system": card["Heizsystem"],
    }])

    changes = pd.DataFrame([
        {
            "variable": variable,
            "before": old,
            "after": state[variable],
            "change": state[variable] - old
            if isinstance(old, (int, float)) and isinstance(state[variable], (int, float))
            else None,
        }
        for variable, old in before.items()
        if old != state[variable]
    ])

    session["offered"] = []
    session["playable"] = []

    return card_summary, changes


def end_round(session):
    """
    Score the current round and show before/after changes plus scoring details.
    """
    state = session["state"]
    game_data = session["game_data"]

    before = {
        "vp": state["vp"],
        "budget": state["budget"],
        "grid_import": state["grid_import"],
    }

    details = score_round(state, game_data, return_details=True)

    changes = pd.DataFrame([
        {
            "variable": variable,
            "before": old,
            "after": state[variable],
            "change": state[variable] - old,
        }
        for variable, old in before.items()
    ])

    scoring = pd.DataFrame([
        {"component": "Embodied emissions", "vp": details["embodied_vp"], "budget": 0},
        {"component": "Heating", "vp": details["heating_vp"], "budget": details["heating_budget"]},
        {"component": "Grid import", "vp": details["grid_vp"], "budget": details["grid_budget"]},
        {"component": "Satisfaction", "vp": 0, "budget": details["satisfaction_budget"]},
    ])

    round_cards = (
        state["played_cards"]
        - session["round_start_cards"]
    )

    labels = {
        card["card_id"]: card.get("label_en", card["card_id"])
        for card in game_data["cards"]
    }

    cards_played = pd.DataFrame([
        {
            "card_id": card_id,
            "label_en": labels.get(card_id, card_id),
        }
        for card_id in round_cards
    ])

    session["round_start_cards"] = state["played_cards"].copy()

    state["round"] += 1
    session["offered"] = []
    session["playable"] = []

    return changes, scoring, details, cards_played

def show(session):
    """Display current state and board in a notebook."""
    try:
        from IPython.display import display

        print("GAME STATE")
        display(state_table(session))

        print("BOARD")
        display(board_table(session))

    except ImportError:
        print(state_table(session))
        print(board_table(session))


def play_manual(version, rule="free_choice", draw_n=7, seed=42):
    """
    Fully interactive manual inspection loop.

    You can also call start_manual(), draw_options(), play_choice(),
    and end_round() separately for more controlled step-by-step inspection.
    """
    session = start_manual(
        version,
        rule=rule,
        draw_n=draw_n,
        seed=seed,
    )

    try:
        from IPython.display import display
    except ImportError:
        display = print

    max_rounds = session["game_data"]["board"]["max_rounds"]

    while session["state"]["round"] <= max_rounds:
        print(f"\nROUND {session['state']['round']}")
        show(session)

        while True:
            options = draw_options(session)

            if options.empty:
                print("No playable cards available.")
                break

            print("PLAYABLE CARDS")
            display(options)

            try:
                value = input("Choose card number, 'state', or 'end': ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break

            if not value or value.lower() == "end":
                break

            if value.lower() == "state":
                show(session)
                continue

            try:
                choice = int(value)
            except ValueError:
                print("Invalid choice.")
                continue

            card, changes = play_choice(session, choice)
            print("PLAYED CARD")
            display(card)

            print("CHANGES")
            display(changes)


        print("ROUND SCORING")
        display(end_round(session))

        if session["state"]["budget"] < 0:
            print("Game ended: budget below zero.")
            break

    print("\nFINAL STATE")
    show(session)

    return session
