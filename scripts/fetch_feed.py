"""Ambil data publik gratis -> data/feed.json (dibaca Macro Engine Desk).
Sumber: FRED (rilis pertama), CFTC (COT), yfinance (MOVE). Kunci: env FRED_API_KEY."""
import os, sys, json, datetime as dt, requests

KEY = os.environ.get("FRED_API_KEY")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "feed.json")
TODAY = dt.date.today()
log = []

def fred(series, **kw):
    p = dict(series_id=series, api_key=KEY, file_type="json", **kw)
    r = requests.get("https://api.stlouisfed.org/fred/series/observations", params=p, timeout=40)
    r.raise_for_status()
    out = []
    for o in r.json()["observations"]:
        try: out.append((o["date"], float(o["value"]), o.get("realtime_start")))
        except ValueError: pass          # nilai "." = kosong
    return out

# ind: (series, mode, skala, n_proxy, batas_wajar). mode: pct = m/m %, diff = selisih, lvl = level
IND = {
 "cpi_core": ("CPILFESL", "pct", 1, 3, 1.0), "cpi": ("CPIAUCSL", "pct", 1, 3, 1.5),
 "pce_core": ("PCEPILFE", "pct", 1, 3, 1.0), "ppi": ("PPIFIS", "pct", 1, 3, 3.0),
 "ahe": ("CES0500000003", "pct", 1, 3, 1.5), "nfp": ("PAYEMS", "diff", 1, 3, 1500),
 "unemp": ("UNRATE", "lvl", 1, 3, 15), "claims": ("ICSA", "lvl", 1e-3, 4, 1500),
 "jolts": ("JTSJOL", "lvl", 1e-3, 3, 20), "retail": ("RSAFS", "pct", 1, 3, 5.0),
 "ip": ("INDPRO", "pct", 1, 3, 3.0), "gdp": ("A191RL1Q225SBEA", "lvl", 1, 3, 15)}

def vintages(sid, start):
    """Semua versi nilai (ALFRED): obs -> [(rs, re, nilai)], untuk 'nilai yang diketahui pada hari D'."""
    p = dict(series_id=sid, api_key=KEY, file_type="json", observation_start=start,
             realtime_start="2000-01-01", realtime_end="9999-12-31", limit=100000)
    r = requests.get("https://api.stlouisfed.org/fred/series/observations", params=p, timeout=60)
    r.raise_for_status()
    out = {}
    for o in r.json()["observations"]:
        try: v = float(o["value"])
        except ValueError: continue
        out.setdefault(o["date"], []).append((o["realtime_start"], o["realtime_end"], v))
    return out

def known(vs, obs, day):
    for rs, re_, v in vs.get(obs, []):
        if rs <= day <= re_: return v
    return None

def consensus_file():
    f = os.path.join(os.path.dirname(__file__), "..", "data", "consensus.csv")
    m = {}
    if os.path.exists(f):
        for ln in open(f):
            c = [x.strip() for x in ln.split(",")]
            if len(c) >= 3 and c[0][:2] == "20":
                try: m[(c[0], c[1])] = float(c[2])
                except ValueError: pass
    return m

def releases():
    res = []; cfile = consensus_file()
    start = (TODAY - dt.timedelta(days=500)).isoformat()
    for ind, (sid, mode, sc, n, bound) in IND.items():
        try:
            vs = vintages(sid, start)
            obs = sorted(vs)
            rows = []; skipped = 0
            for i, d in enumerate(obs):
                if i == 0: continue
                R = min(x[0] for x in vs[d])            # tanggal rilis pertama
                v = known(vs, d, R); pd_ = obs[i - 1]
                prev = known(vs, pd_, R)                # nilai periode lalu yang diketahui saat rilis
                if v is None: continue
                if mode == "pct":
                    if not prev or (dt.date.fromisoformat(d) - dt.date.fromisoformat(pd_)).days > 100: continue
                    act = (v / prev - 1) * 100
                elif mode == "diff":
                    if prev is None: continue
                    act = v - prev
                else: act = v
                act = round(act * sc, 3)
                if abs(act) > bound: skipped += 1; continue   # tidak masuk akal -> buang
                rows.append((R, act, d))
            for i, (rs, act, od) in enumerate(rows):
                hist = [a for _, a, _ in rows[max(0, i - n):i]]
                cons = round(sum(hist) / len(hist), 3) if len(hist) >= 2 else None
                cons = cfile.get((rs, ind), cons)
                if (TODAY - dt.date.fromisoformat(rs)).days <= 150:
                    res.append(dict(date=rs, ind=ind, act=act, cons=cons, obs=od, src="file" if (rs, ind) in cfile else "proxy"))
            log.append(f"ok {ind}" + (f" (buang {skipped} nilai tak wajar)" if skipped else ""))
        except Exception as e:
            log.append(f"GAGAL {ind}: {e}")
    return res

