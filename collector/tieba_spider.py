# collector/tieba_spider.py
import os, sys, platform   # ← 加上 platform
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import time, re, math, random, sqlite3
from urllib.parse import urlencode, urljoin
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
from storage.db import get_conn, upsert_thread, insert_post, upsert_crawl_log



HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

BASE = "https://tieba.baidu.com/"

_driver = None
_req = None

def _get_req():
    """requests 会话（带浏览器头、可用 env 注入 Cookie）"""
    global _req
    if _req:
        return _req
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://tieba.baidu.com/",
        "Connection": "keep-alive",
    })
    # 从环境变量注入 Cookie（在 WSL 下 export BAIDUID=... 等）
    for k in ["BAIDUID","BAIDUID_BFESS","BIDUPSID","PSTM","H_PS_PSSID","ZFY","BDUSS","BDUSS_BFESS"]:
        v = os.getenv(k)
        if v:
            s.cookies.set(k, v, domain=".baidu.com")
            s.cookies.set(k, v, domain=".tieba.baidu.com")
    rty = Retry(total=2, backoff_factor=0.7,
                status_forcelist=(403,429,500,502,503,504),
                allowed_methods=frozenset(["GET","HEAD"]))
    s.mount("https://", HTTPAdapter(max_retries=rty))
    s.mount("http://", HTTPAdapter(max_retries=rty))
    _req = s
    return s

def _get_driver():
    """跨平台初始化 Chrome；WSL/Linux 指定 binary 与禁用 sandbox"""
    global _driver
    if _driver:
        return _driver
    opts = Options()
    opts.add_argument("--headless=new")        # 排障可临时注释
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1200,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--blink-settings=imagesEnabled=false")   # 提速：不加载图片
    if platform.system() != "Windows":
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        for p in ("/usr/bin/google-chrome","/usr/bin/google-chrome-stable",
                  "/usr/bin/chromium","/usr/bin/chromium-browser"):
            if os.path.exists(p):
                opts.binary_location = p
                break
    # 不等待全部资源；后面我们显式等待元素
    opts.page_load_strategy = "none"

    d = uc.Chrome(options=opts)
    d.set_page_load_timeout(60)
    d.set_script_timeout(60)
    # 同时把 client 超时也拉长，避免 webdriver 本地端口读超时
    try:
        d.command_executor._client_config.timeout = 180
    except Exception:
        pass
    _driver = d
    return d

def _restart_driver():
    global _driver
    try:
        if _driver:
            _driver.quit()
    except Exception:
        pass
    _driver = None
    time.sleep(1.0)

