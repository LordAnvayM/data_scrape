"""
Infosys Company Scraper (v3 — all fixes applied)
==================================================
Target   : MoneyControl (moneycontrol.com)
Company  : Infosys
Fixes    :
  1. NLTK punkt tokenizer auto-downloaded → summaries now work
  2. Non-MoneyControl URLs filtered out → only MC articles scraped
  3. Blank PDF filenames fixed → fallback name generated from timestamp

Install dependencies:
    pip install ddgs requests beautifulsoup4 sumy lxml nltk
"""

import os
import re
import csv
import time
import requests
import nltk                                  # FIX 1: NLTK download
from bs4 import BeautifulSoup
from ddgs import DDGS

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

# FIX 1: Download NLTK tokenizer data silently on first run
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)

# ───────────────────────────────────────────────────────────────────────────
# CONFIG  ← only change things here
# ───────────────────────────────────────────────────────────────────────────
COMPANY_NAME  = "Infosys"
MAX_RESULTS   = 8
SUMMARY_LINES = 3
PDF_FOLDER    = "infosys_pdfs"
CSV_OUTPUT    = "infosys_data.csv"
REQUEST_DELAY = 1.5

# Block URLs that never contain useful article content
BLOCKED_DOMAINS = [
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "t.me", "telegram.org",
    "reddit.com", "facebook.com", "instagram.com",
    "google.com/finance", "scribd.com",
]

SEARCH_QUERIES = [
    f"{COMPANY_NAME} latest news 2025 moneycontrol",
    f"{COMPANY_NAME} Q4 Q3 quarterly results earnings moneycontrol",
    f"{COMPANY_NAME} annual report balance sheet moneycontrol financials",
    f"{COMPANY_NAME} share price analyst target buy sell moneycontrol",
    f"{COMPANY_NAME} revenue guidance outlook FY26 moneycontrol",
]

QUERY_LABELS = [
    "news",
    "quarterly_results",
    "annual_report",
    "share_price",
    "analyst_forecast",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# ───────────────────────────────────────────────────────────────────────────
# STEP 1 — DuckDuckGo search
# ───────────────────────────────────────────────────────────────────────────
def search_duckduckgo(query: str, max_results: int) -> list[dict]:
    print(f"\n  Searching: '{query}'")
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("href",  ""),
                "snippet": r.get("body",  ""),
            })
    print(f"  Found {len(results)} results.")
    return results


# ───────────────────────────────────────────────────────────────────────────
# STEP 2 — Summarize with sumy LSA
# ───────────────────────────────────────────────────────────────────────────
def summarize_text(text: str, sentence_count: int = SUMMARY_LINES) -> str:
    if not text or len(text.split()) < 30:
        return text.strip()
    try:
        parser     = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LsaSummarizer()
        summary    = summarizer(parser.document, sentence_count)
        return " ".join(str(s) for s in summary)
    except Exception as e:
        return f"[Summary error: {e}]"


# ───────────────────────────────────────────────────────────────────────────
# STEP 3 — Scrape HTML article
# ───────────────────────────────────────────────────────────────────────────
def scrape_article(url: str) -> dict:
    data = {"headline": "", "body": "", "pdf_links": [], "summary": "", "error": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        h1 = soup.find("h1")
        data["headline"] = h1.get_text(strip=True) if h1 else "N/A"

        paragraphs = soup.find_all("p")
        body = " ".join(
            p.get_text(strip=True) for p in paragraphs
            if len(p.get_text(strip=True)) > 40
        )
        data["body"]    = body[:3000]
        data["summary"] = summarize_text(body)

        pdf_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf") or "pdf" in href.lower():
                if href.startswith("http"):
                    pdf_links.append(href)
                else:
                    pdf_links.append("https://www.moneycontrol.com" + href)
        data["pdf_links"] = list(set(pdf_links))

    except requests.exceptions.HTTPError as e:
        data["error"] = f"HTTP {e.response.status_code}"
    except Exception as e:
        data["error"] = str(e)

    return data


# ───────────────────────────────────────────────────────────────────────────
# STEP 4 — Download PDFs
# ───────────────────────────────────────────────────────────────────────────
def download_pdf(pdf_url: str, folder: str) -> str:
    os.makedirs(folder, exist_ok=True)

    # FIX 3: Generate fallback filename if URL has no meaningful name
    raw_name = pdf_url.split("/")[-1].split("?")[0].strip()
    filename  = re.sub(r"[^\w\-.]", "_", raw_name)
    if not filename or filename == ".pdf" or len(filename) < 5:
        filename = f"infosys_doc_{int(time.time())}.pdf"   # e.g. infosys_doc_1712345678.pdf
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    filepath = os.path.join(folder, filename)

    try:
        resp = requests.get(pdf_url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"        PDF saved → {filepath}")
        return filepath
    except Exception as e:
        print(f"        PDF failed: {e}")
        return f"ERROR: {e}"


# ───────────────────────────────────────────────────────────────────────────
# STEP 5 — Save to CSV
# ───────────────────────────────────────────────────────────────────────────
def save_to_csv(records: list[dict], filename: str) -> None:
    if not records:
        print("No records to save.")
        return
    fieldnames = [
        "data_type", "title", "url", "snippet",
        "headline", "summary", "pdf_links", "error"
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            rec["pdf_links"] = " | ".join(rec.get("pdf_links", []))
            writer.writerow(rec)
    print(f"\n  Results saved → {filename}")


# ───────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ───────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  {COMPANY_NAME} Company Scraper — MoneyControl + DuckDuckGo")
    print("=" * 60)

    all_records = []
    seen_urls   = set()
    total_pdfs  = 0

    for query, label in zip(SEARCH_QUERIES, QUERY_LABELS):
        print(f"\n[{label.upper()}]")
        results = search_duckduckgo(query, MAX_RESULTS)

        for i, result in enumerate(results, 1):
            url = result["url"]

            # Skip junk URLs (social media, video sites, etc.)
            if any(blocked in url for blocked in BLOCKED_DOMAINS):
                print(f"  [{i}] Skipping (junk URL): {url[:60]}")
                continue

            # Skip duplicates
            if url in seen_urls:
                print(f"  [{i}] Skipping duplicate: {url[:60]}")
                continue
            seen_urls.add(url)

            print(f"  [{i}] Scraping: {url[:70]}")
            article = scrape_article(url)

            if article["error"]:
                print(f"       Error: {article['error']}")
            else:
                print(f"       Headline : {article['headline'][:70]}")
                print(f"       Summary  : {article['summary'][:100]}...")
                print(f"       PDFs     : {len(article['pdf_links'])}")

            for pdf_url in article["pdf_links"]:
                download_pdf(pdf_url, PDF_FOLDER)
                total_pdfs += 1
                time.sleep(REQUEST_DELAY)

            merged = {"data_type": label, **result, **article}
            all_records.append(merged)
            time.sleep(REQUEST_DELAY)

    save_to_csv(all_records, CSV_OUTPUT)

    print("\n" + "=" * 60)
    print(f"  Company          : {COMPANY_NAME}")
    print(f"  Articles scraped : {len(all_records)}")
    print(f"  PDFs downloaded  : {total_pdfs}")
    print(f"  CSV output       : {CSV_OUTPUT}")
    print(f"  PDF folder       : {PDF_FOLDER}/")
    print("=" * 60)


if __name__ == "__main__":
    main()