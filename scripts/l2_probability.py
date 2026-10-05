"""L2: probabilitas reaksi emas setelah rilis data (headless, untuk GitHub Actions).
Dibangun dari notebook L2. Butuh: FRED_API_KEY, KAGGLE_USERNAME + KAGGLE_KEY (atau KAGGLE_API_TOKEN).
Zona waktu data harga dideteksi otomatis; kalau tidak bisa diverifikasi, ekspor dibatalkan (tidak menulis hasil palsu)."""

# %% Konfigurasi
import os, re, glob, sys, json, subprocess, importlib, warnings
import numpy as np, pandas as pd
from zoneinfo import ZoneInfo
from scipy.optimize import minimize_scalar
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')
BASE = os.environ.get('MED_BASE', './cache_l2')
os.makedirs(BASE + '/out', exist_ok=True); os.makedirs(BASE + '/data', exist_ok=True)
print('Folder kerja:', os.path.abspath(BASE))
def _secret(name):                                         # Colab: ikon kunci di sidebar kiri > tambah FRED_API_KEY > aktifkan akses notebook
    try:
        from google.colab import userdata
        return userdata.get(name)
    except Exception:
        return os.environ.get(name)
FRED_API_KEY = _secret('FRED_API_KEY')

USE_SYNTHETIC = False                     # True = data sintetis untuk uji kode
SYNTH_EFFECT  = 1.0                       # kekuatan reaksi di data sintetis. Isi 0 untuk uji 'tanpa sinyal' (harus GAGAL)
KAGGLE_SLUG   = 'novandraanugrah/xauusd-gold-price-historical-data-2004-2024'
PRICE_CSV     = None                      # isi path file 1 menit bila deteksi otomatis gagal
AUTO_TZ       = True                      # deteksi zona waktu otomatis
DATA_TZ       = os.environ.get('DATA_TZ', 'UTC')                     # zona waktu jam di dataset harga. Ubah setelah cell 'Cek zona waktu'
CONSENSUS_CSV = os.environ.get('CONSENSUS_CSV', BASE + '/data/consensus.csv')   # opsional: kolom date,ind,consensus (konsensus pasar sungguhan)
FORCE_RELOAD  = False                     # True = abaikan cache di Drive (unduh/parse ulang)
PRICE_CACHE   = BASE + '/data/xau_1m_close_raw.parquet'   # cache harga 1 menit (jam asli dataset)
REL_CACHE     = BASE + '/data/rilis_fred_pertama.csv'     # cache angka rilis pertama dari FRED
HORIZON_MIN = 30      # jendela reaksi setelah rilis
PRE_MIN     = 1       # harga acuan sebelum rilis (menit)
THETA_K     = 0.5     # ambang "signifikan" = THETA_K x volatilitas ekspektasi
MIN_EVENTS  = 60      # peristiwa minimum sebelum prediksi OOS pertama
REFIT_EVERY = 10      # refit setiap N peristiwa
CALIB_FRAC  = 0.3     # porsi akhir data latih untuk kalibrasi suhu
MIN_OOS     = 100     # kriteria lulus
MAX_ECE     = 0.08    # kriteria lulus
SEED = 7

OUT_JSON = os.environ.get('OUT_JSON', BASE + '/out/prob_export.json')
if os.path.exists(OUT_JSON) and not os.environ.get('FORCE'):
    try:
        _g = pd.Timestamp(json.load(open(OUT_JSON)).get('generated')); _age = (pd.Timestamp.now() - _g).days
        if _age < 30: print(f'prob_export.json masih baru ({_age} hari), dilewati. Set FORCE=1 untuk memaksa.'); sys.exit(0)
    except Exception: pass
if not USE_SYNTHETIC and not os.environ.get('L2_TEST') and not (os.environ.get('KAGGLE_USERNAME') or os.environ.get('KAGGLE_API_TOKEN') or os.path.exists(os.path.expanduser('~/.kaggle/kaggle.json'))):
    print('KAGGLE_USERNAME/KAGGLE_KEY (atau KAGGLE_API_TOKEN) belum diset di GitHub Secrets. Probabilitas tidak dihitung.'); sys.exit(0)

