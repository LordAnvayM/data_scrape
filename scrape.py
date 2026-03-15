"""
Infosys Company Scraper v4
===========================
Target   : MoneyControl, Economic Times, LiveMint + more
Company  : Infosys
Features :
  - 15 focused DuckDuckGo search queries
  - Selenium login for Economic Times and LiveMint
  - LSA summarization with 1000-word cap + 10s timeout
  - PDF download filtered by trusted domains + company name
  - Junk URL blocklist
  - Quality checks (min words + Infosys mention)
  - Delay between DDG queries to avoid rate limiting

Install:
    pip install ddgs requests beautifulsoup4 sumy lxml nltk selenium webdriver-manager
"""

import os
import re
import csv
import time
import threading
import requests
import nltk
from bs4 import BeautifulSoup
from ddgs import DDGS

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer

nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)

# ───────────────────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────────────────
COMPANY_NAME       = "Infosys"
MAX_RESULTS        = 15           # DuckDuckGo results per query
SUMMARY_LINES      = 3           # sentences per summary
PDF_FOLDER         = "infosys_pdfs"
CSV_OUTPUT         = "infosys_data.csv"
REQUEST_DELAY      = 1.5         # seconds between page requests
QUERY_DELAY        = 4.0         # seconds between DDG queries (avoid rate limit)
CREDENTIALS_FILE   = "credentials.txt"

BLOCKED_DOMAINS = [
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "t.me", "telegram.org",
    "reddit.com", "facebook.com", "instagram.com",
    "google.com/finance", "scribd.com",
]

TRUSTED_PDF_DOMAINS = [
    "moneycontrol.com",
    "bseindia.com",
    "nseindia.com",
    "infosys.com",
    "sebi.gov.in",
]

# 15 queries covering different angles of Infosys data
SEARCH_QUERIES = [
    # Core financials
    f"{COMPANY_NAME} latest news 2025 moneycontrol",
    f"{COMPANY_NAME} Q4 Q3 quarterly results earnings moneycontrol",
    f"{COMPANY_NAME} annual report balance sheet moneycontrol financials",
    f"{COMPANY_NAME} share price analyst target buy sell moneycontrol",
    f"{COMPANY_NAME} revenue guidance outlook FY26 moneycontrol",
    # Management & strategy
    f"{COMPANY_NAME} CEO Salil Parekh interview statement 2025",
    f"{COMPANY_NAME} deal wins large contracts TCV 2025",
    f"{COMPANY_NAME} AI strategy cloud partnerships 2025",
    # Employee & operations
    f"{COMPANY_NAME} attrition headcount hiring employees 2025",
    f"{COMPANY_NAME} dividend buyback shareholder return 2025",
    # Segment performance
    f"{COMPANY_NAME} BFSI manufacturing retail segment performance",
    f"{COMPANY_NAME} North America Europe revenue client growth",
    # Market & competition
    f"{COMPANY_NAME} vs TCS Wipro HCL comparison market share",
    f"{COMPANY_NAME} margin EBIT operating profit analysis",
    # ESG & governance
    f"{COMPANY_NAME} ESG sustainability governance report 2025",
]

