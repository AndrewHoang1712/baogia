# -*- coding: utf-8 -*-
"""
Chay tren GitHub Actions: lay ton kho tu Google Sheet (qua Apps Script) -> tao tonkho.json ma hoa.
Bien moi truong can co: SHEET_URL, PW_KH, PW_NB, NB_SECRET
  PW_NB     = mat khau noi bo (doi luc nao cung duoc, khong can build lai index.html)
  NB_SECRET = khoa co dinh, PHAI GIONG het NB_SECRET trong cap-nhat-bao-gia.py
"""
import os, json, base64, hashlib, datetime, urllib.request, sys

SHEET_URL = os.environ.get('SHEET_URL', '')
PW_KH     = os.environ.get('PW_KH', '')
PW_NB     = os.environ.get('PW_NB', '')
NB_SECRET = os.environ.get('NB_SECRET', '')

if not SHEET_URL or not PW_KH or not PW_NB or not NB_SECRET:
    sys.exit('Thieu bien moi truong SHEET_URL / PW_KH / PW_NB / NB_SECRET (dat trong GitHub Secrets)')

# ---- 1. Lay du lieu tu Google Sheet ----
# CHONG CACHE: Google hay tra ve ban da luu san cho cung mot URL.
# Them tham so thoi gian + header no-cache de bat buoc doc moi.
import time as _time
_url = SHEET_URL + ('&' if '?' in SHEET_URL else '?') + 'nocache=' + str(int(_time.time()))
req = urllib.request.Request(_url, headers={
    'User-Agent': 'HDGroup-TonKho/' + str(int(_time.time())),
    'Cache-Control': 'no-cache, no-store, max-age=0',
    'Pragma': 'no-cache',
})
raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
if raw.strip() == 'denied':
    sys.exit('Google Sheet tu choi: KEY trong SHEET_URL khong dung')
try:
    payload = json.loads(raw)
except Exception:
    sys.exit('Khong doc duoc du lieu tra ve (kiem tra lai link /exec): ' + raw[:200])

stock = {str(k).strip().upper(): int(v) for k, v in payload.get('stock', {}).items()}
kho   = {str(k).strip().upper(): [int(x) for x in v] for k, v in payload.get('kho', {}).items()}
if not stock:
    sys.exit('Google Sheet khong co du lieu ton kho')

# ---- 1a0. CHAN BAN DOC THIEU: Google Sheet thinh thoang chi tra ve mot phan ma ----
# (da gap ~32 lan trong 80 ngay, co lan chi 700/5185 ma). Neu day ban thieu len web thi
# hang loat ma dang con hang se hien "Lien he" cho den lan quet sau -> khach tuong het hang.
# Gap truong hop do thi GIU NGUYEN tonkho.json cu, khong ghi de. So ma cua lan quet tot
# gan nhat luu trong tonkho-lichsu.json (khoa 'n') - khong co file do thi bo qua buoc nay.
NGUONG_THIEU = 0.85
try:
    import zlib as _z
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _A
    if os.path.exists('tonkho-lichsu.json'):
        _F = json.load(open('tonkho-lichsu.json', encoding='utf-8'))
        _k = hashlib.pbkdf2_hmac('sha256', NB_SECRET.encode(), base64.b64decode(_F['s']), 200000, 32)
        _n = json.loads(_z.decompress(_A(_k).decrypt(base64.b64decode(_F['i']), base64.b64decode(_F['c']), None))).get('n', 0)
        if _n and len(stock) < NGUONG_THIEU * _n:
            print('CANH BAO: Google Sheet chi tra ve %d ma (lan tot gan nhat %d, nguong %d%%).'
                  % (len(stock), _n, NGUONG_THIEU * 100))
            print('  -> Nghi Sheet doc thieu. GIU NGUYEN tonkho.json cu, khong day ban thieu len web.')
            print('  -> Lan quet sau (30 phut nua) se thu lai. Neu lap lai nhieu lan, kiem tra tab 2KHO.')
            sys.exit(0)
except SystemExit:
    raise
except Exception as _e:
    print('(bo qua buoc chan ban doc thieu:', type(_e).__name__, _e, ')')
print(f'Doc duoc {len(stock)} ma tu Google Sheet' + (f' (co chi tiet 2 kho: {len(kho)} ma)' if kho else ' (chi co tong ton)'))
# Dau van tay CUA RIENG DU LIEU SHEET - de biet Sheet co that su doi hay khong
_fp_sheet = hashlib.sha256(json.dumps([stock, kho], sort_keys=True).encode()).hexdigest()[:12]
print('Dau van tay du lieu Sheet:', _fp_sheet)
print('Vai ma dau:', list(stock.items())[:5])
print('Tong ton toan bo:', sum(stock.values()))

