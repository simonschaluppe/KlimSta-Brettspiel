from pathlib import Path

import pandas as pd
from pandas.api.types import is_integer


HEATING_SYSTEMS = {
    "Gas": 0,
    "BIO": 1,
    "FW": 2,
    "GG": 3,
    "WP": 4,
    "ABWWP": 4,
}

# Stable semantic card id from game_data.xlsx.
FLEXIBLE_STORAGE_CARD_ID = "flexible_battery_charging"


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def load_game_data(version):
    """
    Load and prepare one game version.

    Example
    -------
    game_data = load_game_data("Versionen/paper_draft_v1")
    """
    version = Path(version)
    excel_path = version / "game_data.xlsx" if version.is_dir() else version

    cards = pd.read_excel(excel_path, sheet_name="Massnahmenkarten Spielwerte")
    base_board = pd.read_excel(excel_path, sheet_name="Board BaseValues")
    heating_vp = pd.read_excel(excel_path, sheet_name="Board Heiztabelle SP")
    heating_budget = pd.read_excel(excel_path, sheet_name="Board Heiztabelle Budget")
    hp_grid = pd.read_excel(excel_path, sheet_name="Board WP Netzbezug")
    grid_impact = pd.read_excel(excel_path, sheet_name="Netzbezug Impact")

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------
    value_columns = [
        "Count",
        "Kosten",
        "BauEmissionen",
        "Strombedarf",
        "Stromproduktion",
        "Stromspeicher",
        "Wärmeschutz",
        "Zufriedenheit",
        "Wärmepumpen-Effizienz",
        "SofortCO2",
        "SofortBudget",
    ]

    cards[value_columns] = cards[value_columns].fillna(0).astype(int)

    # card_id is the stable logical identifier used throughout the model.
    # Count is expanded afterwards, so several physical copies may share a card_id.
    if cards["card_id"].isna().any():
        raise ValueError("All cards must have a card_id")

    if cards["card_id"].duplicated().any():
        duplicates = cards.loc[cards["card_id"].duplicated(), "card_id"].tolist()
        raise ValueError(f"card_id must be unique before Count expansion: {duplicates}")

    cards["prerequisites"] = [[] for _ in range(len(cards))]
    cards["exclusions"] = [[] for _ in range(len(cards))]
    cards["ws_prerequisites"] = 0

    conditional = cards.loc[cards["Voraussetzung Spalte"].notna()]

    for idx, card in conditional.iterrows():
        column = card["Voraussetzung Spalte"]
        required = card["Voraussetzung Wert"]
        excluded = card["Voraussetzung Wert NICHT"]

        # Existing convention: integer prerequisite means a minimum
        # thermal-protection level rather than another card.
        if is_integer(required):
            cards.at[idx, "ws_prerequisites"] = int(required)
        else:
            cards.at[idx, "prerequisites"] = cards.loc[
                cards[column] == required, "card_id"
            ].tolist()

        cards.at[idx, "exclusions"] = cards.loc[
            cards[column] == excluded, "card_id"
        ].tolist()

    # Expand physical card copies.
    cards = cards.loc[cards.index.repeat(cards["Count"])].reset_index(drop=True)

    # Convert prerequisite/exclusion lists to sets for faster checks.
    cards["prerequisites"] = cards["prerequisites"].apply(set)
    cards["exclusions"] = cards["exclusions"].apply(set)

    # ------------------------------------------------------------------
    # Board lookup tables
    # ------------------------------------------------------------------
    value_names = [f"Values{i}" for i in range(10)]

    base_board = base_board[
        ["Wert", "Start (0-basiert)", *value_names]
    ]

    for column in ["Start (0-basiert)", *value_names]:
        base_board[column] = base_board[column].round().astype("Int64")

    heating_vp = heating_vp[
        ["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]
    ].round().astype(int)

    heating_budget = heating_budget[
        ["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]
    ].round().astype(int)

    hp_grid = hp_grid[
        ["WS", "Effizienz 1", "Effizienz 2", "Effizienz 3", "Effizienz 4", "Effizienz 5"]
    ].round().astype(int)

    grid_impact = grid_impact[
        ["Netzbezug", "Budget", "SP Runde 1", "SP Runde 2", "SP Runde 3", "SP Runde 4"]
    ].round().astype(int)

    def row(name):
        return base_board.loc[base_board["Wert"] == name].iloc[0]

    embodied = row("Bauliche Emissionen")
    demand = row("Strombedarf")
    production = row("Stromproduktion")
    storage = row("Stromspeicher")
    satisfaction = row("Zufriedenheit")

    board = {
        "start_budget": 4,
        "start_vp": 0,
        "max_rounds": 4,

        "embodied_start": int(embodied["Start (0-basiert)"]),
        "embodied_vp": embodied[value_names].astype(int).tolist(),

        "demand_start": int(demand["Start (0-basiert)"]),
        "demand_grid": demand[value_names].astype(int).tolist(),

        "production_start": int(production["Start (0-basiert)"]),
        "production_grid": production[value_names].astype(int).tolist(),

        "storage_start": int(storage["Start (0-basiert)"]),
        "storage_grid": storage[value_names].astype(int).tolist(),

        "satisfaction_start": int(satisfaction["Start (0-basiert)"]),
        "satisfaction_budget": satisfaction[value_names].astype(int).tolist(),

        "heating_vp": heating_vp.values.transpose().tolist(),
        "heating_budget": heating_budget.values.transpose().tolist(),
        "hp_grid": hp_grid.values.transpose().tolist(),

        "grid_budget": grid_impact["Budget"].tolist(),
        "grid_vp": grid_impact[
            ["SP Runde 1", "SP Runde 2", "SP Runde 3", "SP Runde 4"]
        ].values.transpose().tolist(),
    }

    single_slots = [
        slot
        for slot in cards["Slot/Stapel"].dropna().unique()
        if not str(slot).startswith("*")
    ]

    cards = cards.to_dict("records")

    return {
        "cards": cards,
        "board": board,
        "single_slots": single_slots,
        "slot_to_index": {slot: i for i, slot in enumerate(single_slots)},
    }

def new_game(game_data, game_id=None):
    """Create the initial state of one game."""
    board = game_data["board"]

    return {
        "game_id": game_id,
        "round": 1,
        "budget": board["start_budget"],

        # Victory points / CO2 score. Lower is better.
        "vp": board["start_vp"],

        "embodied_emissions": board["embodied_start"],
        "thermal_protection": 0,
        "heating_system": 0,
        "hp_efficiency": -1,

        "electricity_demand": board["demand_start"],
        "electricity_generation": board["production_start"],
        "storage": board["storage_start"],
        "satisfaction": board["satisfaction_start"],
        "grid_import": 0,

        "slots": [None] * len(game_data["single_slots"]),
        "occupied_slots": set(),
        "played_cards": set(),
        "excluded_ids": set(),
    }



def playable_cards(cards, state, max_demand, max_satisfaction ):
    return [
        card for card in cards
        if (
            card["Slot/Stapel"] not in state["occupied_slots"]
            and card["card_id"] not in state["played_cards"]
            and card["card_id"] not in state["excluded_ids"]
            and card["Kosten"] <= state["budget"]
            and card["ws_prerequisites"] <= state["thermal_protection"]
            and (
                not card["prerequisites"]
                or card["prerequisites"] & state["played_cards"]
            )
            and (
                card["Strombedarf"] + state["electricity_demand"]
                <= max_demand
            )
            and (
                card["Zufriedenheit"] + state["satisfaction"]
                <= max_satisfaction
            )
        )
    ]


def play_card(card, state, game_data):
    """Apply one card to the game state."""
    state["played_cards"].add(card["card_id"])
    state["excluded_ids"].update(card["exclusions"])

    slot = card["Slot/Stapel"]
    if slot in game_data["single_slots"]:
        state["occupied_slots"].add(slot)
        state["slots"][game_data["slot_to_index"][slot]] = card["card_id"]

    state["budget"] -= card["Kosten"]

    state["embodied_emissions"] = clamp(
        state["embodied_emissions"] + card["BauEmissionen"], 0, 9
    )
    state["electricity_demand"] = clamp(
        state["electricity_demand"] + card["Strombedarf"], 0, 9
    )
    state["electricity_generation"] = clamp(
        state["electricity_generation"] + card["Stromproduktion"], 0, 9
    )
    state["storage"] = clamp(
        state["storage"] + card["Stromspeicher"], 0, 9
    )
    state["thermal_protection"] = clamp(
        state["thermal_protection"] + card["Wärmeschutz"], 0, 9
    )
    state["hp_efficiency"] = clamp(
        state["hp_efficiency"] + card["Wärmepumpen-Effizienz"], -1, 4
    )
    state["satisfaction"] = clamp(
        state["satisfaction"] + card["Zufriedenheit"], 0, 9
    )

    state["vp"] += card["SofortCO2"]
    state["budget"] += card["SofortBudget"]

    if not pd.isna(card["Heizsystem"]):
        state["heating_system"] = HEATING_SYSTEMS[card["Heizsystem"]]


def score_round(state, game_data):
    """Apply the existing end-of-round effects."""
    board = game_data["board"]

    # Embodied emissions
    state["vp"] += board["embodied_vp"][state["embodied_emissions"]]

    # Heating system
    state["vp"] += board["heating_vp"][
        state["heating_system"]
    ][state["thermal_protection"]]

    state["budget"] += board["heating_budget"][
        state["heating_system"]
    ][state["thermal_protection"]]

    # Grid import from heating
    if state["heating_system"] < 4:
        state["grid_import"] = 0
    else:
        state["grid_import"] = board["hp_grid"][
            state["hp_efficiency"]
        ][state["thermal_protection"]]

    # Electricity demand and production
    state["grid_import"] += board["demand_grid"][state["electricity_demand"]]
    state["grid_import"] += board["production_grid"][state["electricity_generation"]]

    # Storage
    if FLEXIBLE_STORAGE_CARD_ID in state["played_cards"]:
        storage_index = state["storage"]
    else:
        storage_index = min(
            state["electricity_generation"],
            state["storage"],
        )

    state["grid_import"] += board["storage_grid"][storage_index]

    # Satisfaction
    state["budget"] += board["satisfaction_budget"][state["satisfaction"]]

    # Grid impact
    grid_index = clamp(state["grid_import"], 0, 35)

    state["budget"] += board["grid_budget"][grid_index]
    state["vp"] += board["grid_vp"][state["round"] - 1][grid_index]
