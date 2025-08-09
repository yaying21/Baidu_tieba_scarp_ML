# processing/topic.py
import sqlite3, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from processing.clean import clean_text, tokenize

def lda_topics(db="tieba.sqlite3", n_topics=6, max_features=3000):
    conn = sqlite3.connect(db)
    df = pd.read_sql_query("""
        SELECT t.tid, t.title, group_concat(p.content, ' ') AS text
        FROM threads t LEFT JOIN posts p ON t.tid=p.tid
        GROUP BY t.tid
    """, conn)
    conn.close()

    docs = [" ".join(tokenize(clean_text((ti or "") + " " + (tx or "")))) for ti, tx in zip(df.title, df.text)]
    vec = TfidfVectorizer(max_features=max_features)
    X = vec.fit_transform(docs)

    lda = LatentDirichletAllocation(n_components=n_topics, learning_method="batch", random_state=42)
    W = lda.fit_transform(X)
    H = lda.components_
    vocab = vec.get_feature_names_out()

    # 每个主题前10词
    topics = []
    for k in range(n_topics):
        top_idx = H[k].argsort()[-10:][::-1]
        topics.append([vocab[i] for i in top_idx])

    df_topics = pd.DataFrame({
        "tid": df.tid,
        "title": df.title,
        "topic": W.argmax(axis=1)
    })
    return topics, df_topics
