# Ausgegangen von:
# StartWS 0
# WärmeTechIndex 0 bis 4
# WärmepumpenIndex 4
# StartWPEffizienz -1 (nicht vorhanden)
# StartSP 0
import os
import random
import pandas as pd
import datetime as dt
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog

number_of_games = 10_000
mapping_heizsysteme = {"Gas" : 0, "BIO" : 1, "FW" : 2, "GG" : 3, "WP" : 4, "ABWWP" : 4}

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))

# Root-Fenster erstellen und verstecken
root = tk.Tk()
root.wm_attributes("-topmost", 1)
root.withdraw()

# Dialog öffnen
folder_path = filedialog.askdirectory(
    title="Arbeitsordner auswählen",
    initialdir=".",
    mustexist=True  # Verhindert die Auswahl nicht-existierender Pfade
)
root.destroy()

if folder_path:
    success = False
    files = os.listdir(folder_path)
    excel_files = [folder_path + "/" + file for file in files if file.endswith(".xlsx")]
    for file in excel_files:
        try:
            card_df = pd.read_excel(file, sheet_name="Massnahmenkarten Spielwerte")
            base_board_df = pd.read_excel(file, sheet_name="Board BaseValues")
            heiz_sp_df = pd.read_excel(file, sheet_name="Board Heiztabelle SP")
            heiz_budget_df = pd.read_excel(file, sheet_name="Board Heiztabelle Budget")
            wp_netzbezug_df = pd.read_excel(file, sheet_name="Board WP Netzbezug")
            netzbezug_final_df = pd.read_excel(file, sheet_name="Netzbezug Impact")
            success = True
        except Exception as e:
            print("Exception when parsing excel file in folder")
    if not success:
        try:
            card_df = pd.read_pickle(folder_path + "/cards.pkl")
            base_board_df = pd.read_pickle(folder_path + "/base_board.pkl")
            heiz_sp_df = pd.read_pickle(folder_path + "/heiz_sp.pkl")
            heiz_budget_df = pd.read_pickle(folder_path + "/heiz_budget.pkl")
            wp_netzbezug_df = pd.read_pickle(folder_path + "/wp_netzbezug.pkl")
            netzbezug_final_df = pd.read_pickle(folder_path + "/netzbezug_final.pkl")
            success = True
        except FileNotFoundError:
            pass
    if not success:
        folder_path = False
        print("No valid data found in folder. Continuing by creating new folder and starting download!")


if not folder_path:
    now = dt.datetime.now()
    folder_path = now.strftime("Data_%y_%m_%d-%Hh_%Mm_%Ss")
    os.mkdir(folder_path)

    #### Read files
    sheet_id = "1y_pGNGqghla6DfOW5DVMdima_WDhQ3QxvIgioDkcWRg"
    gid_cards = "0"

    url_cards = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_cards}"
    )

    card_df = pd.read_csv(url_cards)
    # base values -> Emi,Strombedarf,prod,speicher,Zuf
    gid_base_board = "376930118"
    url_base_board = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_base_board}"
    )
    base_board_df = pd.read_csv(url_base_board)
    # Heiztabelle in SP
    gid_heiz_sp = "836724185"
    url_heiz_sp = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_heiz_sp}"
    )
    heiz_sp_df = pd.read_csv(url_heiz_sp)
    # Heiztabelle in Budget
    gid_heiz_budget = "1054195681"
    url_heiz_budget = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_heiz_budget}"
    )
    heiz_budget_df = pd.read_csv(url_heiz_budget)
    # Heiztabelle in Netzbezug
    gid_wp_netzbezug = "1845164121"
    url_wp_netzbezug = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_wp_netzbezug}"
    )
    wp_netzbezug_df = pd.read_csv(url_wp_netzbezug)
    # Netzbezug zu SP, Budget
    gid_netzbezug_final = "727895942"
    url_netzbezug_final = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_netzbezug_final}"
    )
    netzbezug_final_df = pd.read_csv(url_netzbezug_final)


try:
    card_df
    base_board_df
    heiz_sp_df
    heiz_budget_df
    wp_netzbezug_df
    netzbezug_final_df
except NameError:
    print("Fatal Error! Dataframes are not defined! Check loading code!")
    exit(100)