def fetch(url, sleep=(0.6, 1.2), wait_css: str | None = None, attempts: int = 3):
    """
    优先用 Selenium：
      - page_load_strategy='none' 先返回
      - 等 DOM 至 interactive/complete
      - 显式等待目标元素出现
      - 滚动一次触发懒加载
    失败后：
      - 重启浏览器再试
      - 最后回退到 requests+Cookie
    """
    last_err = None
    for k in range(attempts):
        try:
            d = _get_driver()
            d.get(url)

            # 1) 等 DOM 就绪（≤10s）
            end = time.time() + 10
            while time.time() < end:
                try:
                    state = d.execute_script("return document.readyState")
                except Exception:
                    state = None
                if state in ("interactive","complete"):
                    break
                time.sleep(0.2)

            # 2) 等待我们关心的元素（≤12s）
            if wait_css:
                WebDriverWait(d, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
                )

            # 3) 触发一次懒加载
            try:
                d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

            time.sleep(random.uniform(*sleep))
            return d.page_source

        except Exception as e:
            last_err = e
            # 第一次失败时重启浏览器，再试
            _restart_driver()
            time.sleep(1.0 + k)

    # ---- Fallback：requests + Cookie （保证任务不中断）----
    try:
        rs = _get_req()
        r = rs.get(url, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception:
        # 最后兜底：返回空串，交由上游解析/跳过
        return ""

def list_url(bar_name: str, page: int):
    # pn 按 50 递增（每页约 50 主题）
    qs = urlencode({"kw": bar_name, "pn": page * 50})
    return urljoin(BASE, f"f?{qs}")

def parse_thread_list(html):
    soup = BeautifulSoup(html, "lxml")
    items = []
    for li in soup.select("li.j_thread_list.clearfix"):
        a = li.select_one("a.j_th_tit")
        if not a: 
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        url = urljoin(BASE, href)
        tid = re.search(r"/p/(\d+)", href)
        tid = tid.group(1) if tid else None

        reply = li.select_one("span.threadlist_rep_num.center_text")
        reply_count = int(reply.get_text(strip=True)) if reply else None

        author = li.select_one("span.frs-author-name")
        author = author.get_text(strip=True) if author else None

        last_time = li.select_one("span.threadlist_reply_date")
        last_reply_at = last_time.get_text(strip=True) if last_time else None

        if tid:
            items.append({
                "tid": tid, "title": title, "url": url,
                "reply_count": reply_count, "author": author,
                "last_reply_at": last_reply_at
            })
    return items

def parse_posts(html):
    soup = BeautifulSoup(html, "lxml")
    posts = []
    # 帖子页楼层容器（可能变动，保留两个选择器作为兜底）
    floors = soup.select("div.l_post") or soup.select("div.l_post_bright")
    if not floors:
        # 新样式：按 post_content、d_post_content_main
        floors = soup.select("div.p_postlist > div.l_post")

    for i, div in enumerate(floors, start=1):
        # 内容
        content = div.select_one(".d_post_content") or div.select_one(".d_post_content_main")
        text = content.get_text("\n", strip=True) if content else ""
        # 作者
        author = None
        au = div.select_one(".p_author_name")
        if au:
            author = au.get_text(strip=True)
        # 时间
        tm = div.select_one("span.tail-info")  # tail-info 通常包含时间与设备
        posted_at = None
        if tm:
            # 找包含 ":" 或 "-" 的片段
            for t in tm.parent.select("span.tail-info"):
                s = t.get_text(strip=True)
                if ":" in s or "-" in s:
                    posted_at = s

        posts.append({
            "floor": i,
            "author": author,
            "content": text,
            "posted_at": posted_at
        })
    return posts

def crawl_bar(bar_name: str, max_pages: int = 2, max_posts_per_thread: int = 2):
    conn = get_conn()
    for page in range(max_pages):
        url = list_url(bar_name, page)
        html = fetch(url, wait_css="li.j_thread_list")
        items = parse_thread_list(html)

        for it in items:
            upsert_thread(conn, {
                **it,
                "bar_name": bar_name,
                "created_at": None,
                "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })

            # 抓帖子前 N 页
            for pn in range(1, max_posts_per_thread + 1):
                post_url = f"{it['url']}?pn={pn}"
                p_html = fetch(post_url, wait_css="div.p_postlist, div.l_post")
                posts = parse_posts(p_html)

                # 如果本轮没解析到楼层，重试一次再解析（仍在 for pn 内）
                if not posts:
                    continue

                # 现在统一入库（避免重试后未写入）
                for p in posts:
                    insert_post(conn, it["tid"], p["floor"], p["author"],
                                p["content"], p["posted_at"], post_url)

        upsert_crawl_log(conn, bar_name, page)
    conn.close()


import atexit
def _cleanup():
    global _driver
    try:
        if _driver:
            _driver.quit()
    except Exception:
        pass
atexit.register(_cleanup)


if __name__ == "__main__":
    import argparse, sys, logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="运行冒烟测试（只抓1页列表+首贴1页内容）")
    ap.add_argument("--bar", type=str, default="测试", help="贴吧名，例如：华为")
    args = ap.parse_args()

    if not args.smoke:
        print("用法示例：python collector/tieba_spider.py --smoke --bar 华为")
        sys.exit(0)

    try:
        # 1) 抓1页列表
        url = list_url(args.bar, page=0)
        logging.info(f"GET {url}")
        html = fetch(url, wait_css="li.j_thread_list")
        items = parse_thread_list(html)
        logging.info(f"列表解析到 {len(items)} 条")

        if not items:
            logging.error("未解析到任何帖子，可能是页面结构变化或访问受限。")
            sys.exit(2)

        # 2) 抓首贴第1页内容
        first = items[0]
        post_url = f"{first['url']}?pn=1"
        logging.info(f"GET {post_url}")
        p_html = fetch(post_url, wait_css="div.p_postlist, div.l_post")
        posts = parse_posts(p_html)
        logging.info(f"首贴解析到 {len(posts)} 个楼层")

        # 3) 判定通过/失败
        if len(posts) == 0:
            logging.error("帖子页解析到 0 楼层，疑似选择器失效。")
            sys.exit(3)

        # 打印几条示例文本
        sample = [p.get("content", "")[:60].replace("\n", " ") for p in posts[:3]]
        logging.info("样例楼层内容：\n- " + "\n- ".join(sample))
        logging.info("SMOKE TEST PASSED ✅")
        sys.exit(0)

    except Exception as e:
        logging.exception(f"SMOKE TEST FAILED ❌: {e}")
        sys.exit(1)
