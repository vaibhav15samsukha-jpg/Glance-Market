#!/usr/bin/env python3
"""Glace Market data pipeline.
Builds the ./site folder: the web page + JSON data for every stock + IPO list.
Env vars:  SCOPE=nifty500 (default) | all     LIMIT=N (test with few stocks)
"""
import io, json, math, os, re, shutil, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import yfinance as yf

SCOPE = os.getenv("SCOPE", "nifty500").lower()
LIMIT = int(os.getenv("LIMIT", "0") or 0)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DATA = os.path.join(SITE, "data")
STK = os.path.join(DATA, "stocks")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
CR = 1e7  # 1 crore


def safe(s):
    return re.sub(r"[^A-Za-z0-9_-]", "_", s)


def num(x, nd=2):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, nd)
    except (TypeError, ValueError):
        return None


def cr(x):
    return None if x is None else round(x / CR, 0)


def fetch(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def now_ist():
    return (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).strftime("%d %b %Y, %H:%M IST")


# ---------------------------------------------------------------- universe
def universe():
    names, fv = {}, {}
    try:
        eq = pd.read_csv(io.StringIO(fetch("https://archives.nseindia.com/content/equities/EQUITY_L.csv")))
        eq.columns = [c.strip() for c in eq.columns]
        eq = eq[eq["SERIES"].str.strip() == "EQ"]
        names = dict(zip(eq["SYMBOL"], eq["NAME OF COMPANY"]))
        fv = {r["SYMBOL"]: num(r.get("FACE VALUE")) for _, r in eq.iterrows()}
    except Exception as e:
        print("EQUITY_L.csv failed:", e)
        if SCOPE == "all":
            raise
    if SCOPE == "all":
        return list(names), names, fv, {}
    n5 = pd.read_csv(io.StringIO(fetch("https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv")))
    names.update(dict(zip(n5["Symbol"], n5["Company Name"])))
    return list(n5["Symbol"]), names, fv, dict(zip(n5["Symbol"], n5["Industry"]))


# ---------------------------------------------------------------- prices
def download(tickers, **kw):
    out = {}
    for i in range(0, len(tickers), 50):
        chunk, df = tickers[i:i + 50], None
        for _ in range(3):
            try:
                df = yf.download(chunk, group_by="ticker", threads=True, progress=False, auto_adjust=True, **kw)
                break
            except Exception as e:
                print("download retry:", e)
                time.sleep(5)
        if df is None or df.empty:
            continue
        for t in chunk:
            try:
                sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
                sub = sub.dropna(how="all")
                if not sub.empty:
                    out[t] = sub
            except KeyError:
                pass
        print(f"  downloaded {min(i + 50, len(tickers))}/{len(tickers)}")
    return out


def to_candles(df, intraday):
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = df.index
    if getattr(idx, "tz", None) is not None and not intraday:
        idx = idx.tz_localize(None)  # keep local date, treat as UTC midnight
    return [[int(ts.timestamp()), round(float(o), 2), round(float(h), 2), round(float(l), 2), round(float(c), 2)]
            for ts, (o, h, l, c) in zip(idx, df[["Open", "High", "Low", "Close"]].values)]


# ---------------------------------------------------------------- fundamentals
def pick(df, names, col):
    if df is None:
        return None
    for n in names:
        if n in df.index:
            v = df.at[n, col]
            if isinstance(v, pd.Series):
                v = v.iloc[0]
            v = num(v, 4)
            if v is not None:
                return v
    return None


def income(df, n):
    if df is None or df.empty:
        return None
    cols = sorted(df.columns)[-n:]
    rows = {k: [] for k in ["Sales", "Expenses", "Operating Profit", "OPM %", "Net Profit", "EPS (₹)"]}
    for c in cols:
        s = pick(df, ["Total Revenue", "Operating Revenue"], c)
        op = pick(df, ["Operating Income", "EBIT"], c)
        rows["Sales"].append(cr(s))
        rows["Expenses"].append(cr(s - op) if s is not None and op is not None else None)
        rows["Operating Profit"].append(cr(op))
        rows["OPM %"].append(round(op / s * 100, 1) if s and op is not None else None)
        rows["Net Profit"].append(cr(pick(df, ["Net Income", "Net Income Common Stockholders"], c)))
        rows["EPS (₹)"].append(pick(df, ["Diluted EPS", "Basic EPS"], c))
    return {"cols": [c.strftime("%b %Y") for c in cols], "rows": [[k, v] for k, v in rows.items()]}


def balance(df, n=5):
    if df is None or df.empty:
        return None
    cols = sorted(df.columns)[-n:]
    rows = {k: [] for k in ["Share Capital", "Reserves", "Borrowings", "Total Liabilities",
                            "Current Assets", "Cash", "Total Assets"]}
    for c in cols:
        cap = pick(df, ["Capital Stock", "Common Stock"], c)
        eq = pick(df, ["Stockholders Equity", "Common Stock Equity"], c)
        rows["Share Capital"].append(cr(cap))
        rows["Reserves"].append(cr(eq - cap) if eq is not None and cap is not None else None)
        rows["Borrowings"].append(cr(pick(df, ["Total Debt"], c)))
        rows["Total Liabilities"].append(cr(pick(df, ["Total Liabilities Net Minority Interest"], c)))
        rows["Current Assets"].append(cr(pick(df, ["Current Assets"], c)))
        rows["Cash"].append(cr(pick(df, ["Cash And Cash Equivalents"], c)))
        rows["Total Assets"].append(cr(pick(df, ["Total Assets"], c)))
    return {"cols": [c.strftime("%b %Y") for c in cols], "rows": [[k, v] for k, v in rows.items()]}


def attr(tk, name):
    try:
        v = getattr(tk, name)
        return v if v is not None and not v.empty else None
    except Exception:
        return None


def build(sym, last, name, fv, industry):
    tk = yf.Ticker(sym + ".NS")
    info = {}
    for a in range(3):
        try:
            info = tk.info or {}
            break
        except Exception:
            time.sleep(2 * (a + 1))
    qi, ai, bs = attr(tk, "quarterly_income_stmt"), attr(tk, "income_stmt"), attr(tk, "balance_sheet")
    price = num(info.get("currentPrice")) or last
    rate = num(info.get("dividendRate"))
    # ROCE = EBIT / (Total assets - Current liabilities), latest annual year
    roce = None
    if ai is not None and bs is not None:
        ebit = pick(ai, ["EBIT", "Operating Income"], sorted(ai.columns)[-1])
        ta = pick(bs, ["Total Assets"], sorted(bs.columns)[-1])
        cl = pick(bs, ["Current Liabilities"], sorted(bs.columns)[-1])
        if ebit is not None and ta and cl is not None and ta - cl > 0:
            roce = round(ebit / (ta - cl) * 100, 1)
    res = None
    if bs is not None:
        c = sorted(bs.columns)[-1]
        eq, cap = pick(bs, ["Stockholders Equity", "Common Stock Equity"], c), pick(bs, ["Capital Stock", "Common Stock"], c)
        res = cr(eq - cap) if eq is not None and cap is not None else None
    roe = num(info.get("returnOnEquity"))
    pat = num(info.get("netIncomeToCommon"))
    rev = num(info.get("totalRevenue"))
    sh = None
    mh = attr(tk, "major_holders")
    if mh is not None:
        try:
            v = mh["Value"] if "Value" in mh else mh.iloc[:, 0]
            ins, inst = num(v.get("insidersPercentHeld"), 4), num(v.get("institutionsPercentHeld"), 4)
            if ins is not None and inst is not None:
                sh = {"cols": ["Latest"], "rows": [["Promoters & insiders", [round(ins * 100, 1)]],
                                                   ["Institutions (FII + DII)", [round(inst * 100, 1)]],
                                                   ["Public & others", [round(max(0, 100 - (ins + inst) * 100), 1)]]]}
        except Exception:
            pass
    desc = (info.get("longBusinessSummary") or "").strip()
    desc = ". ".join(desc.split(". ")[:3]).strip()
    if desc and not desc.endswith("."):
        desc += "."
    return {
        "sym": sym, "name": info.get("longName") or name, "sector": info.get("sector") or "",
        "industry": industry or info.get("industry") or info.get("sector") or "Other", "desc": desc,
        "m": {"price": price, "hi": num(info.get("fiftyTwoWeekHigh")), "lo": num(info.get("fiftyTwoWeekLow")),
              "mcap": cr(num(info.get("marketCap"), 0)), "pe": num(info.get("trailingPE"), 1),
              "bv": num(info.get("bookValue")),
              "dy": round(rate / price * 100, 2) if rate and price else None,
              "roce": roce, "roe": round(roe * 100, 1) if roe is not None else None, "fv": fv,
              "pat": cr(pat), "rev": cr(rev), "res": res},
        "q": income(qi, 8), "p": income(ai, 5), "b": balance(bs), "sh": sh,
    }


# ---------------------------------------------------------------- IPOs
def ipos():
    items, gmp = [], {}
    try:
        with open(os.path.join(ROOT, "config", "gmp.json"), encoding="utf-8") as f:
            gmp = {k.lower(): v for k, v in json.load(f).items()}
    except Exception as e:
        print("gmp.json not read:", e)
    try:
        s = requests.Session()
        s.headers.update(UA)
        s.get("https://www.nseindia.com", timeout=20)
        data = s.get("https://www.nseindia.com/api/ipo-current-issue", timeout=30).json()
        if isinstance(data, dict):
            data = data.get("data") or []
        for d in data:
            name = d.get("companyName") or d.get("symbol") or "IPO"
            band = str(d.get("issuePrice") or d.get("priceBand") or "")
            nums = re.findall(r"\d+(?:\.\d+)?", band)
            upper = float(nums[-1]) if nums else None
            g = gmp.get(name.lower()) if name.lower() in gmp else gmp.get(str(d.get("symbol", "")).lower())
            items.append({"name": name, "band": band, "open": d.get("issueStartDate"), "close": d.get("issueEndDate"),
                          "status": d.get("status"), "sub": d.get("noOfTimeSubscribed"), "gmp": g,
                          "listing": upper + g if upper is not None and g is not None else None,
                          "gain": round(g / upper * 100, 1) if upper and g is not None else None})
    except Exception as e:
        print("IPO fetch failed:", e)
    return {"u": now_ist(), "items": items}


# ---------------------------------------------------------------- main
def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(STK)
    shutil.copy(os.path.join(ROOT, "web", "index.html"), os.path.join(SITE, "index.html"))
    open(os.path.join(SITE, ".nojekyll"), "w").close()

    syms, names, fv, ind = universe()
    if LIMIT:
        syms = syms[:LIMIT]
    print(f"Scope={SCOPE}: {len(syms)} symbols")
    daily = download([s + ".NS" for s in syms], period="7y", interval="1d")
    intra = download(list(daily), period="5d", interval="15m")

    def work(sym):
        t = sym + ".NS"
        if t not in daily:
            return None
        d = to_candles(daily[t], False)
        if len(d) < 5:
            return None
        try:
            rec = build(sym, d[-1][4], names.get(sym, sym), fv.get(sym), ind.get(sym))
        except Exception as e:
            print("skip", sym, e)
            return None
        rec["d"] = d
        rec["i"] = to_candles(intra[t], True) if t in intra else []
        return rec

    summ, index = {}, []
    with ThreadPoolExecutor(6) as ex:
        for rec in ex.map(work, syms):
            if not rec:
                continue
            with open(os.path.join(STK, safe(rec["sym"]) + ".json"), "w", encoding="utf-8") as f:
                json.dump(rec, f, separators=(",", ":"))
            m = rec["m"]
            summ[rec["sym"]] = [rec["sym"], rec["name"], m["price"], m["pe"], m["mcap"], m["dy"], m["roce"], m["roe"]]
            index.append([rec["sym"], rec["name"]])
            summ[rec["sym"]].append(rec["industry"])
    print("built", len(index), "stocks")

    # peers: same industry, closest market cap
    groups = {}
    for s in summ.values():
        groups.setdefault(s[8], []).append(s)
    for sym, s in summ.items():
        others = sorted((o for o in groups[s[8]] if o[0] != sym), key=lambda o: abs((o[4] or 0) - (s[4] or 0)))[:5]
        p = os.path.join(STK, safe(sym) + ".json")
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
        rec["peers"] = [x[:8] for x in [s] + others]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rec, f, separators=(",", ":"))

    index.sort(key=lambda x: x[1])
    with open(os.path.join(DATA, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"u": now_ist(), "s": index}, f, separators=(",", ":"))
    with open(os.path.join(DATA, "ipo.json"), "w", encoding="utf-8") as f:
        json.dump(ipos(), f)
    print("done")


if __name__ == "__main__":
    main()