# %% Definisi indikator (sama dengan alat web)
# c: I = inflasi, G = growth. s: tanda (positif = lebih panas / lebih kuat). sd: σ awal. tz,t: jam rilis (PERIKSA tiap baris dengan kalender resmi).
IND = {
 'cpi_core':dict(c='I',s=1, sd=.10,tz='America/New_York',t='08:30'),
 'cpi':     dict(c='I',s=1, sd=.12,tz='America/New_York',t='08:30'),
 'pce_core':dict(c='I',s=1, sd=.08,tz='America/New_York',t='08:30'),
 'ppi':     dict(c='I',s=1, sd=.25,tz='America/New_York',t='08:30'),
 'ahe':     dict(c='I',s=1, sd=.12,tz='America/New_York',t='08:30'),
 'nfp':     dict(c='G',s=1, sd=75, tz='America/New_York',t='08:30'),
 'unemp':   dict(c='G',s=-1,sd=.12,tz='America/New_York',t='08:30'),
 'claims':  dict(c='G',s=-1,sd=15, tz='America/New_York',t='08:30'),
 'jolts':   dict(c='G',s=1, sd=.35,tz='America/New_York',t='10:00'),
 'ism_m':   dict(c='G',s=1, sd=1.5,tz='America/New_York',t='10:00'),
 'ism_s':   dict(c='G',s=1, sd=1.8,tz='America/New_York',t='10:00'),
 'retail':  dict(c='G',s=1, sd=.5, tz='America/New_York',t='08:30'),
 'ip':      dict(c='G',s=1, sd=.3, tz='America/New_York',t='09:15'),
 'gdp':     dict(c='G',s=1, sd=.7, tz='America/New_York',t='08:30'),
 'cn_pmi':  dict(c='G',s=1, sd=.7, tz='Asia/Shanghai',   t='09:30'),
 'eu_pmi':  dict(c='G',s=1, sd=1.2,tz='Europe/Berlin',   t='10:00'),
}

# %% Data sintetis (HANYA untuk uji pipeline)
def make_synthetic(seed=SEED, years=4):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range('2021-01-04', periods=252 * years)
    idx = (days.values[:, None] + (np.arange(1440) * np.timedelta64(1, 'm'))[None, :]).ravel()
    n = len(idx); r = rng.normal(0, 0.00026, n)
    rel = []
    for d in days:
        if d.day in (12, 13) and d.weekday() < 5 and not any(x[0] == d.strftime('%Y-%m') for x in rel if x[1] == 'cpi_core'):
            rel.append((d.strftime('%Y-%m'), 'cpi_core', d))
    rows = []
    for ym, _, d in rel:
        rows.append((d, 'cpi_core', rng.normal(0.25, .1)))
    for d in days:
        if d.weekday() == 4 and d.day <= 7:
            rows.append((d, 'nfp', 0)); rows.append((d, 'unemp', 0))
        if d.weekday() == 3: rows.append((d, 'claims', 0))
        if d.day in (1, 2) and d.weekday() < 5: rows.append((d, 'ism_m', 0))
    out = []; seen = set()
    for d, ind, _ in rows:
        if (d, ind) in seen: continue
        seen.add((d, ind)); m = IND[ind]; sd = m['sd']
        cons = {'cpi_core': .25, 'nfp': 150, 'unemp': 4.2, 'claims': 225, 'ism_m': 50}[ind]
        act = cons + rng.normal(0, sd * 1.1)
        out.append(dict(date=d.date(), ind=ind, actual=round(act, 3), consensus=cons))
    rl = pd.DataFrame(out)
    # reaksi harga: inflasi panas -> turun, growth kuat -> naik tipis (kunci pada z sebenarnya)
    for d, g in rl.groupby('date'):
        zi = zg = 0.
        for r_ in g.itertuples():
            m = IND[r_.ind]; z = m['s'] * (r_.actual - r_.consensus) / m['sd']
            if m['c'] == 'I': zi += z
            else: zg += z / max(1, len(g))
        m0 = IND[g.iloc[0]['ind']]
        loc = pd.Timestamp(d.year, d.month, d.day, int(m0['t'][:2]), int(m0['t'][3:]), tz=ZoneInfo(m0['tz'])).tz_convert('UTC').tz_localize(None)
        k = np.searchsorted(idx, np.datetime64(loc))
        if k + 6 < n:
            jump = SYNTH_EFFECT * (-1.0 * zi + 0.7 * zg) * 0.00026 * np.sqrt(HORIZON_MIN) * 0.8
            r[k:k + 5] += jump / 5
    px = pd.Series(1900 * np.exp(np.cumsum(r)), index=pd.DatetimeIndex(idx))
    return rl, {'XAU': px}

