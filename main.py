# main.py
import argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crawl", "report"])
    ap.add_argument("--bar")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--posts", type=int, default=2)
    args = ap.parse_args()

    if args.cmd == "crawl":
        from collector.tieba_spider import crawl_bar
        if not args.bar:
            raise SystemExit("--bar 必填")
        # 可选：给一点运行提示
        print(f"[crawl] bar={args.bar} pages={args.pages} posts={args.posts}")
        crawl_bar(args.bar, max_pages=args.pages, max_posts_per_thread=args.posts)
        print("[crawl] done.")

    elif args.cmd == "report":
        from reports.summarize import build_report
        print("[report] building report ...")
        build_report()
        print("[report] done.")

if __name__ == "__main__":
    main()
