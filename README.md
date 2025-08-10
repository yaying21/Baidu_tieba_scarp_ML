**Collecte et Analyse de Données — Baidu Tieba (« 华为 »)**

**Contexte**

Ce projet implémente un pipeline complet pour collecter, nettoyer, analyser et rapporter des données issues de Baidu Tieba, en se concentrant sur le bar « 华为 ».
Il combine Selenium pour la collecte, SQLite pour la persistance, et des techniques de Traitement Automatique du Langage (TAL) pour l’analyse thématique et la détection du sentiment.

**Objectifs**

Collecter :

Titres, auteurs, nombre de réponses, URLs des threads.

Contenus des posts (texte, auteur, date, lien).

Nettoyer :

Suppression d’URLs, espaces, caractères inutiles.

Tokenisation avec jieba.

Analyser :

Analyse thématique par LDA et TF-IDF.

Analyse de sentiment avec SnowNLP.

Rapporter :

Export CSV (mots-clés des sujets, affectation des threads à un sujet, scores de sentiment).

Graphique de répartition des sentiments.

**Structure du projet**

project/

  collector/
  
    tieba_spider.py     # Spider Selenium pour extraire les données
    
  processing/
    clean.py            # Nettoyage texte et tokenisation
    sentiment.py        # Analyse de sentiment (post ou thread)
    topic.py            # Modélisation thématique LDA
  reports/
    summarize.py        # Génération des exports CSV et graphiques
  storage/
    db.py               # Création et mise à jour de la base SQLite
  main.py               # CLI pour lancer crawl et report

**Lancer la collecte**
  python3 main.py crawl --bar "华为" --pages * --posts *

**Générer un rapport**
python3 main.py report

Cela crée :

topic_keywords.csv → mots-clés par sujet

thread_topics.csv → sujets attribués aux threads

post_sentiment.csv → scores et labels de sentiment

sentiment_bar.png → histogramme de la répartition des sentiments

Exemple de pipeline
Crawl : tieba_spider.py → stockage dans SQLite via db.py.

Traitement :

clean.py : nettoyage + tokenisation.

topic.py : extraction de thèmes avec LDA.

sentiment.py : scoring de sentiment.

Rapport : summarize.py → CSV + PNG.
