# processing/clean.py
import re, jieba

URL_RE = re.compile(r"https?://\S+")
SPACE_RE = re.compile(r"\s+")

def clean_text(s: str) -> str:
    s = s or ""
    s = URL_RE.sub(" ", s)
    s = s.replace("\u3000", " ")
    s = SPACE_RE.sub(" ", s).strip()
    return s

def tokenize(s: str):
    s = clean_text(s)
    return [w for w in jieba.cut(s) if w.strip()]