QUERY_LABELS = [
    "news",
    "quarterly_results",
    "annual_report",
    "share_price",
    "analyst_forecast",
    "management",
    "deals",
    "strategy",
    "employees",
    "dividends",
    "segments",
    "geography",
    "competition",
    "margins",
    "esg",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ───────────────────────────────────────────────────────────────────────────
# LOGIN CONFIG — site-specific Selenium login instructions
# ───────────────────────────────────────────────────────────────────────────
# Only sites that support email + password login (no OTP)
# LiveMint uses OTP — cannot be automated, excluded
LOGIN_CONFIGS = {
    "economictimes.indiatimes.com": {
        "login_url":      "https://economictimes.indiatimes.com/login",
        "email_selector": "input[name='email'], input[type='email'], #email",
        "pass_selector":  "input[name='password'], input[type='password'], #password",
        "submit_selector":"button[type='submit'], input[type='submit'], .login-btn",
        "success_check":  "logout",
    },
}


# ───────────────────────────────────────────────────────────────────────────
# STEP 0 — Load credentials from file
# ───────────────────────────────────────────────────────────────────────────
def load_credentials(filepath: str) -> dict:
    """
    Reads credentials.txt and returns a dict:
    { "economictimes.indiatimes.com": ("email", "password"), ... }
    """
    creds = {}
    if not os.path.exists(filepath):
        print(f"  [AUTH] No credentials file found at '{filepath}' — skipping login.")
        return creds

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                domain, email, password = parts
                creds[domain] = (email, password)
                print(f"  [AUTH] Loaded credentials for: {domain}")
    return creds


# ───────────────────────────────────────────────────────────────────────────
# STEP 0b — Selenium login → returns cookies for requests session
# ───────────────────────────────────────────────────────────────────────────
def selenium_login(domain: str, email: str, password: str) -> dict:
    """
    Uses Selenium to log into a site and returns cookies as a dict
    that can be injected into a requests.Session.
    Returns empty dict if login fails.
    """
    cookies = {}
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        print(f"  [AUTH] Launching browser for {domain}...")

        options = Options()
        options.add_argument("--headless")           # run invisibly
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        config = LOGIN_CONFIGS[domain]
        driver.get(config["login_url"])
        time.sleep(3)   # let page load

        wait = WebDriverWait(driver, 15)

        # Fill email
        for sel in config["email_selector"].split(","):
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel.strip())))
                el.clear()
                el.send_keys(email)
                break
            except Exception:
                continue

        # Fill password
        for sel in config["pass_selector"].split(","):
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel.strip())
                el.clear()
                el.send_keys(password)
                break
            except Exception:
                continue

        # Click submit
        for sel in config["submit_selector"].split(","):
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel.strip())
                btn.click()
                break
            except Exception:
                continue

        time.sleep(4)   # wait for redirect after login

        # Check login succeeded
        if config["success_check"].lower() in driver.page_source.lower():
            print(f"  [AUTH] ✓ Login successful for {domain}")
        else:
            print(f"  [AUTH] ⚠ Login may have failed for {domain} — continuing with cookies anyway")

        # Extract cookies from browser and convert to requests format
        for cookie in driver.get_cookies():
            cookies[cookie["name"]] = cookie["value"]

        driver.quit()
        print(f"  [AUTH] {len(cookies)} cookies extracted for {domain}")

    except ImportError:
        print("  [AUTH] Selenium not installed. Run: pip install selenium webdriver-manager")
    except Exception as e:
        print(f"  [AUTH] Login failed for {domain}: {e}")

    return cookies


# ───────────────────────────────────────────────────────────────────────────
# STEP 1 — DuckDuckGo search
# ───────────────────────────────────────────────────────────────────────────
def search_duckduckgo(query: str, max_results: int) -> list[dict]:
    print(f"\n  Searching: '{query}'")
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href",  ""),
                    "snippet": r.get("body",  ""),
                })
    except Exception as e:
        print(f"  DDG error: {e}")
    print(f"  Found {len(results)} results.")
    return results


# ───────────────────────────────────────────────────────────────────────────
# STEP 2 — Summarize with sumy LSA
# ───────────────────────────────────────────────────────────────────────────
def summarize_text(text: str, sentence_count: int = SUMMARY_LINES) -> str:
    if not text or len(text.split()) < 30:
        return text.strip()

    words = text.split()
    if len(words) > 1000:
        text = " ".join(words[:1000])

    result = [None]
    error  = [None]

    def _run():
        try:
            parser     = PlaintextParser.from_string(text, Tokenizer("english"))
            summarizer = LsaSummarizer()
            summary    = summarizer(parser.document, sentence_count)
            result[0]  = " ".join(str(s) for s in summary)
        except Exception as e:
            error[0] = str(e)

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=10)

    if t.is_alive():
        return "[Summary skipped: took too long]"
    if error[0]:
        return f"[Summary error: {error[0]}]"
    return result[0] or ""


