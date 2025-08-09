# storage/db.py
import sqlite3, time
DB = "tieba.sqlite3"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS threads(
      tid TEXT PRIMARY KEY, title TEXT, author TEXT, reply_count INTEGER,
      url TEXT, created_at TEXT, last_reply_at TEXT, bar_name TEXT, crawled_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS posts(
      id INTEGER PRIMARY KEY AUTOINCREMENT, tid TEXT, floor INTEGER,
      author TEXT, content TEXT, posted_at TEXT, url TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS crawl_log(
      bar_name TEXT, page INTEGER, crawled_at TEXT,
      PRIMARY KEY(bar_name, page)
    )""")
    return conn

def upsert_thread(conn, row):
    conn.execute("""INSERT INTO threads(tid,title,author,reply_count,url,created_at,last_reply_at,bar_name,crawled_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(tid) DO UPDATE SET
                      title=excluded.title, reply_count=excluded.reply_count,
                      last_reply_at=excluded.last_reply_at, crawled_at=excluded.crawled_at, bar_name=excluded.bar_name
                  """,
                  (row["tid"], row["title"], row["author"], row["reply_count"], row["url"],
                   row["created_at"], row["last_reply_at"], row["bar_name"], row["crawled_at"]))
    conn.commit()

def insert_post(conn, tid, floor, author, content, posted_at, url):
    conn.execute("""INSERT INTO posts(tid,floor,author,content,posted_at,url) VALUES(?,?,?,?,?,?)""",
                 (tid, floor, author, content, posted_at, url))
    conn.commit()

def upsert_crawl_log(conn, bar_name, page):
    conn.execute("""INSERT OR REPLACE INTO crawl_log(bar_name,page,crawled_at) VALUES(?,?,?)""",
                 (bar_name, page, time.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
