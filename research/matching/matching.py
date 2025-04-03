
import torch
import os
import pandas as pd
import numpy as np
from dateutil import parser
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# On oublie ces lignes là, il faut juste fournir un csv en entrée à la place et le convertir en dataframe


torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)] 
r = """

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
"""

def get_best_match_with_transformer(query, candidates, model):
    """
    Retourne l'élément de la liste `candidates` le plus similaire à `query`
    """
    embeddings = model.encode([query] + candidates)
    similarities = cosine_similarity([embeddings[0]], embeddings[1:])[0]
    best_idx = similarities.argmax()
    return candidates[best_idx], similarities[best_idx]

def data_matching(source_csv, ocr_df):

    #Pre-traitement des données OCR d'entrée
    # Pareil, changer le chemin en entrée selon ce que fournit l'OCR
    
    ocr_output = ocr_df
    whole_df = pd.read_csv(source_csv)
    
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
    
    #ocr_output.to_csv("export_fixed.csv", sep=",", index=False)
    
    
    
    # Par ordre de hiérarchie: prix > date > vendeur > currency, on vérifie dans cette ordre
    # A chaque fois, on retient les lignes qui correspondent ou qui matchent le mieux au vendeur, et on attribue la facture correspondante
    # Après attribution de la facture, on marque la ligne comme checked, pour ne pas la reparcourir dans les itérations successives
    
    # Initialisation de l'instance qui fait le matching
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Les colonnes rajoutées pour assigner l'image et pour éliminer les lignes assignées des futures itérations
    whole_df['checked'] = False
    whole_df['assigned_picture'] = ''
    
    # Start matching
    for index, row in ocr_output.iterrows():
        if not isinstance(row['total_price'], (int, float)):
            continue
    
        # Création d'un dataframe qui match les infos entre l'output et celui du relevé bancaire 
        # Pour chaque attribut, s'il n'y a qu'un match trouvé, on l'assigne immédiatement et on passe à la prochaine itération
        # On ne check que les lignes qui n'ont pas déjà une image assignée
        filtered_df = whole_df[(whole_df['assigned_picture'] == '') & 
                               (whole_df['amount'] == row['total_price'])]

        # S'il n'y a qu'un match dès le check du prix, pas besoin de continuer, on établit d'emblée le matching
        # Bonus: ne pas associer immédiatement l'image selon le prix, même s'il n'y a qu'un seul record
        if filtered_df.shape[0] == 1:
            match_index = filtered_df.index[0]
            whole_df.loc[match_index, 'checked'] = True
            whole_df.loc[match_index, 'assigned_picture'] = row['filename']
            continue
    
        # On check la date, de manière rigide
        filtered_df = filtered_df[filtered_df['date'] == row['date_of_purchase']]
    
        if filtered_df.shape[0] == 1:
            match_index = filtered_df.index[0]
            whole_df.loc[match_index, 'checked'] = True
            whole_df.loc[match_index, 'assigned_picture'] = row['filename']
            continue
    
        # On check le nom du vendeur, en retenant le plus similaire
        if not filtered_df.empty:
            # Matching du nom du vendeur, on retient le meilleur et on l'assigne à la ligne dans le dataframe du relevé bancaire selon l'index
            candidate_vendors = filtered_df['vendor'].astype(str).tolist()
            best_vendor, score = get_best_match_with_transformer(row['vendor'], candidate_vendors, model=model)
            best_index = filtered_df[filtered_df['vendor'] == best_vendor].index[0]
            whole_df.loc[best_index, 'checked'] = True
            whole_df.loc[best_index, 'assigned_picture'] = row['filename']
    
    # On retient les images qui n'ont pas trouvé de match pour les montrer à l'utilisateur
    picture_list = ocr_output['filename'].tolist()
    missing_pictures = list(set(picture_list) - set(whole_df['assigned_picture'].dropna()))
    
    # Ici, on renvoie le dataframe
    return whole_df, missing_pictures