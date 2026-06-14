# Ausgegangen von:
# StartWS 0
# WärmeTechIndex 0 bis 4
# WärmepumpenIndex 4
# StartWPEffizienz -1 (nicht vorhanden)
# StartSP 0
import random
import pandas as pd

number_of_games = 1_000_000
mapping_heizsysteme = {"Gas" : 0, "BIO" : 1, "FW" : 2, "GG" : 3, "WP" : 4, "ABWWP" : 4}
download = False

if download:
    sheet_id = "1y_pGNGqghla6DfOW5DVMdima_WDhQ3QxvIgioDkcWRg"
    gid_cards = "0"
    gid_board = "376930118"

    url_cards = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_cards}"
    )
    url_board = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid_board}"
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

    board_df = pd.read_csv(url_board)
    # Save
    card_df.to_pickle("cards.pkl")
    board_df.to_pickle("board.pkl")
else:
    card_df = pd.read_pickle("cards.pkl")
    board_df = pd.read_pickle("board.pkl")

# Aus dem Excel!
board = {"budget" : 4, "bau_em_start_index" : 5, "bau_emissionen" : [-5,-4,-3,-2,-1,0,1,2,3,4,5],
         "WS_max" : 9, "tech_count" : 5, "wp_eff_count" : 5, "heiz_siegpunkte" : [[]], "heiz_kosten" : [[]],
         "wp_eff_netzbezug" : [[]], "bedarf_start_index" : 1, "bedarf_netzbezug" : [9,8,7,6,5,4,3,2,1,0],
         "strom_prod_netzbezug" : [0,0,-1,-1,-2,-2,-3,-3,-4,-4], "speicher_prod_netzbezug" : [0,-1,-1],
         "zuf_start_index" : 5, "zufriedenheit_budget" : [2,3,3,4,4,5,5,6,6,7], "netzbezug_budget" : [0,"bis",20],
         "netzbezug_sp_runde" : [[]], "start_sp" : 0, "max_runden" : 4}

slots = card_df['Slot/Stapel'].unique()
single_slots = [slot for slot in slots if not slot.startswith("*")]


for uid in range(number_of_games):
    game_state = {"budget": board["budget"], "bau_em": board["bau_em_start_index"], "runde": 1, "game_id": uid,
                  "wae_schu": 0, "wae_tech": 0, "wp_eff": -1, "bedarf": board["bedarf_start_index"],
                  "strom_prod": 0, "speicher": 0, "zufriedenheit": board["zuf_start_index"], "sp": board["start_sp"],
                  "decisions" : [], "slots" : [-1] * len(single_slots), "occupied" : []}
    # decisions will be list of strings with game moves
    # slots will be holding card_ids of cards in slots that are single use
    # occupied holds list of (single use) slot names which are in use

    stats = {"min_budget": game_state["budget"], "max_budget": game_state["budget"],
             "min_sp": game_state["sp"], "max_sp": game_state["sp"],
             "min_netz": len(board["netzbezug_budget"]), "max_netz": 0, "min_zuf": game_state["zufriedenheit"],
             "max_zuf": game_state["zufriedenheit"]}
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
            game_state["occupied"].append(chosen_card['Slot/Stapel'])
            if chosen_card['Slot/Stapel'] in single_slots:
                game_state["slots"][single_slots.index(chosen_card['Slot/Stapel'])] = chosen_card['id']


            game_state["budget"] -= chosen_card['Kosten']
            game_state["bau_em"] += chosen_card['BauEmissionen']
            game_state["bedarf"] += chosen_card['Strombedarf']
            game_state["strom_prod"] += chosen_card['Stromproduktion']
            game_state["speicher"] += chosen_card['Stromspeicher']
            game_state["wae_schu"] += chosen_card['Wärmeschutz']
            game_state["wp_eff"] += chosen_card['Wärmepumpen-Effizienz']
            game_state["zufriedenheit"] += chosen_card['Zufriedenheit']
            if len(chosen_card['Heizsystem']) > 0:
                game_state["wae_tech"] = mapping_heizsysteme[chosen_card['Heizsystem']]


        ######### WERTUNG #########

        # Bauliche Emissionen:
        game_state["sp"] += board["bau_emissionen"][game_state["bau_em"]]
        # Heizenergie
        game_state["sp"] += board["heiz_siegpunkte"][game_state["wae_schu"]][game_state["wae_tech"]]
        game_state["budget"] += board["heiz_kosten"][game_state["wae_schu"]][game_state["wae_tech"]]
        game_state["netzbezug"] = 0 if game_state["wae_tech"] < 4 else board["wp_eff_netzbezug"][game_state["wae_schu"]][game_state["wp_eff"]]
        # Strombedarf
        game_state["netzbezug"] += board["bedarf_netzbezug"][game_state["bedarf"]]
        # Stromproduktion
        game_state["netzbezug"] += board["strom_prod_netzbezug"][game_state["strom_prod"]]
        # Stromspeicher
        game_state["netzbezug"] += board["speicher_prod_netzbezug"][min(game_state["strom_prod"], game_state["speicher"])]
        # Zufriedenheit
        game_state["budget"] += board["zufriedenheit_budget"][game_state["zufriedenheit"]]
        # Netzbezug auswerten
        game_state["budget"] += board["netzbezug_budget"][game_state["netzbezug"]]
        game_state["sp"] += board["netzbezug_sp_runde"][game_state["netzbezug"]][game_state["runde"]]

        game_state["runde"] += 1