# %% Loader harga (Kaggle) dan angka rilis (FRED, nilai pertama)
def check_minute_bars(s):
    med = s.index.to_series().diff().median()
    if pd.isna(med) or med > pd.Timedelta('5min'):
        raise ValueError(f'Data ini bukan data 1 menit (selisih tengah antar bar = {med}, {len(s)} baris). Event study 30 menit butuh bar 1 menit. Periksa daftar file dan isi PRICE_CSV dengan file 1m.')

def _tz_to_utc(s):
    if DATA_TZ == 'UTC': return s
    idx = s.index.tz_localize(DATA_TZ, ambiguous='NaT', nonexistent='NaT'); keep = ~idx.isna()
    s = s[keep]; s.index = idx[keep].tz_convert('UTC').tz_localize(None); return s

def load_kaggle_xau():
    if os.path.exists(PRICE_CACHE) and not FORCE_RELOAD:
        s = pd.read_parquet(PRICE_CACHE)['close']; print('Cache harga dipakai:', PRICE_CACHE, '|', len(s), 'baris')
        check_minute_bars(s); s = _tz_to_utc(s); print('Rentang harga (UTC):', s.index.min(), 's/d', s.index.max()); return s
    f = PRICE_CSV
    if f is None:
        import kagglehub
        path = kagglehub.dataset_download(KAGGLE_SLUG)
        files = sorted(glob.glob(path + '/**/*.csv', recursive=True))
        print('File di dataset:', [(os.path.basename(x), round(os.path.getsize(x) / 1e6, 1)) for x in files], '(nama, MB)')
        pat = re.compile(r'(?<![0-9A-Za-z])(1m|1min|m1)(?![0-9A-Za-z])', re.I)
        cand = [x for x in files if pat.search(os.path.basename(x))]
        if not cand: raise FileNotFoundError('File 1 menit tidak terdeteksi. Isi PRICE_CSV dengan salah satu path di daftar atas.')
        f = cand[0]
    print('Memakai:', f)
    with open(f, 'r', errors='ignore') as fh: head = fh.readline()
    sep = ';' if head.count(';') >= head.count(',') else ','
    df = pd.read_csv(f, sep=sep)
    df.columns = [c.strip().lower() for c in df.columns]
    print('Kolom:', list(df.columns), '| baris:', len(df))
    dcol = next((c for c in ['date', 'datetime', 'timestamp', 'time'] if c in df.columns), df.columns[0])
    ts = df[dcol].astype(str).str.strip()
    if dcol == 'date' and 'time' in df.columns: ts = ts + ' ' + df['time'].astype(str).str.strip()
    try: t = pd.to_datetime(ts, format='%Y.%m.%d %H:%M')
    except Exception: t = pd.to_datetime(ts, format='mixed')
    s = pd.Series(df['close'].astype(float).values, index=pd.DatetimeIndex(t)).sort_index()
    s = s[~s.index.duplicated()]
    check_minute_bars(s)
    try: s.rename('close').to_frame().to_parquet(PRICE_CACHE); print('Cache harga disimpan:', PRICE_CACHE)
    except Exception as e: print('Cache harga tidak tersimpan:', repr(e)[:100])
    s = _tz_to_utc(s)                                      # jam dataset -> UTC (tanpa tz)
    print('Rentang harga (UTC):', s.index.min(), 's/d', s.index.max())
    return s