### Clean up card_df
value_columns = ["BauEmissionen", "Strombedarf", "Stromproduktion", "Stromspeicher",
                 "Wärmeschutz", "Zufriedenheit", "Wärmepumpen-Effizienz", "SofortCO2", "SofortBudget"]
card_df[value_columns] = (
    card_df[value_columns]
    .fillna(0)
    .astype(int)
)
card_df['id'] = range(len(card_df))
# Voraussetzungen parsen
card_df['prerequisites'] = [[] for _ in range(len(card_df))]
card_df['exclusions'] = [[] for _ in range(len(card_df))]
bed_cards = card_df.loc[card_df['Voraussetzung Spalte'].notna()]
bed_cards_prerequisites = []
bed_cards_exclusion = []
for _, row in bed_cards.iterrows():
    id_list = card_df.loc[card_df[row['Voraussetzung Spalte']] == row['Voraussetzung Wert']]['id'].values.tolist()
    bed_cards_prerequisites.append(id_list)
    not_id_list = card_df.loc[card_df[row['Voraussetzung Spalte']] == row['Voraussetzung Wert NICHT']]['id'].values.tolist()
    bed_cards_exclusion.append(not_id_list)
card_df.loc[bed_cards.index, 'prerequisites'] = pd.Series(
    bed_cards_prerequisites,
    index=bed_cards.index,
)
card_df.loc[bed_cards.index, 'exclusions'] = pd.Series(
    bed_cards_exclusion,
    index=bed_cards.index,
)
card_df = card_df.loc[card_df.index.repeat(card_df['Count'])].reset_index(drop=True)


# Ensuring int types from float values
base_board_df[["Start (0-basiert)", "Values0", "Values1", "Values2", "Values3", "Values4",
               "Values5", "Values6", "Values7", "Values8", "Values9"]] = (
    base_board_df[["Start (0-basiert)", "Values0", "Values1", "Values2", "Values3", "Values4",
               "Values5", "Values6", "Values7", "Values8", "Values9"]].round(0).astype(int))
