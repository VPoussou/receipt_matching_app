# Matching de tickets de caisse aux relevés bancaires

***Cette application streamlit permets à un utilisateur d'uploader un lot de tickets de caisse au format .jpg et un relevé bancaire au format ;csv et d'obtenir un tableur de correspondance visualisable dans l'application et téléchargeable au format .xls***

## Installation
Cloner le repo. Créer un environnement virtuel, l'activer, installer les dépendances spécifiées dans le fichier *requirements.txt*. Créez un fichier .env à la racine du repo avec dedans "*MISTRAL_API_KEY=your_api_key*" Pour lancer l'application utilisez la commande "*streamlit run main.py*"
***la logique du .env a été remplacée en prod par st.secrets['MISTRAL_API_KEY']***

## Utilisation
Vous pouvez déposer le dossier contenant les tickets de caisse dans la boite de dépot de gauche, et le relevé bancaire dans celle de droite, puis cliquer sur le bouton *start matching*. Après vous pourrez visualiser les résultats dans l'interface, et les télécharger au format .xls

## Résultats
Avant que HuggingFace nous mette des batons dans les roues (aparamment on fait trop de requêtes depuis streamlit vers les serverus de HgF) On était montés à 192 identifications sur 200 dont 190 bonnes identifications
Soit une précisions de 0.995, un recall de 0.950, une accuracy de 0.945 et un F1 Score de 0.972.
La méthode de matching alternative disponible en toggle sur l'application donne de bien moins bons résultats.