# ind: (series FRED, jenis, skala). pct = % perubahan m/m, diff = selisih level, level = apa adanya
FRED_MAP = {
 'cpi_core': ('CPILFESL', 'pct', 1), 'cpi': ('CPIAUCSL', 'pct', 1), 'pce_core': ('PCEPILFE', 'pct', 1), 'ppi': ('PPIFIS', 'pct', 1),
 'ahe': ('CES0500000003', 'pct', 1), 'nfp': ('PAYEMS', 'diff', 1), 'unemp': ('UNRATE', 'level', 1),
 'claims': ('ICSA', 'level', 1e-3), 'jolts': ('JTSJOL', 'level', 1e-3), 'retail': ('RSAFS', 'pct', 1),
 'ip': ('INDPRO', 'pct', 1), 'gdp': ('A191RL1Q225SBEA', 'level', 1)}
EXP_N = {'cpi_core': 3, 'cpi': 3, 'pce_core': 3, 'ppi': 3, 'ahe': 3, 'nfp': 3, 'unemp': 1, 'claims': 4, 'jolts': 1, 'retail': 3, 'ip': 3, 'gdp': 2}

def first_release_values(a, kind, scale=1.0):
    """a: DataFrame kolom realtime_start, date, value (format get_series_all_releases). Nilai = rilis PERTAMA tiap periode.
    Untuk pct/diff, periode sebelumnya diambil dari vintage yang sudah diketahui pada hari rilis (bukan revisi masa depan)."""
    a = a.dropna(subset=['value']).copy()
    a['realtime_start'] = pd.to_datetime(a['realtime_start']); a['date'] = pd.to_datetime(a['date'])
    a = a.sort_values(['date', 'realtime_start'])
    vint = {d: (g['realtime_start'].values, g['value'].astype(float).values) for d, g in a.groupby('date')}
    dates = sorted(vint); rows = []
    for i, d in enumerate(dates):
        rs, v = vint[d]; rel_date = rs[0]; first = v[0]
        lag = (pd.Timestamp(rel_date) - d).days
        if lag < 0 or lag > 135: continue                   # data lama yang vintage-nya baru dimulai belakangan: tanggal rilis tidak bisa dipercaya
        if kind == 'level': val = first
        else:
            if i == 0 or (d - dates[i - 1]).days > 100: continue     # butuh periode sebelumnya yang berurutan
            prs, pv = vint[dates[i - 1]]; m = prs <= rel_date
            if not m.any(): continue
            prev = pv[m][-1]; val = first - prev if kind == 'diff' else 100 * (first / prev - 1)
        rows.append((pd.Timestamp(rel_date).normalize(), val * scale))
    return pd.DataFrame(rows, columns=['date', 'actual'])

def fetch_fred_rel():
    if os.path.exists(REL_CACHE) and not FORCE_RELOAD:
        r = pd.read_csv(REL_CACHE, parse_dates=['date']); print('Cache rilis dipakai:', REL_CACHE, '|', len(r), 'rilis'); return r
    from fredapi import Fred
    fred = Fred(api_key=FRED_API_KEY); out = []
    for ind, (sid, kind, scale) in FRED_MAP.items():
        try: a = fred.get_series_all_releases(sid)
        except Exception as e: print('Gagal', sid, e); continue
        t = first_release_values(a, kind, scale).sort_values('date').reset_index(drop=True); t['ind'] = ind
        n = EXP_N[ind]; t['consensus'] = t['actual'].shift(1).rolling(n, min_periods=n).mean()   # proxy point-in-time: rata-rata n rilis sebelumnya
        out.append(t.dropna()); print(f'{ind:9s} {sid:16s} {len(t)} rilis')
    r = pd.concat(out)[['date', 'ind', 'actual', 'consensus']]
    r.to_csv(REL_CACHE, index=False); print('Cache rilis disimpan:', REL_CACHE)
    return r

# %% Muat data
USING_PROXY = True
if USE_SYNTHETIC:
    rel, PRICES = make_synthetic()
    print('MODE SINTETIS: hanya uji kode. Jangan baca hasilnya sebagai kondisi pasar.')
