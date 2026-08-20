from pathlib import Path

import pandas as pd


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

    # Stable logical card ids
    if cards["card_id"].isna().any():
        raise ValueError("All cards must have a card_id")

    if cards["card_id"].duplicated().any():
        duplicates = cards.loc[
            cards["card_id"].duplicated(keep=False),
            "card_id",
        ].unique()

        raise ValueError(
            f"card_id must be unique before Count expansion: {duplicates.tolist()}"
        )

    # ------------------------------------------------------------------
    # Parse card constraints
    # ------------------------------------------------------------------
    cards["requires_cards"] = [set() for _ in range(len(cards))]
    cards["excludes_cards"] = [set() for _ in range(len(cards))]
    cards["min_thermal_protection"] = 0

    conditional = cards.loc[cards["Voraussetzung Spalte"].notna()]

    for idx, card in conditional.iterrows():
        column = card["Voraussetzung Spalte"]
        required = card["Voraussetzung Wert"]
        excluded = card["Voraussetzung Wert NICHT"]

        # Numeric requirement = minimum thermal protection.
        if pd.notna(required) and isinstance(required, (int, float)):
            cards.at[idx, "min_thermal_protection"] = int(required)

        # Otherwise resolve the configured column/value to stable card_id(s).
        elif pd.notna(required):
            cards.at[idx, "requires_cards"] = set(
                cards.loc[
                    cards[column] == required,
                    "card_id",
                ]
            )

        # Resolve exclusions in the same way.
        if pd.notna(excluded):
            cards.at[idx, "excludes_cards"] = set(
                cards.loc[
                    cards[column] == excluded,
                    "card_id",
                ]
            )

    # Expand physical copies after constraints have been resolved
    cards = cards.loc[
        cards.index.repeat(cards["Count"])
    ].reset_index(drop=True)

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
        return base_board.loc[
            base_board["Wert"] == name
        ].iloc[0]

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

        "heating_vp": heating_vp[
            ["Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]
        ].values.transpose().tolist(),

        "heating_budget": heating_budget[
            ["Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]
        ].values.transpose().tolist(),

        "hp_grid": hp_grid[
            ["Effizienz 1", "Effizienz 2", "Effizienz 3", "Effizienz 4", "Effizienz 5"]
        ].values.transpose().tolist(),

        "grid_budget": grid_impact["Budget"].tolist(),

        "grid_vp": grid_impact[
            ["SP Runde 1", "SP Runde 2", "SP Runde 3", "SP Runde 4"]
        ].values.transpose().tolist(),
    }

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
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
        "slot_to_index": {
            slot: i
            for i, slot in enumerate(single_slots)
        },
    }

def storage_index(state):
    if FLEXIBLE_STORAGE_CARD_ID in state["played_cards"]:
        return state["storage"]

    return min(
        state["electricity_generation"],
        state["storage"],
    )

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



def playable_cards(cards, state, max_demand, max_satisfaction):
    played = state["played_cards"]
    excluded = state["excluded_ids"]

    return [
        card for card in cards
        if (
            card["Slot/Stapel"] not in state["occupied_slots"]
            and card["card_id"] not in played
            and card["card_id"] not in excluded
            and card["Kosten"] <= state["budget"]

            and card["min_thermal_protection"] <= state["thermal_protection"]

            and (
                not card["requires_cards"]
                or card["requires_cards"] & played
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
    state["excluded_ids"].update(card["excludes_cards"])

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


def score_round(state, game_data, return_details=False):
    """Apply end-of-round effects and optionally return a scoring breakdown."""
    board = game_data["board"]

    # Embodied emissions
    embodied_vp = board["embodied_vp"][state["embodied_emissions"]]
    state["vp"] += embodied_vp

    # Heating system
    heating_vp = board["heating_vp"][
        state["heating_system"]
    ][state["thermal_protection"]]

    heating_budget = board["heating_budget"][
        state["heating_system"]
    ][state["thermal_protection"]]

    state["vp"] += heating_vp
    state["budget"] += heating_budget

    # Grid import from heating
    if state["heating_system"] < 4:
        heating_grid = 0
    else:
        heating_grid = board["hp_grid"][
            state["hp_efficiency"]
        ][state["thermal_protection"]]

    # Electricity demand and production
    demand_grid = board["demand_grid"][state["electricity_demand"]]
    production_grid = board["production_grid"][state["electricity_generation"]]

    # Storage
    storage_grid = board["storage_grid"][storage_index(state)]

    state["grid_import"] = (
        heating_grid
        + demand_grid
        + production_grid
        + storage_grid
    )

    # Satisfaction
    satisfaction_budget = board["satisfaction_budget"][state["satisfaction"]]
    state["budget"] += satisfaction_budget

    # Grid impact
    grid_index = clamp(state["grid_import"], 0, 35)

    grid_budget = board["grid_budget"][grid_index]
    grid_vp = board["grid_vp"][state["round"] - 1][grid_index]

    state["budget"] += grid_budget
    state["vp"] += grid_vp

    if return_details:
        return {
            "embodied_vp": embodied_vp,
            "heating_vp": heating_vp,
            "grid_vp": grid_vp,
            "heating_budget": heating_budget,
            "satisfaction_budget": satisfaction_budget,
            "grid_budget": grid_budget,
            "heating_grid": heating_grid,
            "demand_grid": demand_grid,
            "production_grid": production_grid,
            "storage_grid": storage_grid,
            "grid_import": state["grid_import"],
            "grid_index": grid_index,
        }