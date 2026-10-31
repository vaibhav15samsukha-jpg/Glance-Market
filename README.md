Glace Market

A free stock research website for NSE-listed companies. Search a company and see its key ratios, price chart, peers, financial statements and shareholding, with a link out to Screener.in for more detail.

Live site: https://vaibhav15samsukha-jpg.github.io/Glance-Market/

Educational project. Not investment advice. Data comes from free sources and may be delayed, incomplete or occasionally wrong. Always verify against company filings.

Features
Search any covered company by name or symbol
Key figures: market cap, price, 52-week high/low, P/E, book value, dividend yield, ROCE, ROE, face value, profit after tax, revenue, reserves
Candlestick chart with 1D, 5D, 1M, 6M, 1Y, 3Y, 5Y and 7Y views
Peer comparison against companies in the same industry
Quarterly results, Profit & Loss, Balance Sheet and a simple shareholding split
Live IPO page showing current NSE issues, with an optional grey market premium (GMP) that you enter by hand
Light and dark mode, works on mobile
How it works
NSE company lists + Yahoo Finance
            |
   Python script (scripts/update.py)
            |
   JSON files, one per company
            |
   GitHub Actions (runs on weekdays)
            |
   GitHub Pages (static website)
scripts/update.py downloads the list of listed companies from NSE, then price history and company data through the yfinance library.
It calculates some figures itself where the source does not provide them, for example ROCE = EBIT / (total assets - current liabilities), dividend yield and P/E from earnings per share.
It writes one JSON file per company, plus a search index and an IPO file.
A GitHub Actions workflow (.github/workflows/update.yml) runs the script twice on weekdays and publishes the result to GitHub Pages.
The website (web/index.html) is a single static page that reads those JSON files in the browser. There is no server or database.
Tech stack

Python (pandas, requests, yfinance), JavaScript with an HTML canvas for the candlestick charts, GitHub Actions, GitHub Pages.

Data sources and limitations
Prices and financials: Yahoo Finance via yfinance (unofficial, free). Updated about twice a day, so this is not real-time data.
Company lists and face value: NSE and Nifty Indices files.
Shareholding is simplified to three groups (promoters and insiders, institutions, public). It is not the full quarterly pattern.
Coverage gaps: Yahoo has little data for some small or recently listed companies, so their financial tables can be empty. Use the Screener.in button on each page for those.
IPO premium (GMP) is unofficial grey-market data. It is not fetched automatically. Edit config/gmp.json to show it.
Some figures (ROCE, P/E, book value) are calculated from statements when the source does not give them, so they can differ slightly from Screener.in.
Run it yourself
bash
pip install -r requirements.txt
LIMIT=10 python scripts/update.py      # builds ./site with 10 companies for a quick test

Set SCOPE=all to cover every NSE-listed company (slow), or leave the default nifty500.

To deploy: fork the repo, go to Settings, then Pages, set Source to GitHub Actions, and run the "Update Glace Market" workflow once from the Actions tab.

Project structure
web/index.html               the website
scripts/update.py            data pipeline
config/gmp.json              manual IPO premium entries
.github/workflows/update.yml scheduled build and deploy
About

Built by Vaibhav Samsukha, CA Finalist, as a hands-on project in financial data and equity research. The code was developed with AI assistance (Claude); I designed the features and data coverage, set up the deployment, tested the output and understand how each part works.

Content

PDF

repo click Add file

You use it for real analysis. An equity research report on one company, using the site’s numbers, shows the skill the role actually needs. The site becomes a tool for it, not the whole story.