else:
    if not FRED_API_KEY: raise RuntimeError('FRED_API_KEY belum diisi. Tambahkan di Colab Secrets (ikon kunci) lalu aktifkan akses notebook.')
    PRICES = {'XAU': load_kaggle_xau()}
    rel = fetch_fred_rel()
    if os.path.exists(CONSENSUS_CSV):                      # konsensus pasar sungguhan menggantikan proxy
        c = pd.read_csv(CONSENSUS_CSV, comment='#', header=None, names=['date', 'ind', 'cons_real'], parse_dates=['date'])
        rel = rel.merge(c[['date', 'ind', 'cons_real']], on=['date', 'ind'], how='left')
        USING_PROXY = rel['cons_real'].isna().mean() > 0.5
        rel['consensus'] = rel['cons_real'].fillna(rel['consensus']); rel = rel.drop(columns='cons_real')
    print('Sumber surprise:', 'PROXY statistik (rata-rata rilis sebelumnya), BUKAN konsensus pasar' if USING_PROXY else 'konsensus dari file')
rel['date'] = pd.to_datetime(rel['date']); rel = rel[rel['ind'].isin(IND)].dropna(subset=['actual', 'consensus'])
print(len(rel), 'rilis;', {k: len(v) for k, v in PRICES.items()}, 'baris harga')

# %% Surprise point-in-time dan penggabungan per timestamp
def build_events(rel):
    rel = rel.sort_values('date').copy(); zs = []
    hist = {k: [] for k in IND}
    for r in rel.itertuples():
        m = IND[r.ind]; h = hist[r.ind]
        sd = np.std(h, ddof=1) if len(h) >= 8 and np.std(h, ddof=1) > 0 else m['sd']   # hanya rilis SEBELUMNYA
        zs.append(float(np.clip(m['s'] * (r.actual - r.consensus) / sd, -4, 4)))
        h.append(r.actual - r.consensus)
    rel['z'] = zs; rel['c'] = rel['ind'].map(lambda i: IND[i]['c'])
    def utc(r):
        m = IND[r.ind]; d = r.date
        return pd.Timestamp(d.year, d.month, d.day, int(m['t'][:2]), int(m['t'][3:]), tz=ZoneInfo(m['tz'])).tz_convert('UTC').tz_localize(None)
    rel['t'] = [utc(r) for r in rel.itertuples()]
    g = rel.groupby('t')
    ev = pd.DataFrame({'zI': g.apply(lambda x: x.loc[x.c == 'I', 'z'].mean() if (x.c == 'I').any() else 0.),
                       'zG': g.apply(lambda x: x.loc[x.c == 'G', 'z'].mean() if (x.c == 'G').any() else 0.),
                       'n_ind': g.size()}).reset_index().sort_values('t').reset_index(drop=True)
    ev['absz'] = np.maximum(ev.zI.abs(), ev.zG.abs())
    return ev
EV = build_events(rel)
print(len(EV), 'peristiwa (timestamp unik)')

# %% Cek zona waktu data harga
def tz_check(px, ev, span=range(-12, 13)):
    """Rilis AS 08:30 ET harus memunculkan lonjakan |return| tepat di menitnya. Cari pergeseran jam (k) yang menaikkan lonjakan itu."""
    a = np.abs(np.log(px).diff()).dropna(); ts = a.index.values; v = a.values
    e8 = ev[(ev['t'].dt.minute == 30) & (ev['t'].dt.hour.isin([12, 13]))]
    res = {}
    for name, months in [('dingin', (12, 1, 2)), ('panas', (6, 7, 8))]:
        e = e8[e8['t'].dt.month.isin(months)]['t'].values; row = {}
        for k in span:
            sh = np.timedelta64(k, 'h')
            i0 = np.searchsorted(ts, e + sh); i1 = np.searchsorted(ts, e + sh + np.timedelta64(5, 'm')); ib = np.searchsorted(ts, e + sh - np.timedelta64(180, 'm'))
            r = [v[x0:x1].mean() / (v[b0:x0].mean() + 1e-12) for x0, x1, b0 in zip(i0, i1, ib) if x1 - x0 >= 3 and x0 - b0 >= 60]
            row[k] = float(np.mean(r)) if len(r) >= 20 else np.nan
        res[name] = pd.Series(row)
    return pd.DataFrame(res)
