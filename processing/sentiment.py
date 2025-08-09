# processing/sentiment.py
import sqlite3, pandas as pd
from snownlp import SnowNLP
from processing.clean import clean_text

def sentiment_baseline(db="tieba.sqlite3", level="post"):
    conn = sqlite3.connect(db)
    if level == "post":
        df = pd.read_sql_query("SELECT id, tid, content, posted_at FROM posts", conn)
        text_series = df["content"].fillna("")
    else:
        df = pd.read_sql_query("""
            SELECT t.tid, t.title, group_concat(p.content, ' ') AS text
            FROM threads t LEFT JOIN posts p ON t.tid=p.tid
            GROUP BY t.tid
        """, conn)
        text_series = (df["title"].fillna("") + " " + df["text"].fillna(""))

    scores = []
    for s in text_series:
        s_clean = clean_text(s)
        try:
            score = SnowNLP(s_clean).sentiments  # 0~1，趋近1更正向
        except Exception:
            score = 0.5
        scores.append(score)

    conn.close()
    df_out = df.copy()
    df_out["sent_score"] = scores
    df_out["sent_label"] = pd.cut(df_out["sent_score"], bins=[-0.01,0.35,0.65,1.01], labels=["neg","neu","pos"])
    return df_out
