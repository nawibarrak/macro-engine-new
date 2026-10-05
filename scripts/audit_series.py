"""Audit data v2 (tahap 2b): memeriksa seri yang SUDAH tersimpan, bukan sekadar mengulang pengambilan.
Tiga jenis pemeriksaan, semuanya tampil di beranda (data/audit_series.json):
 1. SILANG-SUMBER: besaran yang sama dari dua sumber independen (FRED vs Yahoo, FRED vs BLS) harus cocok dalam toleransi.
 2. KONSISTENSI: hubungan yang harus berlaku antar seri (10Y-2Y = kurva, nominal-breakeven = riil, korelasi DXY-EURUSD, dst).
 3. KEBEKUAN/CADANGAN: harga yang 'macet' (nilai sama berhari-hari) dan seri yang jatuh ke sumber cadangan.
Hasil: pass / warn / fail / na. FAIL pada seri kunci menutup gerbang. 'na' = tidak bisa diperiksa (bukan lolos).
Toleransi adalah perkiraan awal (lihat docs/PROGRESS.md); ubah di tabel CROSS/BLS di bawah, bukan di logika."""
import os, sys, json, math, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_layer as DL
from registry import REGISTRY, BY_ID

OUT = os.path.join(DL.ROOT, "audit_series.json")
NOW = DL.NOW
checks = []
FRED_URL = "https://fred.stlouisfed.org/series/"
YF_URL = "https://finance.yahoo.com/quote/"
BLS_URL = "https://data.bls.gov/timeseries/"

def add(kind, name, series, status, detail, tol=None, links=None):
    checks.append(dict(kind=kind, name=name, series=series, status=status, detail=detail, tol=tol, links=links or []))

def link(prov, ref):
    return (FRED_URL if prov == "fred" else YF_URL if prov == "yf" else BLS_URL) + ref

# ---------- 1. silang-sumber ----------
# (id seri, nama, sumber kiri, sumber kanan, mode, toleransi)  mode: pct = selisih persen, abs = selisih absolut
CROSS = [
 ("SPX", "S&P 500: FRED vs Yahoo", ("fred", "SP500"), ("yf", "^GSPC"), "pct", 0.5),
 ("NDX", "Nasdaq 100: Yahoo vs FRED", ("yf", "^NDX"), ("fred", "NASDAQ100"), "pct", 0.5),
 ("US10Y", "Yield 10 tahun: FRED vs Yahoo", ("fred", "DGS10"), ("yf", "^TNX"), "abs", 0.08),
 ("VIX", "VIX: FRED vs Yahoo", ("fred", "VIXCLS"), ("yf", "^VIX"), "pct", 3.0),
 ("WTI", "WTI: FRED (spot) vs Yahoo (futures)", ("fred", "DCOILWTICO"), ("yf", "CL=F"), "pct", 3.0),
 ("USDJPY", "USD/JPY: Yahoo vs FRED", ("yf", "JPY=X"), ("fred", "DEXJPUS"), "pct", 0.8),
 ("EURUSD", "EUR/USD: Yahoo vs FRED", ("yf", "EURUSD=X"), ("fred", "DEXUSEU"), "pct", 0.8),
 ("BTC", "Bitcoin: Yahoo vs FRED (Coinbase)", ("yf", "BTC-USD"), ("fred", "CBBTCUSD"), "pct", 2.0)]
# BLS (sumber resmi) vs FRED untuk periode terbaru yang sama. mode abs/pct, toleransi
BLS = [("CPI", "CUSR0000SA0", "pct", 0.06), ("CPICORE", "CUSR0000SA0L1E", "pct", 0.06),
       ("NFP", "CES0000000001", "abs", 1.0), ("UNEMP", "LNS14000000", "abs", 0.05), ("AHE", "CES0500000003", "abs", 0.03)]

def p_bls(sid):
    import requests
    y = NOW().year
    r = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", timeout=40,
                      json={"seriesid": [sid], "startyear": str(y - 1), "endyear": str(y)})
    r.raise_for_status()
    out = []
    for x in r.json()["Results"]["series"][0]["data"]:
        if x["period"].startswith("M") and x["period"] != "M13":
            try: out.append([f"{x['year']}-{x['period'][1:]}-01", float(x["value"])])
            except ValueError: pass          # BLS menulis '-' untuk bulan tanpa data
    return sorted(out)

def fetch(src, days=60):
    start = (NOW().date() - dt.timedelta(days=days)).isoformat()
    pts, _ = DL.clean(DL.PROVIDERS[src[0]](src[1], start), dict(lo=None, hi=None))
    return dict((d, v) for d, v in pts)

def dev(a, b, mode):
    return (a / b - 1) * 100 if mode == "pct" else a - b

