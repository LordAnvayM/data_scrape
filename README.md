# Infosys Company Scraper

A Python web scraper that collects financial data about **Infosys** from MoneyControl and other trusted finance websites using DuckDuckGo search.

---

## What it does

- Searches DuckDuckGo with 5 focused queries targeting different types of Infosys data
- Scrapes article headlines, body text, and summaries from the results
- Downloads any PDF reports (analyst reports, filings) found on those pages
- Filters out junk pages (social media, videos, pages with no Infosys content)
- Saves everything to a structured CSV file

---

## Project structure

```
project/
│
├── infosys_scraper.py     ← main script
├── requirements.txt       ← dependencies
├── README.md              ← this file
│
├── infosys_data.csv       ← generated after running (scraped articles)
└── infosys_pdfs/          ← generated after running (downloaded PDFs)
```

---

## Setup

**1. Clone or download the project**

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the scraper**
```bash
python infosys_scraper.py
```

NLTK tokenizer data is downloaded automatically on the first run.

---

## Output

### `infosys_data.csv`
Each row is one scraped article with these columns:

| Column | Description |
|--------|-------------|
| `data_type` | Category of the article (`news`, `quarterly_results`, `annual_report`, `share_price`, `analyst_forecast`) |
| `title` | Title from DuckDuckGo search result |
| `url` | Full URL of the page |
| `snippet` | Short preview text from DuckDuckGo |
| `headline` | H1 headline scraped from the page |
| `summary` | 3-sentence LSA summary of the article body |
| `pdf_links` | Pipe-separated list of PDF URLs found on the page |
| `error` | Any HTTP or network error encountered |

### `infosys_pdfs/`
Analyst reports, broker notes, and filings downloaded as PDF files.

---

## How it works

```
DuckDuckGo search (5 queries)
        ↓
Filter out junk URLs (YouTube, Twitter, Facebook etc.)
        ↓
Scrape HTML (headline + body text)
        ↓
Quality check (min 50 words + must mention Infosys)
        ↓
Summarize with LSA algorithm (sumy)
        ↓
Download PDFs found on page
        ↓
Save all data to CSV
```

---

## Configuration

All settings are at the top of `infosys_scraper.py`:

```python
COMPANY_NAME  = "Infosys"   # change to scrape a different company
MAX_RESULTS   = 8           # DuckDuckGo results per query
SUMMARY_LINES = 3           # sentences in each summary
REQUEST_DELAY = 1.5         # seconds between requests (be polite!)
```

To scrape a different company, just change `COMPANY_NAME` and update the `SEARCH_QUERIES` list.

---

## Libraries used

| Library | Purpose |
|---------|---------|
| `ddgs` | DuckDuckGo search (no API key needed) |
| `requests` | HTTP requests to fetch pages and PDFs |
| `beautifulsoup4` | Parse HTML and extract text |
| `sumy` | Extractive text summarization (LSA algorithm) |
| `lxml` | HTML parser used by BeautifulSoup |
| `nltk` | Tokenizer required by sumy |

---

## Known limitations

- Some sites (Infosys.com, Business Standard) return `403 Forbidden` and cannot be scraped
- DuckDuckGo results vary — not every run will return the same URLs
- PDFs behind login walls will fail to download
- Summaries work best on long-form articles; short pages may return minimal summaries"# data_scrape" 
