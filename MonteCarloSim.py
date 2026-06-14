# Ausgegangen von:
# StartWS 0
# WärmeTechIndex 0 bis 4
# WärmepumpenIndex 4
# StartWPEffizienz -1 (nicht vorhanden)
# StartSP 0
import random
import pandas as pd

number_of_games = 10_000
mapping_heizsysteme = {"Gas" : 0, "BIO" : 1, "FW" : 2, "GG" : 3, "WP" : 4, "ABWWP" : 4}
download = False

def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))

if download:
    sheet_id = "1y_pGNGqghla6DfOW5DVMdima_WDhQ3QxvIgioDkcWRg"
    gid_cards = "0"

    url_cards = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_cards}"
    )
    value_columns = ["BauEmissionen", "Strombedarf", "Stromproduktion", "Stromspeicher",
                     "Wärmeschutz", "Zufriedenheit", "Wärmepumpen-Effizienz"]

    card_df = pd.read_csv(url_cards)

    card_df[value_columns] = (
        card_df[value_columns]
        .fillna(0)
        .astype(int)
    )
    card_df['id'] = range(len(card_df))


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


    # Save
    card_df.to_pickle("cards.pkl")
    base_board_df.to_pickle("base_board.pkl")
    heiz_sp_df.to_pickle("heiz_sp.pkl")
    heiz_budget_df.to_pickle("heiz_budget.pkl")
    wp_netzbezug_df.to_pickle("wp_netzbezug.pkl")
    netzbezug_final_df.to_pickle("netzbezug_final.pkl")
else:
    card_df = pd.read_pickle("cards.pkl")
    base_board_df = pd.read_pickle("base_board.pkl")
    heiz_sp_df = pd.read_pickle("heiz_sp.pkl")
    heiz_budget_df = pd.read_pickle("heiz_budget.pkl")
    wp_netzbezug_df = pd.read_pickle("wp_netzbezug.pkl")
    netzbezug_final_df = pd.read_pickle("netzbezug_final.pkl")


# MAGIC NUMBER: StartBudget (4)
bau_em_row = base_board_df.loc[base_board_df['Wert'] == "Bauliche Emissionen"]
bedarf_row = base_board_df.loc[base_board_df['Wert'] == "Strombedarf"]
prod_row = base_board_df.loc[base_board_df['Wert'] == "Stromproduktion"]
speicher_row = base_board_df.loc[base_board_df['Wert'] == "Stromspeicher"]
zuf_row = base_board_df.loc[base_board_df['Wert'] == "Zufriedenheit"]

board = {"budget" : 4,
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
         "start_sp" : 0, "max_runden" : 4}


slots = card_df['Slot/Stapel'].unique()
single_slots = [slot for slot in slots if not slot.startswith("*")]

game_master_list = []

for uid in range(number_of_games):
    game_state = {"budget": board["budget"], "bau_em": board["bau_em_start_index"], "runde": 1, "game_id": uid,
                  "wae_schu": 0, "wae_tech": 0, "wp_eff": -1, "bedarf": board["bedarf_start_index"],
                  "strom_prod": board["strom_prod_start"], "speicher": board["speicher_start"],
                  "zufriedenheit": board["zuf_start_index"], "sp": board["start_sp"],
                  "decisions" : [], "slots" : [-1] * len(single_slots), "occupied" : []}
    # decisions will be list of strings with game moves
    # slots will be holding card_ids of cards in slots that are single use
    # occupied holds list of (single use) slot names which are in use

    ''' NOT CURRENTLY IMPLEMENTED
    stats = {"min_budget": game_state["budget"], "max_budget": game_state["budget"],
             "min_sp": game_state["sp"], "max_sp": game_state["sp"],
             "min_netz": len(board["netzbezug_budget"]), "max_netz": 0, "min_zuf": game_state["zufriedenheit"],
             "max_zuf": game_state["zufriedenheit"]}
    '''
    while game_state["runde"] < board["max_runden"]:
        while True:
            ######### SPIELZUG #########
            # zufälligen Stapel auswählen -> Was ist mit schon gefüllten? Noch nichts
            chosen_slot = random.choice([slot for slot in slots if slot not in game_state["occupied"]])
            # zufällige Karte aus dem Stapel auswählen
            chosen_card = card_df.loc[card_df['Slot/Stapel'] == chosen_slot].sample().iloc[0]

            # Prüfen ob Karte bezahlbar ist
            if chosen_card['Kosten'] > game_state["budget"]:
                # wenn nein -> Schlusswertung
                game_state["decisions"].append("Gepasst")
                break
            # Wenn ja einbauen, Werte anpassen, zurück zum Anfang
            game_state["decisions"].append(f"Installiert {chosen_card['Name']}")
            if chosen_card['Slot/Stapel'] in single_slots:
                game_state["occupied"].append(chosen_card['Slot/Stapel'])
                game_state["slots"][single_slots.index(chosen_card['Slot/Stapel'])] = chosen_card['id']


            game_state["budget"] -= chosen_card['Kosten']
            game_state["bau_em"] += chosen_card['BauEmissionen']
            game_state["bedarf"] += chosen_card['Strombedarf']
            game_state["strom_prod"] += chosen_card['Stromproduktion']
            game_state["speicher"] += chosen_card['Stromspeicher']
            game_state["wae_schu"] += chosen_card['Wärmeschutz']
            game_state["wp_eff"] += chosen_card['Wärmepumpen-Effizienz']
            game_state["zufriedenheit"] += chosen_card['Zufriedenheit']
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
        game_state["sp"] += board["netzbezug_sp_runde"][game_state["runde"]][clamp(game_state["netzbezug"], 0, 20)]

        game_master_list.append(game_state)

        game_state["runde"] += 1
    if uid % 1000 == 0:
        print(uid)

game_history_df = pd.DataFrame(game_master_list)
game_history_df.to_parquet("History.parquet")