def last(series, **kw):
    s = fred(series, observation_start=(TODAY - dt.timedelta(days=120)).isoformat(), **kw)
    return s

def market():
    shock, liq, cb = {}, {}, {}
    try:
        vix = last("VIXCLS"); shock["vix"] = vix[-1][1]
        v3 = last("VXVCLS"); shock["vix3m"] = v3[-1][1]
        hy = last("BAMLH0A0HYM2"); shock["hy"] = hy[-1][1]
        shock["hyp"] = hy[-21][1] if len(hy) > 21 else None
    except Exception as e: log.append(f"GAGAL shock: {e}")
    try:
        import yfinance as yf
        h = yf.Ticker("^MOVE").history(period="5d")["Close"].dropna()
        shock["move"] = round(float(h.iloc[-1]), 1)
    except Exception as e: log.append(f"MOVE tidak tersedia (isi manual): {e}")
    try:
        w = last("WALCL"); t = last("WTREGEN"); r = last("RRPONTSYD")
        liq = dict(w0=w[-1][1] / 1e3, t0=t[-1][1] / 1e3, r0=r[-1][1],
                   w1=w[-5][1] / 1e3, t1=t[-5][1] / 1e3, r1=r[-21][1] if len(r) > 21 else None)
        liq = {k: (round(v, 1) if v is not None else None) for k, v in liq.items()}
    except Exception as e: log.append(f"GAGAL likuiditas: {e}")
    try:
        cb["FED"] = {"rate": last("DFEDTARU")[-1][1]}
        cb["ECB"] = {"rate": last("ECBDFR")[-1][1]}
    except Exception as e: log.append(f"GAGAL bank sentral: {e}")
    return shock, liq, cb

COT = {"GOLD": "088691", "CRUDE": "067651", "COPPER": "085692", "EUR": "099741",
       "GBP": "096742", "JPY": "097741", "AUD": "232741", "SPX": "13874A",
       "NDX": "209742", "BTC": "133741"}

def cot():
    out = {}
    for k, code in COT.items():
        try:
            r = requests.get("https://publicreporting.cftc.gov/resource/6dca-aqww.json", timeout=40,
                params={"cftc_contract_market_code": code, "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": 160})
            r.raise_for_status()
            rows = [dict(d=x["report_date_as_yyyy_mm_dd"][:10],
                         net=int(float(x["noncomm_positions_long_all"])) - int(float(x["noncomm_positions_short_all"])),
                         oi=int(float(x["open_interest_all"]))) for x in r.json()]
            out[k] = rows
        except Exception as e: log.append(f"GAGAL COT {k}: {e}")
    return out

if __name__ == "__main__":
    if not KEY: sys.exit("FRED_API_KEY belum diset (GitHub: Settings > Secrets > Actions)")
    rel = releases(); shock, liq, cb = market(); c = cot()
    feed = dict(generated=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                consensus="proxy", releases=rel, shock=shock, liq=liq, cb=cb, cot=c, log=log)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(feed, open(OUT, "w"), indent=1)
    print("\n".join(log)); print(f"releases={len(rel)} cot={len(c)} shock={shock}")
    if len(rel) == 0 and not c: sys.exit("Tidak ada data sama sekali: cek API key / jaringan")