# ───────────────────────────────────────────────────────────────────────────
# STEP 3 — Scrape HTML article
# ───────────────────────────────────────────────────────────────────────────
def scrape_article(url: str, session: requests.Session = None) -> dict:
    """
    Scrape a single article page.
    If a requests.Session with login cookies is passed, it's used instead
    of a plain request — enabling access to login-protected pages.
    """
    data = {"headline": "", "body": "", "pdf_links": [], "summary": "", "error": ""}
    try:
        requester = session if session else requests
        resp = requester.get(url, headers=HEADERS, timeout=10)
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
            href     = a["href"]
            alt_text = a.get_text(strip=True).lower()

            if not (href.lower().endswith(".pdf") or "pdf" in href.lower()):
                continue

            if not href.startswith("http"):
                href = "https://www.moneycontrol.com" + href

            if not any(domain in href for domain in TRUSTED_PDF_DOMAINS):
                continue

            if COMPANY_NAME.lower() not in href.lower() and \
               COMPANY_NAME.lower() not in alt_text:
                continue

            pdf_links.append(href)

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

    raw_name = pdf_url.split("/")[-1].split("?")[0].strip()
    filename  = re.sub(r"[^\w\-.]", "_", raw_name)
    if not filename or filename == ".pdf" or len(filename) < 5:
        filename = f"infosys_doc_{int(time.time())}.pdf"
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
    print(f"  {COMPANY_NAME} Company Scraper v4 — DuckDuckGo + Selenium")
    print("=" * 60)

    # ── Load credentials and create authenticated sessions ──────────────────
    credentials = load_credentials(CREDENTIALS_FILE)
    sessions    = {}   # domain → requests.Session with login cookies

    for domain, (email, password) in credentials.items():
        if domain not in LOGIN_CONFIGS:
            print(f"  [AUTH] No login config for {domain} — skipping.")
            continue
        cookies = selenium_login(domain, email, password)
        if cookies:
            s = requests.Session()
            s.cookies.update(cookies)
            sessions[domain] = s
            print(f"  [AUTH] Session ready for {domain}")

    # ── Main scraping loop ───────────────────────────────────────────────────
    all_records = []
    seen_urls   = set()
    total_pdfs  = 0

    for query, label in zip(SEARCH_QUERIES, QUERY_LABELS):
        print(f"\n[{label.upper()}]")
        results = search_duckduckgo(query, MAX_RESULTS)

        for i, result in enumerate(results, 1):
            url = result["url"]

            # Skip junk URLs
            if any(blocked in url for blocked in BLOCKED_DOMAINS):
                print(f"  [{i}] Skipping (junk URL): {url[:60]}")
                continue

            # Skip duplicates
            if url in seen_urls:
                print(f"  [{i}] Skipping duplicate: {url[:60]}")
                continue
            seen_urls.add(url)

            # Use authenticated session if available for this domain
            session = None
            for domain, sess in sessions.items():
                if domain in url:
                    session = sess
                    print(f"  [{i}] Scraping (authenticated): {url[:65]}")
                    break
            else:
                print(f"  [{i}] Scraping: {url[:70]}")

            article = scrape_article(url, session=session)

            if article["error"]:
                print(f"       Error: {article['error']}")
                continue

            word_count = len(article["body"].split())
            if word_count < 50:
                print(f"       Skipping (too little content: {word_count} words)")
                continue

            combined = (article["headline"] + article["body"]).lower()
            if "infosys" not in combined:
                print(f"       Skipping (Infosys not mentioned)")
                continue

            print(f"       Headline : {article['headline'][:70]}")
            print(f"       Summary  : {article['summary'][:100]}...")
            print(f"       PDFs     : {len(article['pdf_links'])}")

            for pdf_url in article["pdf_links"]:
                result = download_pdf(pdf_url, PDF_FOLDER)
                if not result.startswith("ERROR"):
                    total_pdfs += 1
                time.sleep(REQUEST_DELAY)

            merged = {"data_type": label, **result, **article}
            all_records.append(merged)
            time.sleep(REQUEST_DELAY)

        # Delay between queries to avoid DDG rate limiting
        time.sleep(QUERY_DELAY)

    save_to_csv(all_records, CSV_OUTPUT)

    print("\n" + "=" * 60)
    print(f"  Company          : {COMPANY_NAME}")
    print(f"  Articles scraped : {len(all_records)}")
    print(f"  PDFs downloaded  : {total_pdfs}")
    print(f"  Authenticated    : {list(sessions.keys()) or 'None'}")
    print(f"  CSV output       : {CSV_OUTPUT}")
    print(f"  PDF folder       : {PDF_FOLDER}/")
    print("=" * 60)


if __name__ == "__main__":
    main()