def run_cross():
    for sid, name, L, R, mode, tol in CROSS:
        links = [link(*L), link(*R)]
        try:
            a, b = fetch(L), fetch(R)
        except Exception as e:
            add("silang", name, [sid], "na", f"tidak bisa diambil: {type(e).__name__}: {str(e)[:90]}", tol, links); continue
        common = sorted(set(a) & set(b))
        if not common or (NOW().date() - dt.date.fromisoformat(common[-1])).days > 14:
            add("silang", name, [sid], "na", "tidak ada tanggal bersama dalam 14 hari terakhir", tol, links); continue
        ds = [dev(a[d], b[d], mode) for d in common[-10:] if b[d]]
        lastd = ds[-1]; med = sorted(abs(x) for x in ds)[len(ds) // 2]
        unit = "%" if mode == "pct" else " poin"
        st = "fail" if abs(lastd) > tol else "warn" if (abs(lastd) > tol / 2 or med > tol / 2) else "pass"
        add("silang", name, [sid], st,
            f"{common[-1]}: {L[1]}={a[common[-1]]:.4g} vs {R[1]}={b[common[-1]]:.4g}, selisih {lastd:+.3f}{unit} (toleransi {tol}{unit}; median 10 hari {med:.3f}). Selisih per tanggal: " + ", ".join(f"{d[5:]} {x:+.2f}" for d, x in zip(common[-10:], ds)), tol, links)

def run_bls():
    for sid, bid, mode, tol in BLS:
        name = f"{BY_ID[sid]['label']}: FRED vs BLS"; links = [link("fred", BY_ID[sid]["prov"][0][1]), link("bls", bid)]
        d = DL.load(sid)
        if not d or not d.get("points"):
            add("silang", name, [sid], "na", "seri belum tersimpan", tol, links); continue
        try: bl = dict(p_bls(bid))
        except Exception as e:
            add("silang", name, [sid], "na", f"BLS tidak terjangkau: {type(e).__name__}: {str(e)[:80]}", tol, links); continue
        mine = dict((x[0], x[1]) for x in d["points"])
        common = sorted(set(mine) & set(bl))
        if not common:
            add("silang", name, [sid], "na", "belum ada periode bersama (BLS belum memuat periode terbaru FRED?)", tol, links); continue
        k = common[-1]; df = dev(mine[k], bl[k], mode)
        st = "fail" if abs(df) > tol else "pass"
        add("silang", name, [sid], st, f"periode {k[:7]}: FRED {mine[k]:.4g} vs BLS {bl[k]:.4g}, selisih {df:+.4f} (toleransi {tol})", tol, links)

# ---------- 2. konsistensi internal ----------
def ser(sid):
    d = DL.load(sid)
    return dict((x[0], x[1]) for x in d["points"]) if d and d.get("points") else {}

def corr(x, y):
    n = len(x)
    if n < 20: return None
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x)); sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return None if not sx or not sy else sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)

def rets(a, b, step=1, n=90):
    ds = sorted(set(a) & set(b))[-(n + step):]
    ra, rb = [], []
    for i in range(step, len(ds)):
        if a[ds[i - step]] and b[ds[i - step]]:
            ra.append(a[ds[i]] / a[ds[i - step]] - 1); rb.append(b[ds[i]] / b[ds[i - step]] - 1)
    return ra, rb

