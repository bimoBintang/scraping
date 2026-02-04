# TikTok Scraper

Scraper profil dan following list TikTok menggunakan Python dengan Playwright browser automation.

## 📦 Instalasi

```bash
# Install dependencies
pip install requests playwright

# Install browser Chromium
playwright install chromium
```

## 🚀 Quick Start

```bash
# Ambil profil user
python tiktok_playwright.py username

# Ambil profil + simpan ke JSON
python tiktok_playwright.py username --save

# Ambil profil + daftar following (perlu cookies)
python tiktok_playwright.py username --following --cookies tiktok_cookies.json --save
```

## 🍪 Setup Cookies (Untuk Fitur Following)

TikTok memerlukan login untuk melihat daftar following. Ikuti langkah berikut:

### Langkah 1: Install Extension
- Chrome/Edge: Install [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
- Firefox: Install [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)

### Langkah 2: Login ke TikTok
1. Buka https://www.tiktok.com
2. Login dengan akun Anda

### Langkah 3: Export Cookies
1. Klik icon **Cookie-Editor** di browser (icon berbentuk cookie)
2. Klik tombol **Export** di bagian bawah
3. Pilih format **JSON** 
4. Cookies akan di-copy ke clipboard

### Langkah 4: Simpan ke File
1. Buat file baru: `tiktok_cookies.json`
2. Paste isi cookies
3. Simpan file

### Langkah 5: Gunakan dengan Scraper
```bash
python tiktok_playwright.py username --following --cookies tiktok_cookies.json
```

## 📖 Penggunaan Lengkap

### Scrape Profil

```bash
# Profil satu user
python tiktok_playwright.py charlidamelio

# Profil multiple users
python tiktok_playwright.py user1 user2 user3

# Simpan hasil ke JSON
python tiktok_playwright.py username --save
```

### Scrape Following List (Perlu Cookies)

```bash
# Ambil daftar following
python tiktok_playwright.py username --following --cookies tiktok_cookies.json

# Batasi jumlah following
python tiktok_playwright.py username --following --max 50 --cookies tiktok_cookies.json

# Simpan ke file
python tiktok_playwright.py username --following --save --cookies tiktok_cookies.json
```

### Mode Browser

```bash
# Mode Visible (DEFAULT - rekomendasi)
python tiktok_playwright.py username

# Mode Headless (bisa kena CAPTCHA)
python tiktok_playwright.py username --headless
```

## ⚙️ Opsi CLI

| Flag | Short | Deskripsi |
|------|-------|-----------|
| `--save` | `-s` | Simpan hasil ke file JSON |
| `--following` | `-f` | Ambil daftar following (perlu cookies) |
| `--cookies FILE` | `-c FILE` | Path ke file cookies JSON |
| `--max N` | `-m N` | Maksimal following (default: 100) |
| `--headless` | `-H` | Jalankan browser tanpa tampilan |
| `--debug` | `-d` | Simpan HTML untuk debugging |
| `--output DIR` | `-o DIR` | Direktori output |

## 📁 Output Files

```
tiktok_username.json          # Data profil
tiktok_username_following.json # Daftar following
debug_username_playwright.html # HTML debug (jika --debug)
```

## 📊 Contoh Output

### Profil JSON
```json
{
  "username": "tiktok",
  "nickname": "TikTok",
  "followers": 92800000,
  "following": 3,
  "likes": 453500000,
  "video_count": 1381,
  "bio": "One TikTok can make a big impact",
  "verified": true,
  "private": false
}
```

### Following JSON
```json
[
  {
    "username": "user1",
    "profile_url": "https://www.tiktok.com/@user1",
    "avatar": "https://..."
  }
]
```

## 🔧 Penggunaan Sebagai Library

```python
import asyncio
from tiktok_playwright import TikTokPlaywrightScraper

async def main():
    async with TikTokPlaywrightScraper(headless=False) as scraper:
        # Ambil profil
        profile = await scraper.get_profile("tiktok")
        print(profile)
        
        # Ambil following list
        following = await scraper.get_following("tiktok", max_count=50)
        print(f"Following: {len(following)} users")

asyncio.run(main())
```

## ⚠️ Catatan Penting

1. **Gunakan Mode Visible** - TikTok agresif memblokir headless browser
2. **Rate Limiting** - Jangan scrape terlalu cepat/banyak
3. **VPN** - Gunakan VPN jika sering kena rate limit
4. **CAPTCHA** - Jika muncul CAPTCHA, tunggu beberapa menit

## 📂 File dalam Project

| File | Deskripsi |
|------|-----------|
| `tiktok_playwright.py` | Scraper utama dengan Playwright |
| `tiktok_scraper.py` | Versi ringan dengan requests (tanpa browser) |
| `README.md` | Dokumentasi ini |

## 🛠️ Troubleshooting

### CAPTCHA Detected
```bash
# Gunakan mode visible
python tiktok_playwright.py username

# Tunggu beberapa menit sebelum retry
```

### Browser Not Found
```bash
# Install browser
playwright install chromium
```

### ModuleNotFoundError
```bash
pip install playwright requests
```

---
*Dibuat untuk keperluan edukasi. Gunakan dengan bertanggung jawab.*