TZ = tz_check(PRICES['XAU'], EV)
best = TZ.idxmax(); kw, ks = int(best['dingin']), int(best['panas'])
print(TZ.round(2).T.to_string()); print('Pergeseran terbaik: dingin', kw, '| panas', ks, '| (rasio lonjakan di puncak:', round(float(TZ.max().min()), 2), ')')
if kw == 0 and ks == 0: print('OK: jam data sudah selaras dengan UTC.')
elif kw == ks:
    print(f"Jam data = UTC{kw:+d} (jika DATA_TZ masih 'UTC'). Set DATA_TZ = 'Etc/GMT{-kw:+d}' di Konfigurasi lalu jalankan ulang dari 'Muat data'.")
else:
    print(f'Pergeseran berbeda antar musim ({kw:+d} dingin, {ks:+d} panas): jam data ber-DST (jam broker). Coba DATA_TZ = "Europe/Athens", jalankan ulang dari Muat data, lalu cek lagi sampai keduanya 0.')
if float(TZ.max().min()) < 1.3: print('PERHATIAN: lonjakan di puncak lemah. Data 1 menit mungkin jarang di era awal, atau tanggal rilis dari FRED meleset. Jangan lanjut sebelum ini jelas.')

# %% Koreksi zona waktu otomatis
if AUTO_TZ and DATA_TZ == 'UTC' and not (kw == 0 and ks == 0):
    DATA_TZ = f"Etc/GMT{-kw:+d}" if kw == ks else 'Europe/Athens'
    print('AUTO zona waktu ->', DATA_TZ)
    PRICES['XAU'] = load_kaggle_xau()
    TZ = tz_check(PRICES['XAU'], EV); best = TZ.idxmax(); kw, ks = int(best['dingin']), int(best['panas']); print(TZ.round(2).T.to_string())
    if not (kw == 0 and ks == 0): raise RuntimeError(f'Zona waktu tidak bisa diselaraskan otomatis (sisa pergeseran dingin {kw}, panas {ks}). Set DATA_TZ manual. Ekspor dibatalkan.')
if float(TZ.max().min()) < 1.3: raise RuntimeError('Lonjakan pasca-rilis lemah: zona waktu/tanggal rilis tidak bisa diverifikasi. Ekspor dibatalkan.')
print('Zona waktu terverifikasi:', DATA_TZ)

# %% Label reaksi harga per aset
def label_asset(ev, px):
    px = px[~px.index.duplicated()].sort_index()
    lp = np.log(px); r1 = lp.diff()
    vol1 = r1.rolling(1440, min_periods=500).std()                   # volatilitas 1 menit, 24 jam terakhir
    tab = pd.DataFrame({'p': px.values, 'v': vol1.values}, index=px.index).reset_index().rename(columns={'index': 'time'})
    tab.columns = ['time', 'p', 'v']
    def asof(ts, col):
        q = pd.DataFrame({'time': ts.values}).sort_values('time')
        m = pd.merge_asof(q, tab, on='time', direction='backward', tolerance=pd.Timedelta('5min'))
        return m[col].values
    t = ev['t']
    pre_t = t - pd.Timedelta(minutes=PRE_MIN); post_t = t + pd.Timedelta(minutes=HORIZON_MIN)
    d = ev.copy(); d['p0'] = asof(pre_t, 'p'); d['p1'] = asof(post_t, 'p'); d['v1'] = asof(pre_t, 'v')
    d = d.dropna(subset=['p0', 'p1', 'v1']).reset_index(drop=True)
    d['r'] = np.log(d.p1 / d.p0); d['sig'] = d.v1 * np.sqrt(HORIZON_MIN); th = THETA_K * d['sig']
    d['y'] = np.where(d.r > th, 2, np.where(d.r < -th, 0, 1))
    d['vol_pct'] = [0.5 if i == 0 else float((d.v1.iloc[:i] <= d.v1.iloc[i]).mean()) for i in range(len(d))]   # persentil ekspansif
    return d
