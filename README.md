# Glace Market
Free stock research site (NSE). Data pipeline (Python + yfinance + NSE files) -> GitHub Actions -> GitHub Pages.

## Setup
1. Create a PUBLIC GitHub repo, upload all these files (keep the folder structure, incl. .github/).
2. Settings -> Pages -> Source: "GitHub Actions".
3. Actions tab -> "Update Glace Market" -> Run workflow. Wait for the green tick.
4. Your site: https://YOUR-USERNAME.github.io/YOUR-REPO/

Updates run automatically on weekdays at 12:30 PM and 5:00 PM IST.
IPO premium (GMP) is unofficial: edit config/gmp.json (name -> premium in rupees).
Local test: pip install -r requirements.txt && LIMIT=10 python scripts/update.py