# ---- 1a. LICH SU TON KHO 5 MOC / NGAY (cho bieu do ton kho tren trang noi bo) ----
# File tonkho-lichsu.json: zlib + AES-GCM, khoa tu NB_SECRET (giong c2) -> chi tai khoan noi bo mo duoc.
# Luu ton tai 5 moc gio VN moi ngay: 9h, 12h, 16h, 19h, 22h. Moi lan quet thuoc ve moc GAN NHAT
# PHIA SAU no (tre toi 15 phut van tinh cho moc vua qua): quet 8h30 / 9h07 -> moc 9h, 9h40 -> moc 12h,
# 21h30 -> moc 22h, sau 22h15 -> moc 9h hom sau. Nhieu lan quet cung 1 moc thi lan SAU CUNG thang.
# Chi ghi khi ton DOI (o trong = ton giu nguyen tu moc truoc).
# Dinh dang (sau giai nen): {v:2, d0:'YYYY-MM-DD', moc:[9,12,16,19,22], dn:o_cuoi, n:so_ma,
#                            h:{MA:[o,k1,k2, o,k1,k2,...]}}   voi o = so_ngay_tu_d0 * SO_MOC + thu_tu_moc
# TOAN BO phan nay boc try/except: loi gi o day cung KHONG duoc lam hong viec cap nhat ton kho.
LS_FILE = 'tonkho-lichsu.json'
LS_NGUONG = 0.85          # lan quet doc duoc it hon 85% so ma lan truoc -> coi la Sheet doc thieu, bo qua
# v3 (09/11/2026): luu MOI lan quet - moc moi 30 phut tu 8h00 den 21h30 (dung nhip bot chay).
# LS_MOC tinh bang PHUT ke tu 0h (v2 cu tinh bang GIO).
LS_MOC = list(range(8 * 60, 21 * 60 + 30 + 1, 30))    # 480,510,...,1290 -> 28 moc/ngay
LS_TRE = 14               # phut: lan quet tre toi 14 phut sau moc van tinh cho moc do
LS_V = 3