heiz_sp_df[["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]] = (
    heiz_sp_df[["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]].round(0).astype(int))
heiz_budget_df[["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]] = (
    heiz_budget_df[["WS", "Gas", "Biomasse", "Fernwärme", "Grünes Gas", "Wärmepumpe"]].round(0).astype(int))
wp_netzbezug_df[["WS", "Effizienz 1", "Effizienz 2", "Effizienz 3", "Effizienz 4", "Effizienz 5"]] = (
    wp_netzbezug_df[["WS", "Effizienz 1", "Effizienz 2", "Effizienz 3",
                     "Effizienz 4", "Effizienz 5"]].round(0).astype(int))
netzbezug_final_df[["Netzbezug", "Budget", "SP Runde 1", "SP Runde 2", "SP Runde 3", "SP Runde 4"]] = (
    netzbezug_final_df[["Netzbezug", "Budget",
                        "SP Runde 1", "SP Runde 2", "SP Runde 3", "SP Runde 4"]].round(0).astype(int))




#### Save Dataframes to pickles
card_df.to_pickle(folder_path + "/cards.pkl")
base_board_df.to_pickle(folder_path + "/base_board.pkl")
heiz_sp_df.to_pickle(folder_path + "/heiz_sp.pkl")
heiz_budget_df.to_pickle(folder_path + "/heiz_budget.pkl")
wp_netzbezug_df.to_pickle(folder_path + "/wp_netzbezug.pkl")
netzbezug_final_df.to_pickle(folder_path + "/netzbezug_final.pkl")


# MAGIC NUMBER: StartBudget (4)
bau_em_row = base_board_df.loc[base_board_df['Wert'] == "Bauliche Emissionen"]
bedarf_row = base_board_df.loc[base_board_df['Wert'] == "Strombedarf"]
prod_row = base_board_df.loc[base_board_df['Wert'] == "Stromproduktion"]
speicher_row = base_board_df.loc[base_board_df['Wert'] == "Stromspeicher"]
zuf_row = base_board_df.loc[base_board_df['Wert'] == "Zufriedenheit"]

board = {"budget" : 4,
         "start_sp" : 0, 
         "max_runden" : 4,
         "bau_em_start_index" : int(bau_em_row['Start (0-basiert)'].iloc[0]),
         "bau_emissionen" : bau_em_row[[f"Values{i}" for i in range(10)]].values.tolist()[0],
         "bedarf_start_index": int(bedarf_row['Start (0-basiert)'].iloc[0]),
         "bedarf_netzbezug": bedarf_row[[f"Values{i}" for i in range(10)]].values.tolist()[0],
         "strom_prod_start": int(prod_row['Start (0-basiert)'].iloc[0]),
         "strom_prod_netzbezug": prod_row[[f"Values{i}" for i in range(10)]].values.tolist()[0],
         "speicher_start": int(speicher_row['Start (0-basiert)'].iloc[0]),
         "speicher_prod_netzbezug": speicher_row[[f"Values{i}" for i in range(10)]].values.tolist()[0],
         "zuf_start_index" : int(zuf_row['Start (0-basiert)'].iloc[0]),
         "zufriedenheit_budget" : zuf_row[[f"Values{i}" for i in range(10)]].values.tolist()[0],
         "heiz_siegpunkte" : heiz_sp_df.values.transpose().tolist(), "heiz_kosten" : heiz_budget_df.values.transpose().tolist(),
         "wp_eff_netzbezug" : wp_netzbezug_df.values.transpose().tolist(),
         "netzbezug_budget" : netzbezug_final_df['Budget'].tolist(),
         "netzbezug_sp_runde" : netzbezug_final_df[['SP Runde 1', 'SP Runde 2', 'SP Runde 3', 'SP Runde 4']].values.transpose().tolist(),
         }

slots = card_df['Slot/Stapel'].unique()
single_slots = [slot for slot in slots if not slot.startswith("*")]

cards_by_slot = {
    slot: group.to_dict("records")
    for slot, group in card_df.groupby("Slot/Stapel", sort=False)
}

slot_to_index = {
    slot: index
    for index, slot in enumerate(single_slots)
}

game_master_list = []

for uid in range(number_of_games):
    game_state = {"budget": board["budget"], 
                  "bau_em": board["bau_em_start_index"],
                  "runde": 1,
                  "game_id": uid,
                  "wae_schu": 0, 
                  "wae_tech": 0, 
                  "wp_eff": -1, 
                  "bedarf": board["bedarf_start_index"],
                  "strom_prod": board["strom_prod_start"], 
                  "speicher": board["speicher_start"],
                  "zufriedenheit": board["zuf_start_index"], 
                  "sp": board["start_sp"],
                  "slots" : [-1] * len(single_slots), 
                  "occupied" : set(),
                  "played_cards": set(),
                  "excluded_ids": set(),
                  "played_cards_log": [],
                  "round_end_reason": None,
                  }
    # decisions will be list of strings with game moves
    # slots will be holding card_ids of cards in slots that are single use
    # occupied holds list of (single use) slot names which are in use

    ''' NOT CURRENTLY IMPLEMENTED
    stats = {"min_budget": game_state["budget"], "max_budget": game_state["budget"],
             "min_sp": game_state["sp"], "max_sp": game_state["sp"],
             "min_netz": len(board["netzbezug_budget"]), "max_netz": 0, "min_zuf": game_state["zufriedenheit"],
             "max_zuf": game_state["zufriedenheit"]}
    '''
    while game_state["runde"] <= board["max_runden"]:
        while True:
            ######### SPIELZUG #########
            # Verfügbare Kartenstapel ermitteln
            available_slots = [
                slot for slot in slots
                if slot not in game_state["occupied"] # nur aus noch nicht belegten slots
                and any(
                    card["id"] not in game_state["played_cards"] # falls in dem stapel noch karten sind, die noch nicht gespielt wurden
                    for card in cards_by_slot[slot]
                )
            ]
            if not available_slots:
                game_state["round_end_reason"] = "no_available_slots"
                break
            
            # Kartenstapel wählen
            chosen_slot = random.choice(available_slots)

            # Noch nicht gespielte Karten dieses Stapels
            unplayed_cards = [
                card
                for card in cards_by_slot[chosen_slot]
                if card["id"] not in game_state["played_cards"]
            ]

            # Drei Karten ziehen, oder alle verbleibenden, falls weniger als drei vorhanden sind
            drawn_cards = random.sample(
                unplayed_cards,
                k=min(3, len(unplayed_cards))
            )

            # Nur spielbare Karten aus den drei gezogenen Karten (bezahlbar und Voraussetzungen passen)
            playable_cards = [
                card
                for card in drawn_cards
                if card["Kosten"] <= game_state["budget"] and card["id"] not in game_state["excluded_ids"] and
                   (not card["prerequisites"] or set(card["prerequisites"]) & game_state["played_cards"])
            ]

            # Keine der gezogenen Karten ist spielbar: Schlusswertung
            if not playable_cards:
                game_state["round_end_reason"] = "no_playable_drawn_cards"
                break

            # Eine leistbare Karte auswählen und spielen
            chosen_card = random.choice(playable_cards)

            # Werte anpassen, zurück zum Anfang
            game_state["played_cards"].add(chosen_card["id"])
            game_state["excluded_ids"].update(chosen_card["exclusions"])
            game_state["played_cards_log"].append({
                "runde": game_state["runde"],
                "card_id": chosen_card["id"],
            })

            if chosen_card['Slot/Stapel'] in single_slots:
                game_state["occupied"].add(chosen_slot)
                game_state["slots"][slot_to_index[chosen_slot]] = chosen_card["id"]


            game_state["budget"] -= chosen_card['Kosten']
            game_state["bau_em"] += chosen_card['BauEmissionen']
            game_state["bedarf"] += chosen_card['Strombedarf']
            game_state["strom_prod"] += chosen_card['Stromproduktion']
            game_state["speicher"] += chosen_card['Stromspeicher']
            game_state["wae_schu"] += chosen_card['Wärmeschutz']
            game_state["wp_eff"] += chosen_card['Wärmepumpen-Effizienz']
            game_state["zufriedenheit"] += chosen_card['Zufriedenheit']
            game_state["sp"] += chosen_card['SofortCO2']
            game_state["budget"] += chosen_card['SofortBudget']
            if not pd.isna(chosen_card['Heizsystem']):
                game_state["wae_tech"] = mapping_heizsysteme[chosen_card['Heizsystem']]


        ######### WERTUNG #########

        # Bauliche Emissionen:
        game_state["sp"] += board["bau_emissionen"][clamp(game_state["bau_em"], 0, 9)]
        # Heizenergie
        game_state["sp"] += board["heiz_siegpunkte"][game_state["wae_tech"]][clamp(game_state["wae_schu"], 0, 9)]
        game_state["budget"] += board["heiz_kosten"][game_state["wae_tech"]][clamp(game_state["wae_schu"], 0, 9)]
        game_state["netzbezug"] = 0 if game_state["wae_tech"] < 4 else board["wp_eff_netzbezug"][clamp(game_state["wp_eff"], 0, 4)][clamp(game_state["wae_schu"], 0, 9)]
        # Strombedarf
        game_state["netzbezug"] += board["bedarf_netzbezug"][clamp(game_state["bedarf"], 0, 9)]
        # Stromproduktion
        game_state["netzbezug"] += board["strom_prod_netzbezug"][clamp(game_state["strom_prod"], 0, 9)]
        # Stromspeicher
        game_state["netzbezug"] += board["speicher_prod_netzbezug"][clamp(min(game_state["strom_prod"], game_state["speicher"]), 0, 9)]
        # Zufriedenheit
        game_state["budget"] += board["zufriedenheit_budget"][clamp(game_state["zufriedenheit"], 0, 9)]
        # Netzbezug auswerten
        game_state["budget"] += board["netzbezug_budget"][clamp(game_state["netzbezug"], 0, 20)]
        game_state["sp"] += board["netzbezug_sp_runde"][game_state["runde"] - 1][clamp(game_state["netzbezug"], 0, 20)]

        snapshot = game_state.copy()
        snapshot["slots"] = game_state["slots"].copy()
        snapshot["occupied"] = list(game_state["occupied"])
        snapshot["played_cards"] = list(game_state["played_cards"])
        snapshot["played_cards_log"] = game_state["played_cards_log"].copy()

        game_master_list.append(snapshot)
        game_state["round_end_reason"] = None
        game_state["runde"] += 1
    if uid % 1000 == 0:
        print(f"Simulated games: {uid:_} / {number_of_games:_}")

game_history_df = pd.DataFrame(game_master_list)
game_history_df.to_parquet(folder_path + "/History.parquet")
