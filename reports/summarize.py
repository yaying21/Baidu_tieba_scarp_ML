# reports/summarize.py
import sqlite3, pandas as pd, matplotlib.pyplot as plt
from processing.topic import lda_topics
from processing.sentiment import sentiment_baseline

def build_report(db="tieba.sqlite3"):
    topics, df_topics = lda_topics(db)
    df_sent = sentiment_baseline(db, level="post")

    # 主题词展示
    topic_df = pd.DataFrame({"topic_id": list(range(len(topics))),
                             "keywords": [", ".join(t) for t in topics]})
    topic_df.to_csv("topic_keywords.csv", index=False)
    df_topics.to_csv("thread_topics.csv", index=False)
    df_sent.to_csv("post_sentiment.csv", index=False)

    # 情感分布图
    ax = df_sent["sent_label"].value_counts().sort_index().plot(kind="bar", rot=0, title="Post Sentiment")
    plt.tight_layout()
    plt.savefig("sentiment_bar.png")
    print("导出：topic_keywords.csv / thread_topics.csv / post_sentiment.csv / sentiment_bar.png")
