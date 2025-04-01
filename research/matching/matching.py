from stringmatch import Match
import pandas as pd
import os
import numpy as np
from dateutil import parser

path_to_csv_folder = "bank_statements\\"

whole_df = pd.DataFrame()
df_list = []

for filename in os.listdir(path_to_csv_folder):
    if filename.endswith(".csv"):
        #print(filename)
        current_df = pd.read_csv(path_to_csv_folder + filename)
        df_list.append(current_df)

whole_df = pd.concat(df_list)

whole_df.reset_index(drop=True, inplace=True)



#Pre-traitement des données d'entrée

path_to_export = r"export.csv"

ocr_output = pd.read_csv(path_to_export)

def parse_date_safely(date_str):
    # Ne rien faire si la valeur est vide ou autre chose qu'une string
    if pd.isna(date_str) or not isinstance(date_str, str):
        return date_str
    try:
        # parsing de la date
        dt = parser.parse(date_str, fuzzy=True, dayfirst=False)
        return dt.strftime('%Y-%m-%d')
    # Retourne la valeur inchangée si échec
    except Exception:
        return date_str

# Application sur la colonne
ocr_output['date_of_purchase'] = ocr_output['date_of_purchase'].apply(parse_date_safely)

ocr_output['vendor'] = ocr_output['name_of_store'].astype(str) + ' ' + (ocr_output['address'].astype(str))

ocr_output['filename'] = ocr_output['filename'].str.replace(r'^.*\\', '', regex=True)

ocr_output.to_csv("export_fixed.csv", sep=",", index=False)



# Par ordre de hiérarchie: prix > date > vendeur > currency, on vérifie dans cette ordre
# A chaque fois, on retient les lignes qui correspondent ou qui matchent le mieux au vendeur, et on attribue la facture correspondante
# Après attribution de la facture, on marque la ligne comme checked, pour ne pas la reparcourir dans les itérations successives

# Initialisation de l'instance qui fait le matching
match = Match()

# Les colonnes rajoutées pour assigner l'image et pour éliminer les lignes assignées des futures itérations
whole_df['checked'] = False
whole_df['assigned_picture'] = np.nan

unassigned_pictures_list = []

for index, _ in ocr_output.iterrows():
    # Récupération des informations du dataframe output de l'OCR
    vendor_entry = ocr_output.loc[index, 'vendor']
    amount_entry = ocr_output.loc[index, 'total_price']
    date_entry = ocr_output.loc[index, 'date_of_purchase']
    picture_entry = ocr_output.loc[index, 'filename']

    # Création d'un dataframe qui match les infos entre l'output et celui du relevé bancaire
    sorted_df = whole_df[whole_df['checked'] == False]
    sorted_df = whole_df[whole_df['amount'] == amount_entry]
    sorted_df = whole_df[whole_df['date'] == (date_entry)]
    
    if not sorted_df.empty:
        # Matching du nom du vendeur, on retient le meilleur et on l'assigne à la ligne dans le dataframe du relevé bancaire selon l'index
        vendor_list = sorted_df['vendor'].values.tolist()
        if (isinstance(vendor_list[0], str)):
            best_matching = match.get_best_matches(str(vendor_entry), vendor_list, limit=1)
            if len(best_matching) > 0:
                best_matching_index = whole_df[whole_df['vendor'] == best_matching[0]].index[0]
        else:
            best_matching_index = whole_df[whole_df['date'] == (date_entry)].index[0]
            
        whole_df.loc[best_matching_index, 'checked'] = True
        whole_df.loc[best_matching_index, 'assigned_picture'] = picture_entry

    else:
        # Si on ne trouve pas de ligne correspondante, on garde l'image ici (un index tant que les données source de l'ocr ne sont pas dispo)
        unassigned_pictures_list.append(picture_entry)


whole_df.to_csv("current_output.csv")