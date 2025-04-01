# Matching de tickets de caisse aux relevés bancaires

***Cette application streamlit permets à un utilisateur d'uploader un lot de tickets de caisse au format .jpg et un relevé bancaire au format ;csv et d'obtenir un tableur de correspondance visualisable dans l'application et téléchargeable au format .xlS***

## Installation
Cloner le repo. Créer un environnement virtuel, l'activer, installer les dépendances spécifiées dans le fichier *requirements.txt*. Créez un fichier .env à la racine du repo avec dedans "*MISTRAL_API_KEY=your_api_key*" Pour lancer l'application utilisez la commande "*streamlit run main.py*"

## Utilisation
Vous pouvez déposer le dossier contenant les tickets de caisse dans la boite de dépot de gauche, et le relevé bancaire dans celle de droite, puis cliquer sur le bouton valider en dessous. Après vous pourrez visualiser les résultats dans l'interface, et les télécharger au format .xls 