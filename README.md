# Infosys Company Scraper v4

A Python web scraper that collects financial news, quarterly results, analyst reports, deal wins, ESG data, and research PDFs about **Infosys** using DuckDuckGo as the search engine and BeautifulSoup for HTML parsing. Achieves ~118 articles and ~33 PDFs per run across 15 focused search queries.

---

## Project Structure

```
project/
│
├── scraper.py     ← main script
├── credentials.txt        ← login details (Economic Times)
├── requirements.txt       ← dependencies
├── README.md              ← this file
│
├── infosys_data.csv       ← generated on run (scraped articles)
└── infosys_pdfs/          ← generated on run (downloaded broker PDFs)
```

---

## Quickstart

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Fill in credentials** *(optional)*

Open `credentials.txt` and add your Economic Times login:
```
economictimes.indiatimes.com | your@email.com | yourpassword
```
If you skip this, ET pages will still be scraped — just without authentication.

**3. Run**
```bash
python scraper.py
```

NLTK tokenizer data and ChromeDriver install automatically on first run.

---

## How It Works

```
0. Load credentials.txt
   └─ Selenium logs into Economic Times (headless Chrome)
   └─ Cookies injected into requests.Session for ET pages

1. DuckDuckGo Search
   └─ 15 queries × 15 results = up to 225 URLs discovered
   └─ 4 second delay between queries to avoid DDG rate limiting

2. Filter each URL
   ├─ Block junk domains (YouTube, Twitter, Telegram, Reddit, etc.)
   └─ Skip duplicates already seen in earlier queries

3. Scrape HTML
   ├─ Use authenticated session if URL is from Economic Times
   ├─ Extract H1 headline
   ├─ Extract body text from <p> tags
   └─ Collect PDF links (trusted domains + Infosys mention only)

4. Quality Check
   ├─ Skip if fewer than 50 words of body text
   └─ Skip if "Infosys" not mentioned in headline or body

5. Summarize
   └─ LSA algorithm (sumy) → 3 key sentences
      · Input capped at 1000 words (prevents hangs on large docs)
      · 10 second timeout — skips gracefully if too slow

6. Download PDFs
   └─ Only from: moneycontrol.com, bseindia.com, nseindia.com,
                 infosys.com, sebi.gov.in
   └─ URL or anchor text must mention "Infosys"

7. Save everything to CSV
```

---

## 15 Search Queries

| Label | Query Focus |
|-------|-------------|
| `news` | Latest Infosys news 2025 |
| `quarterly_results` | Q3/Q4 earnings and results |
| `annual_report` | Balance sheet and financials |
| `share_price` | Analyst targets, buy/sell ratings |
| `analyst_forecast` | FY26 revenue guidance |
| `management` | CEO Salil Parekh interviews and statements |
| `deals` | Large deal wins and TCV |
| `strategy` | AI, cloud, and partnership news |
| `employees` | Attrition, headcount, and hiring |
| `dividends` | Dividend and buyback announcements |
| `segments` | BFSI, manufacturing, retail performance |
| `geography` | North America and Europe revenue |
| `competition` | vs TCS, Wipro, HCL comparison |
| `margins` | EBIT and operating profit analysis |
| `esg` | ESG, sustainability, governance |

---

## Output

### `infosys_data.csv`

| Column | Description |
|--------|-------------|
| `data_type` | Which query found this article |
| `title` | Page title from DuckDuckGo |
| `url` | Full URL of the scraped page |
| `snippet` | Short preview text from DuckDuckGo |
| `headline` | H1 heading scraped from the page |
| `summary` | 3-sentence LSA extractive summary |
| `pdf_links` | Pipe-separated PDF URLs found on the page |
| `error` | Any HTTP or network error encountered |

### `infosys_pdfs/`
Broker research notes downloaded from MoneyControl and BSE/NSE — typically from ICICI Securities, Emkay, Motilal Oswal, Anand Rathi, and Prabhudas Lalwai.

---

## Configuration

All settings are at the top of `scraper.py`:

```python
COMPANY_NAME       = "Infosys"   # change to scrape any other company
MAX_RESULTS        = 8           # DuckDuckGo results per query
SUMMARY_LINES      = 3           # sentences per summary
REQUEST_DELAY      = 1.5         # seconds between page requests
QUERY_DELAY        = 4.0         # seconds between DDG queries
CREDENTIALS_FILE   = "credentials.txt"
```

---

## Selenium Login

The scraper attempts to log into **Economic Times** automatically using Selenium before scraping begins.

- Runs in **headless mode** — no browser window opens
- Cookies extracted from browser and injected into `requests.Session`
- ChromeDriver installs automatically via `webdriver-manager`
- If login fails or credentials are missing, ET pages are scraped without authentication — the rest of the scraper is unaffected

> **Note:** Economic Times may require OTP verification depending on account settings, in which case the login silently falls back to unauthenticated scraping.

---

## Libraries Used

| Library | Purpose |
|---------|---------|
| `ddgs` | DuckDuckGo search — no API key needed |
| `requests` | Fetch pages and PDFs |
| `beautifulsoup4` | Parse HTML and extract content |
| `sumy` + `nltk` | LSA extractive summarization |
| `lxml` | Fast HTML parser |
| `selenium` | Automate browser login for Economic Times |
| `webdriver-manager` | Auto-installs ChromeDriver |

---

## Known Limitations

| Issue | Cause | Workaround |
|-------|-------|------------|
| Infosys.com returns 403 on all pages | Cloudflare bot protection | None — not scrapeable |
| Business Standard returns 403 | Cloudflare + paid subscription | None |
| Trendlyne, Groww, Investing.com return 0 words | JavaScript-rendered pages | Would need Selenium to render |
| ET login may not fully authenticate | Possible OTP requirement on account | Use a password-only ET account |
| LiveMint login not supported | OTP-only login, cannot be automated | Scraped unauthenticated (most articles are public) |
| DuckDuckGo results vary per run | DDG rotates results | Expected behaviour — run produces different URLs each time |