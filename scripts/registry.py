"""Registry seri data v2: SATU tempat yang mendefinisikan setiap angka di sistem.
Tiap seri: label penuh, grup, frekuensi, penyedia berlapis (urutan = cadangan), batas wajar,
umur maksimum sebelum dianggap basi. Penyedia: ("fred", id) | ("yf", ticker).
Baris dengan flag v=True BELUM diuji dari sandbox: lihat status.json setelah run pertama."""

# freq -> (umur maks hari sebelum 'basi', menit minimum antar-fetch, tier)
FREQ = {"harian": (5, 25, "cepat"), "mingguan": (12, 180, "lambat"),
        "bulanan": (50, 180, "lambat"), "kuartalan": (130, 360, "lambat")}

def S(id, label, group, freq, prov, unit="", lo=None, hi=None, crit=False, v=False, note=""):
    return dict(id=id, label=label, group=group, freq=freq, prov=prov, unit=unit,
                lo=lo, hi=hi, crit=crit, v=v, note=note)

REGISTRY = [
 # --- Harga aset prioritas (tier cepat; yfinance, cadangan FRED bila ada)
 S("XAUUSD", "Emas (XAU/USD, futures GC)", "Harga", "harian", [("yf", "GC=F")], "USD/oz", 500, 6000, True),
 S("WTI", "Minyak mentah WTI", "Harga", "harian", [("fred", "DCOILWTICO"), ("yf", "CL=F")], "USD/bbl", -50, 250, True),
 S("SPX", "S&P 500", "Harga", "harian", [("fred", "SP500"), ("yf", "^GSPC")], "indeks", 500, 20000, True),
 S("USDJPY", "USD/JPY", "Harga", "harian", [("yf", "JPY=X"), ("fred", "DEXJPUS")], "JPY", 50, 250, True),
 S("EURUSD", "EUR/USD", "Harga", "harian", [("yf", "EURUSD=X"), ("fred", "DEXUSEU")], "USD", 0.6, 1.6, True),
 S("DXY", "Indeks Dolar AS (DXY)", "Harga", "harian", [("yf", "DX-Y.NYB"), ("fred", "DTWEXBGS")], "indeks", 70, 140),
 S("COPPER", "Tembaga (futures HG)", "Harga", "harian", [("yf", "HG=F")], "USD/lb", 1, 10),
 S("NDX", "Nasdaq 100", "Harga", "harian", [("yf", "^NDX"), ("fred", "NASDAQ100")], "indeks", 2000, 60000),
 S("BTC", "Bitcoin", "Harga", "harian", [("yf", "BTC-USD"), ("fred", "CBBTCUSD")], "USD", 1000, 1000000),
 S("EEM", "Pasar berkembang (ETF EEM)", "Harga", "harian", [("yf", "EEM")], "USD", 10, 100),
 S("TLT", "Obligasi AS 20+ tahun (ETF TLT)", "Harga", "harian", [("yf", "TLT")], "USD", 30, 200),
 S("HYG", "Obligasi korporasi high-yield (ETF HYG)", "Harga", "harian", [("yf", "HYG")], "USD", 40, 120),
 S("NIKKEI", "Nikkei 225", "Harga", "harian", [("yf", "^N225")], "indeks", 5000, 100000),
 # --- Suku bunga, yield, ekspektasi
 S("US02Y", "Yield obligasi AS 2 tahun", "Yield", "harian", [("fred", "DGS2")], "%", -1, 12, True),
 S("US10Y", "Yield obligasi AS 10 tahun", "Yield", "harian", [("fred", "DGS10"), ("yf", "^TNX")], "%", -1, 12, True),
 S("US30Y", "Yield obligasi AS 30 tahun", "Yield", "harian", [("fred", "DGS30")], "%", -1, 12),
 S("REAL10Y", "Yield riil 10 tahun (TIPS)", "Yield", "harian", [("fred", "DFII10")], "%", -3, 6),
 S("BE10Y", "Ekspektasi inflasi 10 tahun (breakeven)", "Yield", "harian", [("fred", "T10YIE")], "%", -1, 6),
 S("CURVE", "Kurva 10 tahun minus 2 tahun", "Yield", "harian", [("fred", "T10Y2Y")], "poin %", -4, 4),
 S("DE10Y", "Yield obligasi Jerman 10 tahun", "Yield", "bulanan", [("fred", "IRLTLT01DEM156N")], "%", -2, 15, v=True),
 S("JP10Y", "Yield obligasi Jepang 10 tahun", "Yield", "bulanan", [("fred", "IRLTLT01JPM156N")], "%", -1, 10, v=True),
 # --- Suku bunga kebijakan bank sentral (yfinance tidak punya ini; FRED punya)
 S("FED", "Suku bunga kebijakan Fed (batas atas)", "Kebijakan", "harian", [("fred", "DFEDTARU")], "%", 0, 12, True),
 S("ECB", "Suku bunga deposito ECB", "Kebijakan", "harian", [("fred", "ECBDFR")], "%", -1, 10),
 S("BOE", "Suku bunga semalam Inggris (SONIA, proksi BoE)", "Kebijakan", "harian", [("fred", "IUDSOIA")], "%", 0, 12, v=True),
 S("BOJ", "Suku bunga antarbank Jepang (proksi BoJ)", "Kebijakan", "bulanan", [("fred", "IRSTCI01JPM156N")], "%", -1, 5, v=True),
 S("BOC", "Suku bunga kebijakan Kanada", "Kebijakan", "bulanan", [("fred", "IRSTCB01CAM156N")], "%", 0, 12, v=True),
 S("RBA", "Suku bunga kebijakan Australia", "Kebijakan", "bulanan", [("fred", "IRSTCB01AUM156N")], "%", 0, 12, v=True),
 S("SNB", "Suku bunga kebijakan Swiss", "Kebijakan", "bulanan", [("fred", "IRSTCB01CHM156N")], "%", -2, 8, v=True),
 # --- Stres dan likuiditas
 S("VIX", "VIX (volatilitas saham AS)", "Stres", "harian", [("fred", "VIXCLS"), ("yf", "^VIX")], "poin", 5, 150, True),
 S("VIX3M", "VIX 3 bulan", "Stres", "harian", [("fred", "VXVCLS"), ("yf", "^VIX3M")], "poin", 5, 100),
 S("MOVE", "MOVE (volatilitas obligasi AS)", "Stres", "harian", [("yf", "^MOVE")], "poin", 20, 300, v=True),
 S("HYOAS", "Selisih kredit high-yield (OAS)", "Stres", "harian", [("fred", "BAMLH0A0HYM2")], "%", 1, 25, True),
 S("NFCI", "Kondisi keuangan Chicago (NFCI)", "Stres", "mingguan", [("fred", "NFCI")], "indeks", -2, 6),
 S("WALCL", "Total aset neraca Fed", "Likuiditas", "mingguan", [("fred", "WALCL")], "juta USD", 1e6, 2e7),
 S("TGA", "Kas Treasury di Fed (TGA)", "Likuiditas", "mingguan", [("fred", "WTREGEN")], "miliar USD", 0, 2e3),
 S("RRP", "Reverse repo Fed", "Likuiditas", "harian", [("fred", "RRPONTSYD")], "miliar USD", 0, 3e3),
 # --- Pertumbuhan
 S("NFP", "Penggajian nonpertanian (level)", "Pertumbuhan", "bulanan", [("fred", "PAYEMS")], "ribu", 1e5, 2e5),
 S("UNEMP", "Tingkat pengangguran", "Pertumbuhan", "bulanan", [("fred", "UNRATE")], "%", 1, 20),
 S("CLAIMS", "Klaim pengangguran awal", "Pertumbuhan", "mingguan", [("fred", "ICSA")], "orang", 1e5, 7e6),
 S("RETAIL", "Penjualan ritel", "Pertumbuhan", "bulanan", [("fred", "RSAFS")], "juta USD", 1e5, 2e6),
 S("INDPRO", "Produksi industri", "Pertumbuhan", "bulanan", [("fred", "INDPRO")], "indeks", 50, 200),
 S("EMPIRE", "Survei manufaktur New York (Empire)", "Pertumbuhan", "bulanan", [("fred", "GACDISA066MSFRBNY")], "indeks", -80, 80),
 S("PHILLY", "Survei manufaktur Philadelphia", "Pertumbuhan", "bulanan", [("fred", "GACDFSA066MSFRBPHI")], "indeks", -80, 80),
 S("GDP", "PDB riil AS (pertumbuhan tahunan berantai)", "Pertumbuhan", "kuartalan", [("fred", "A191RL1Q225SBEA")], "%", -40, 40),
 # --- Inflasi
 S("CPI", "Indeks harga konsumen (CPI)", "Inflasi", "bulanan", [("fred", "CPIAUCSL")], "indeks", 100, 500),
 S("CPICORE", "CPI inti", "Inflasi", "bulanan", [("fred", "CPILFESL")], "indeks", 100, 500),
 S("PCECORE", "PCE inti", "Inflasi", "bulanan", [("fred", "PCEPILFE")], "indeks", 80, 400),
 S("PPI", "Indeks harga produsen (PPI)", "Inflasi", "bulanan", [("fred", "PPIFIS")], "indeks", 80, 400),
 S("AHE", "Upah per jam rata-rata", "Inflasi", "bulanan", [("fred", "CES0500000003")], "USD", 15, 80),
 S("NROU", "Pengangguran alami (NAIRU, CBO)", "Inflasi", "kuartalan", [("fred", "NROU")], "%", 2, 8),
]
BY_ID = {s["id"]: s for s in REGISTRY}
