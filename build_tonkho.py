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
print(f'Doc duoc {len(stock)} ma tu Google Sheet' + (f' (co chi tiet 2 kho: {len(kho)} ma)' if kho else ' (chi co tong ton)'))
# Dau van tay CUA RIENG DU LIEU SHEET - de biet Sheet co that su doi hay khong
_fp_sheet = hashlib.sha256(json.dumps([stock, kho], sort_keys=True).encode()).hexdigest()[:12]
print('Dau van tay du lieu Sheet:', _fp_sheet)
print('Vai ma dau:', list(stock.items())[:5])
print('Tong ton toan bo:', sum(stock.values()))

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