def run_consistency():
    # identitas aritmetik pada tanggal terbaru yang dimiliki ketiganya
    for name, out, f, parts, tol in [("Kurva = 10 tahun − 2 tahun", "CURVE", lambda a, b: a - b, ("US10Y", "US02Y"), 0.06),
                                     ("Yield riil ≈ nominal 10 tahun − breakeven", "REAL10Y", lambda a, b: a - b, ("US10Y", "BE10Y"), 0.25)]:
        o, x, y = ser(out), ser(parts[0]), ser(parts[1]); common = sorted(set(o) & set(x) & set(y))
        if not common: add("konsistensi", name, [out, *parts], "na", "tidak ada tanggal bersama", tol); continue
        d = common[-1]; exp = f(x[d], y[d]); df = o[d] - exp
        add("konsistensi", name, [out, *parts], "fail" if abs(df) > tol else "pass",
            f"{d}: {out}={o[d]:.3f}, hitung ulang={exp:.3f}, selisih {df:+.3f} (toleransi {tol})", tol)
    # korelasi yang secara struktural harus berlaku
    for name, a, b, step, cond, warn_at, fail_at in [
            ("Korelasi DXY dan EUR/USD harus negatif (90 hari)", "DXY", "EURUSD", 1, "neg", -0.3, 0.0),
            ("Korelasi S&P 500 dan SPY harus sangat positif", "SPX", "SPY", 1, "pos", 0.9, 0.5),
            ("Korelasi emas futures dan GLD harus sangat positif", "XAUUSD", "GLD", 1, "pos", 0.9, 0.5),
            ("Selisih kredit HY naik ketika HYG turun (perubahan 5 hari, negatif)", "HYOAS", "HYG", 5, "neg", -0.2, 0.2)]:
        x, y = ser(a), ser(b)
        ra, rb = rets(x, y, step)
        c = corr(ra, rb) if ra else None
        if c is None: add("konsistensi", name, [a, b], "na", "data belum cukup (butuh ≥20 pengamatan bersama)"); continue
        def grade(c):
            if cond == "neg": return "fail" if c > fail_at else "warn" if c > warn_at else "pass"
            return "fail" if c < fail_at else "warn" if c < warn_at else "pass"
        st = grade(c); extra = ""
        if step == 1 and st != "pass":
            r5a, r5b = rets(x, y, 5); c5 = corr(r5a, r5b) if r5a else None
            if c5 is not None:
                extra = f"; korelasi perubahan 5 hari {c5:+.2f}"
                if st == "warn" and grade(c5) == "pass":
                    st = "pass"; extra += " (lolos: selisih jam penutupan antar-pasar melemahkan korelasi harian, bukan data rusak)"
        add("konsistensi", name, [a, b], st, f"korelasi harian {c:+.2f} dari {len(ra)} pengamatan{extra}")
    # rasio yang seharusnya stabil: emas/GLD, SPX/SPY
    for name, a, b in [("Rasio emas futures terhadap GLD stabil", "XAUUSD", "GLD"), ("Rasio S&P 500 terhadap SPY stabil", "SPX", "SPY")]:
        x, y = ser(a), ser(b); common = sorted(set(x) & set(y))[-60:]
        if len(common) < 20: add("konsistensi", name, [a, b], "na", "data belum cukup"); continue
        r = [x[d] / y[d] for d in common if y[d]]; med = sorted(r)[len(r) // 2]; dv = (r[-1] / med - 1) * 100
        add("konsistensi", name, [a, b], "fail" if abs(dv) > 4 else "warn" if abs(dv) > 1.5 else "pass",
            f"rasio terbaru {r[-1]:.3f} vs median 60 hari {med:.3f}, simpangan {dv:+.2f}% (peringatan >1,5%, gagal >4%)")
    # likuiditas bersih masuk akal (miliar USD)
    w, t, r_ = ser("WALCL"), ser("TGA"), ser("RRP"); cm = sorted(set(w) & set(t))
    if cm and r_:
        d = cm[-1]; rr = r_[max(k for k in r_ if k <= d)] if any(k <= d for k in r_) else 0
        net = w[d] / 1e3 - t[d] / 1e3 - rr
        add("konsistensi", "Likuiditas bersih Fed dalam rentang wajar (3.000–10.000 miliar USD)", ["WALCL", "TGA", "RRP"],
            "pass" if 3000 <= net <= 10000 else "warn", f"{d}: {net:,.0f} miliar USD")

# ---------- 3. kebekuan dan sumber cadangan ----------
STUCK = ["XAUUSD", "SPX", "NDX", "USDJPY", "EURUSD", "DXY", "COPPER", "BTC", "VIX", "WTI", "US02Y", "US10Y", "HYOAS", "IHSG", "USDIDR", "NIKKEI"]
def run_health():
    for sid in STUCK:
        d = DL.load(sid)
        if not d or len(d.get("points", [])) < 6: continue
        v = [p[1] for p in d["points"][-5:]]
        add("beku", f"{BY_ID[sid]['label']}: tidak macet", [sid], "fail" if len(set(v)) == 1 else "pass",
            "5 nilai terakhir identik, kemungkinan sumber macet" if len(set(v)) == 1 else f"5 nilai terakhir bervariasi ({min(v):.4g} sampai {max(v):.4g})")
    for s in REGISTRY:
        d = DL.load(s["id"])
        if d and d.get("fallback"):
            add("cadangan", f"{s['label']}: memakai sumber cadangan", [s["id"]], "warn",
                f"sumber utama {s['prov'][0][1]} tidak segar atau gagal; kini {d.get('prov')}:{d.get('ref')}")

def summarize():
    cnt = {k: sum(c["status"] == k for c in checks) for k in ("pass", "warn", "fail", "na")}
    crit = [s["id"] for s in REGISTRY if s["crit"]]
    trust = {}
    for s in REGISTRY:
        mine = [c for c in checks if s["id"] in c["series"] and c["kind"] in ("silang", "beku", "konsistensi")]
        cross_ok = any(c["kind"] == "silang" and c["status"] == "pass" for c in mine if c["series"][0] == s["id"])
        if any(c["status"] == "fail" for c in mine): lv = "bermasalah"
        elif cross_ok: lv = "terverifikasi"
        elif any(c["status"] == "pass" for c in mine): lv = "konsisten"
        else: lv = "sumber tunggal"
        trust[s["id"]] = lv
    blocked = [i for i in crit if trust[i] == "bermasalah"]
    unver = [i for i in crit if trust[i] in ("sumber tunggal", "konsisten")]
    return dict(generated=NOW().isoformat(timespec="seconds"), counts=cnt, trust=trust,
                gate=dict(open=not blocked, blocked_by=blocked, unverified_crit=unver), checks=checks)

def main():
    for f in (run_cross, run_bls, run_consistency, run_health):
        try: f()
        except Exception as e: add("sistem", f"{f.__name__} error", [], "warn", f"{type(e).__name__}: {str(e)[:120]}")
    res = summarize()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(f"audit: {res['counts']} gerbang={'TERBUKA' if res['gate']['open'] else 'TERTUTUP ' + ','.join(res['gate']['blocked_by'])}")
    for c in checks:
        if c["status"] in ("fail", "warn"): print(f"  {c['status']:5} {c['name']}: {c['detail']}")

if __name__ == "__main__":
    main()