FEATS = ['zG', 'zI', 'absz', 'vol_pct']

# %% Model: multinomial logistik + kalibrasi suhu
def _fit_T(logp, y):
    def nll(T):
        z = logp / T; z = z - z.max(1, keepdims=True); p = np.exp(z); p /= p.sum(1, keepdims=True)
        return -np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1)))
    return minimize_scalar(nll, bounds=(.3, 5), method='bounded').x

def fit_model(X, y):
    k = int(len(X) * (1 - CALIB_FRAC)); sc = StandardScaler().fit(X[:k])
    clf = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(X[:k]), y[:k])
    M = dict(sc=sc, clf=clf, T=1.0)
    if len(X) - k >= 15:
        lp = _lp(M, X[k:]); M['T'] = float(_fit_T(lp, y[k:]))
    return M

def _lp(M, X):
    lp_ = M['clf'].predict_log_proba(M['sc'].transform(X)); out = np.full((len(X), 3), -12.)
    for j, c in enumerate(M['clf'].classes_): out[:, int(c)] = lp_[:, j]
    return out

def predict(M, X):
    z = _lp(M, X) / M['T']; z = z - z.max(1, keepdims=True); p = np.exp(z); p /= p.sum(1, keepdims=True)
    return np.clip(p, 1e-4, 1);

def clim(y):
    c = np.bincount(y, minlength=3) + 1.; return c / c.sum()

# %% Walk-forward out-of-sample
def walk_forward(d):
    X = d[FEATS].values; y = d['y'].values; P = np.full((len(d), 3), np.nan); B = P.copy(); i = MIN_EVENTS
    while i < len(d):
        j = min(i + REFIT_EVERY, len(d)); te0 = d['t'].iloc[i]
        tr = np.where(d['t'].values + np.timedelta64(HORIZON_MIN, 'm') < np.datetime64(te0))[0]   # purge: jendela hasil tidak boleh menyentuh data uji
        M = fit_model(X[tr], y[tr]); P[i:j] = predict(M, X[i:j]); B[i:j] = clim(y[tr]); i = j
    ok = ~np.isnan(P[:, 0]); return P[ok], B[ok], y[ok], d.loc[ok].reset_index(drop=True)

# %% Metrik, CI, kriteria lulus
def brier(P, y): return ((P - np.eye(3)[y]) ** 2).sum(1)
def ece(p, hit, bins=4):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); q[-1] += 1e-9; e = 0.; rows = []
    for a, b in zip(q[:-1], q[1:]):
        m = (p >= a) & (p < b)
        if m.sum(): e += m.mean() * abs(p[m].mean() - hit[m].mean()); rows.append((round(float(p[m].mean()), 3), round(float(hit[m].mean()), 3), int(m.sum())))
    return e, rows
def evaluate(P, B, y, name):
    bm, bb = brier(P, y), brier(B, y); skill = 1 - bm.mean() / bb.mean()
    rng = np.random.default_rng(SEED); sk = []
    for _ in range(2000):
        i = rng.integers(0, len(y), len(y)); sk.append(1 - bm[i].mean() / bb[i].mean())
    lo, hi = np.percentile(sk, [2.5, 97.5]); pval = float((np.array(sk) <= 0).mean())
    e_up, tab_up = ece(P[:, 2], (y == 2).astype(float)); e_dn, tab_dn = ece(P[:, 0], (y == 0).astype(float))
    E = (e_up + e_dn) / 2; mv = y != 1; dirhit = float((np.where(P[:, 2] > P[:, 0], 2, 0)[mv] == y[mv]).mean()) if mv.any() else np.nan
    verdict = 'data kurang' if len(y) < MIN_OOS else ('lulus' if (lo > 0 and E < MAX_ECE) else 'gagal')
    return dict(asset=name, n_oos=int(len(y)), skill=float(skill), skill_lo=float(lo), skill_hi=float(hi), p_boot=pval, ece=float(E), dir_hit=dirhit, verdict=verdict, rel_up=tab_up, rel_dn=tab_dn)

