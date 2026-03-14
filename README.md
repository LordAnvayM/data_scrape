# Infosys Company Scraper

A Python web scraper that collects financial news, quarterly results, analyst reports, and research PDFs about **Infosys** using DuckDuckGo as the search engine and BeautifulSoup for HTML parsing.

---

## Project Structure

```
project/
│
├── infosys_scraper.py     ← main script
├── requirements.txt       ← dependencies
├── README.md              ← this file
│
├── infosys_data.csv       ← generated on run (scraped articles)
└── infosys_pdfs/          ← generated on run (downloaded broker PDFs)
```

---

## Quickstart

```bash
pip install -r requirements.txt
python infosys_scraper.py
```

NLTK tokenizer data downloads automatically on the first run. No API keys required.

---

## How It Works

The scraper runs a 5-step pipeline for each of 5 search queries:

```
1. DuckDuckGo Search
   └─ 5 queries × 8 results = up to 40 URLs discovered

2. Filter
   ├─ Block junk domains (YouTube, Twitter, Telegram, Reddit, etc.)
   ├─ Skip duplicates seen in earlier queries
   ├─ Skip pages with fewer than 50 words of body text
   └─ Skip pages that don't mention "Infosys" at all

3. Scrape HTML
   ├─ Extract H1 headline
   ├─ Extract body text from <p> tags
   └─ Collect PDF links (trusted domains only)

4. Summarize
   └─ LSA algorithm (sumy) → 3 key sentences
      · Input capped at 1000 words to prevent hangs on large documents
      · 10-second timeout — skips gracefully if LSA takes too long

5. Download PDFs
   └─ Only PDFs from trusted domains that mention "Infosys"
      Trusted: moneycontrol.com, bseindia.com, nseindia.com,
               infosys.com, sebi.gov.in
```

---

## Search Queries

The scraper runs 5 focused queries targeting different types of data:

| Label | Query |
|-------|-------|
| `news` | Infosys latest news 2025 moneycontrol |
| `quarterly_results` | Infosys Q4 Q3 quarterly results earnings moneycontrol |
| `annual_report` | Infosys annual report balance sheet moneycontrol financials |
| `share_price` | Infosys share price analyst target buy sell moneycontrol |
| `analyst_forecast` | Infosys revenue guidance outlook FY26 moneycontrol |

---

## Output

### `infosys_data.csv`

Each row is one scraped article.

| Column | Description |
|--------|-------------|
| `data_type` | Which query found this article (`news`, `quarterly_results`, etc.) |
| `title` | Page title from DuckDuckGo search result |
| `url` | Full URL of the scraped page |
| `snippet` | Short preview text from DuckDuckGo |
| `headline` | H1 heading scraped from the page |
| `summary` | 3-sentence LSA extractive summary of the article |
| `pdf_links` | Pipe-separated list of PDF URLs found on the page |
| `error` | Any HTTP or network error encountered |

### `infosys_pdfs/`

Broker research notes and filings downloaded as PDFs. These come from MoneyControl's research section and BSE/NSE filings — typically analyst reports from firms like ICICI Securities, Emkay, Motilal Oswal, Anand Rathi, and Prabhudas Lalwai.

---

## Configuration

All settings are at the top of `infosys_scraper.py` under the `CONFIG` section:

```python
COMPANY_NAME  = "Infosys"   # change this to scrape any other company
MAX_RESULTS   = 8           # DuckDuckGo results per query
SUMMARY_LINES = 3           # sentences per article summary
REQUEST_DELAY = 1.5         # seconds between requests
PDF_FOLDER    = "infosys_pdfs"
CSV_OUTPUT    = "infosys_data.csv"
```

To scrape a different company, change `COMPANY_NAME` and update `SEARCH_QUERIES` accordingly.

---

## Filtering Logic

### Blocked domains (never scraped)
Social media, video platforms, and messaging apps are skipped entirely:
`youtube.com`, `twitter.com`, `x.com`, `t.me`, `reddit.com`, `facebook.com`, `instagram.com`, `google.com/finance`, `scribd.com`

### Trusted PDF domains (only these can serve PDFs)
To prevent downloading unrelated PDFs (e.g. NVIDIA reports from financial comparison sites):
`moneycontrol.com`, `bseindia.com`, `nseindia.com`, `infosys.com`, `sebi.gov.in`

### Quality checks (applied after scraping)
- **Minimum 50 words** of body text — filters out JS-rendered empty pages, login walls, and homepages
- **Must mention "Infosys"** — filters out irrelevant pages that happened to appear in results
- **PDF links must mention "Infosys"** in their URL or anchor text — prevents downloading generic legal/disclaimer PDFs

---

## Libraries Used

| Library | Purpose |
|---------|---------|
| `ddgs` | DuckDuckGo search — no API key needed |
| `requests` | HTTP requests to fetch pages and PDFs |
| `beautifulsoup4` | Parse HTML, extract text and links |
| `sumy` | Extractive text summarization using LSA algorithm |
| `lxml` | Fast HTML parser used by BeautifulSoup |
| `nltk` | Sentence tokenizer required by sumy |

---

## Known Limitations

- **JS-rendered pages** — Sites like Trendlyne, Groww, and Investing.com load content via JavaScript. `requests` fetches the raw HTML before JS runs, so these pages return 0 words and are skipped. A browser automation tool like Selenium would be needed to scrape them.
- **403 errors** — Infosys.com and Business Standard actively block scrapers. Their content is inaccessible without authentication or a headless browser.
- **DuckDuckGo variability** — Results differ between runs. The same query may return different URLs on different days.
- **Salary PDFs** — Annual reports hosted on NSE/BSE are very large. The summarizer caps input at 1000 words and has a 10-second timeout to avoid hanging.