def ls_gio(m):            # 540 -> '9h' | 570 -> '9h30'
    return '%dh' % (m // 60) if m % 60 == 0 else '%dh%02d' % (m // 60, m % 60)

def _ls_key(salt):
    return hashlib.pbkdf2_hmac('sha256', NB_SECRET.encode(), salt, 200000, 32)

def ls_o(luc, d0):
    """Vi tri o (ngay*SO_MOC + moc) cho 1 lan quet luc `luc` (datetime gio VN)."""
    ngay = (luc.date() - d0).days
    phut = luc.hour * 60 + luc.minute
    for k, m in enumerate(LS_MOC):
        if phut <= m + LS_TRE:
            return ngay * len(LS_MOC) + k
    return (ngay + 1) * len(LS_MOC)          # quet sau 21h44 -> moc 8h hom sau (dem khong doi ton)

def ls_doc():
    """Doc + giai ma file lich su. Chua co file -> None."""
    import zlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not os.path.exists(LS_FILE):
        return None
    F = json.load(open(LS_FILE, encoding='utf-8'))
    raw = AESGCM(_ls_key(base64.b64decode(F['s']))).decrypt(
        base64.b64decode(F['i']), base64.b64decode(F['c']), None)
    return json.loads(zlib.decompress(raw).decode('utf-8'))

def ls_ghi(obj):
    import zlib
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = zlib.compress(json.dumps(obj, separators=(',', ':')).encode('utf-8'), 9)
    salt, iv = os.urandom(16), os.urandom(12)
    F = {'v': obj.get('v', LS_V), 's': base64.b64encode(salt).decode(), 'i': base64.b64encode(iv).decode(),
         'c': base64.b64encode(AESGCM(_ls_key(salt)).encrypt(iv, raw, None)).decode()}
    with open(LS_FILE, 'w', encoding='utf-8') as f:
        json.dump(F, f, separators=(',', ':'))

def ls_cap_nhat(kho_map, luc):
    """Nap ton cua lan quet luc `luc` (gio VN) vao lich su. Tra ve True neu file thay doi (can commit)."""
    obj = ls_doc()
    if obj is None:
        print('[LICH SU] chua co file lich su -> bo qua (file goc duoc tao 1 lan tu lich su git)')
        return False
    if obj.get('v') != LS_V or obj.get('moc') != LS_MOC:
        print('[LICH SU] file lich su khac dinh dang (v=%s, moc=%s) -> KHONG ghi de' % (obj.get('v'), obj.get('moc')))
        return False
    d0 = datetime.date.fromisoformat(obj['d0'])
    i = ls_o(luc, d0)
    if i < obj.get('dn', 0):
        print('[LICH SU] lan quet cu hon du lieu da co -> bo qua'); return False
    n_truoc = obj.get('n', 0)
    if n_truoc and len(kho_map) < LS_NGUONG * n_truoc:
        print('[LICH SU] CANH BAO: chi doc duoc %d ma (lan truoc %d) -> nghi Sheet doc thieu, KHONG ghi lich su'
              % (len(kho_map), n_truoc))
        return False
    h = obj.setdefault('h', {})
    doi = 0
    for sku, v in kho_map.items():
        if isinstance(v, list):
            k1 = max(int(v[0] or 0), 0); k2 = max(int(v[1] or 0), 0) if len(v) > 1 else 0
        else:
            k1, k2 = max(int(v or 0), 0), 0
        a = h.get(sku)
        if not a:
            h[sku] = [i, k1, k2]; doi += 1; continue
        if a[-3] == i:                                  # da co diem o MOC NAY -> lan quet sau thang
            if a[-2] != k1 or a[-1] != k2:
                a[-2], a[-1] = k1, k2; doi += 1
                if len(a) >= 6 and a[-5] == k1 and a[-4] == k2:   # quay ve dung gia tri moc truoc -> bo diem
                    del a[-3:]
        elif a[-2] != k1 or a[-1] != k2:                # moc moi va ton doi -> them diem
            a.extend([i, k1, k2]); doi += 1
    if not doi:
        print('[LICH SU] khong doi'); return False
    obj['dn'] = max(i, obj.get('dn', 0))
    obj['n'] = len(kho_map)
    ls_ghi(obj)
    print('[LICH SU] %s -> moc %s: %d ma doi ton | tong %d ma | %d KB'
          % (luc.strftime('%d/%m %H:%M'), ls_gio(LS_MOC[i % len(LS_MOC)]), doi, len(h), os.path.getsize(LS_FILE) // 1024))
    return True

def ls_chay(kho_map):
    """Goi tu 2 cho (co doi / khong doi ton). Khong bao gio nem loi ra ngoai."""
    try:
        luc = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
        if ls_cap_nhat(kho_map, luc):
            import subprocess
            subprocess.run(['git', 'add', LS_FILE], check=False)
    except Exception as e:
        print('[LICH SU] LOI (bo qua, ton kho van cap nhat binh thuong):', type(e).__name__, e)

# ---- 1b. Bo qua neu ton kho KHONG doi (tranh commit rac moi 15 phut) ----
# mat khau cung nam trong fingerprint -> doi PW_NB/PW_KH la file duoc tao lai ngay
# 'v2' = doi cach xu ly ton AM (am -> 0 cho ban khach). Doi chuoi nay se ep tao lai file
# du ton kho khong thay doi.
_pw_tag = hashlib.sha256((PW_KH + '|' + PW_NB + '|' + NB_SECRET + '|v2').encode()).hexdigest()
fingerprint = hashlib.sha256(json.dumps([stock, kho, _pw_tag], sort_keys=True).encode()).hexdigest()
HASH_FILE = 'tonkho.hash'
if os.path.exists(HASH_FILE):
    try:
        if open(HASH_FILE).read().strip() == fingerprint:
            print('Ton kho KHONG doi so voi lan truoc -> khong tao file moi.')
            print('  (Neu Google Sheet ro rang da doi ma van thay dong nay, nghia la link Apps Script'
                  ' dang tra ve du lieu cu hoac doc nham tab.)')
            ls_chay(kho or stock)          # lan ghi truoc loi thi lan nay ghi bu (khong doi thi khong ghi gi)
            sys.exit(0)
    except Exception:
        pass

# ---- 2. Ma hoa 2 lop (khach / noi bo) ----
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# khach: ton > 20 -> "Con hang" (-1); ton AM coi nhu HET (0) -> hien "Lien he"
stock_kh = {k: (-1 if v > 20 else max(v, 0)) for k, v in stock.items()}

salt = os.urandom(16)
k_kh = hashlib.pbkdf2_hmac('sha256', PW_KH.encode(), salt, 200000, 32)
k_nb = hashlib.pbkdf2_hmac('sha256', NB_SECRET.encode(), salt, 200000, 32)   # ton kho that
k_pw = hashlib.pbkdf2_hmac('sha256', PW_NB.encode(), salt, 200000, 32)      # mo NB_SECRET
i1, i2, i3 = os.urandom(12), os.urandom(12), os.urandom(12)
b = lambda x: base64.b64encode(x).decode()

vn_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))   # gio Viet Nam
data = {
    'date': vn_now.strftime('%d/%m/%Y %H:%M'),
    's':  b(salt),
    'i1': b(i1), 'c1': b(AESGCM(k_kh).encrypt(i1, json.dumps(stock_kh, ensure_ascii=False).encode(), None)),
    'i2': b(i2), 'c2': b(AESGCM(k_nb).encrypt(i2, json.dumps(kho or stock, ensure_ascii=False).encode(), None)),
    # c3 = NB_SECRET khoa bang MAT KHAU NOI BO. Doi mat khau: sua Secret PW_NB -> Run workflow.
    'i3': b(i3), 'c3': b(AESGCM(k_pw).encrypt(i3, NB_SECRET.encode(), None)),
}
with open('tonkho.json', 'w', encoding='utf-8') as f:
    json.dump(data, f)

with open(HASH_FILE, 'w') as f:
    f.write(fingerprint)

print(f"Da tao tonkho.json ({os.path.getsize('tonkho.json')//1024} KB) luc {data['date']}")

# ---- 3. Lich su ton kho (sau cung - loi o day khong anh huong tonkho.json da ghi) ----
ls_chay(kho or stock)