# %% Jalankan untuk semua aset + koreksi Holm
RESULTS = {}; DATA = {}
for a, px in PRICES.items():
    d = label_asset(EV, px); DATA[a] = d
    print(f'{a}: {len(d)} dari {len(EV)} peristiwa punya harga di sekitar waktu rilis (rentang harga {px.index.min():%Y-%m-%d} s/d {px.index.max():%Y-%m-%d}; rentang rilis {EV.t.min():%Y-%m-%d} s/d {EV.t.max():%Y-%m-%d})')
    if len(d) <= MIN_EVENTS + 10:
        print(f'   -> {a}: data kurang. Penyebab umum: file harga bukan 1 menit, zona waktu/tanggal rilis meleset, atau rentang harga tidak menutup rentang rilis.')
        RESULTS[a] = dict(asset=a, n_oos=0, verdict='data kurang', skill=np.nan, skill_lo=np.nan, skill_hi=np.nan, p_boot=1., ece=np.nan, dir_hit=np.nan, rel_up=[], rel_dn=[]); continue
    P, B, y, dd = walk_forward(d); RESULTS[a] = evaluate(P, B, y, a)
ps = sorted([(r['p_boot'], a) for a, r in RESULTS.items()]); m = len(ps)
for rank, (p, a) in enumerate(ps):                                   # Holm-Bonferroni
    RESULTS[a]['p_holm'] = float(min(1., p * (m - rank)))
    if RESULTS[a]['verdict'] == 'lulus' and RESULTS[a]['p_holm'] >= .05: RESULTS[a]['verdict'] = 'gagal'
for a, r in RESULTS.items():
    print(f"{a}: n_oos={r['n_oos']}  skill={r['skill']:+.3f} [{r['skill_lo']:+.3f}, {r['skill_hi']:+.3f}]  ECE={r['ece']:.3f}  arah={r['dir_hit']:.2f}  Holm p={r['p_holm']:.3f}  -> {r['verdict'].upper()}")
    print('   keandalan P(naik) (rata prediksi, frekuensi nyata, n):', r['rel_up'])

# %% Model final, grid probabilitas, ekspor ke alat web
def make_grid(M):
    g = {}
    for cat in ['I', 'G']:
        rows = []
        for z in range(-3, 4):
            x = np.array([[z if cat == 'G' else 0., z if cat == 'I' else 0., abs(z), .5]])
            p = predict(M, x)[0]; rows.append(dict(z=z, p_dn=round(float(p[0]), 4), p_flat=round(float(p[1]), 4), p_up=round(float(p[2]), 4)))
        g[cat] = rows
    return g
export = dict(generated=pd.Timestamp.now().isoformat(timespec='seconds'), synthetic=bool(USE_SYNTHETIC), consensus='proxy' if USING_PROXY else 'file', horizon_min=HORIZON_MIN, theta_k=THETA_K, assets={})
for a, d in DATA.items():
    r = RESULTS[a]
    if r['n_oos'] == 0: continue
    M = fit_model(d[FEATS].values, d['y'].values); base = clim(d['y'].values)
    export['assets'][a] = dict(n=int(len(d)), n_oos=r['n_oos'], skill=round(r['skill'], 4), skill_lo=round(r['skill_lo'], 4), skill_hi=round(r['skill_hi'], 4),
        ece=round(r['ece'], 4), p_holm=round(r['p_holm'], 4), verdict=r['verdict'], base=dict(p_dn=round(float(base[0]), 4), p_flat=round(float(base[1]), 4), p_up=round(float(base[2]), 4)), grid=make_grid(M))
if not export['assets']:
    raise RuntimeError('Tidak ada aset yang punya data cukup, jadi prob_export.json TIDAK ditulis. Lihat pesan "data kurang" di cell sebelumnya.')
path = OUT_JSON; os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
with open(path, 'w') as f: json.dump(export, f, indent=1)
print('Tersimpan:', path)
print(json.dumps(export['assets'].get('XAU', {}).get('grid', {}).get('I', [])[:7], indent=0)[:600])
