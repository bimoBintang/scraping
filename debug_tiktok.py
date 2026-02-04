import requests
import json
import re
import time

def debug_tiktok_profile(username):
    print("=" * 60)
    print(f"DEBUG TIKTOK PROFILE: @{username}")
    print("=" * 60)
    
    url = f"https://www.tiktok.com/@{username}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    print(f"\n1. MENGIRIM REQUEST KE: {url}")
    print(f"   Headers: {headers}")
    
    try:
        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=15)
        elapsed_time = time.time() - start_time
        
        print(f"\n2. RESPONSE DITERIMA:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Time: {elapsed_time:.2f} detik")
        print(f"   Content Length: {len(response.text)} karakter")
        print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
        
        # Cek jika redirect
        if response.history:
            print(f"   Redirect dari: {response.history[0].url}")
        
        # Simpan raw HTML untuk inspeksi
        html = response.text
        with open(f'debug_{username}_raw.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n3. RAW HTML DISIMPAN: debug_{username}_raw.html")
        
        # Analisis HTML
        print(f"\n4. ANALISIS HTML:")
        print(f"   - Title tag: {extract_title(html)}")
        print(f"   - Script tags: {html.count('<script')} ditemukan")
        print(f"   - JSON patterns dalam HTML:")
        
        # Cari semua JSON patterns
        json_patterns = {
            'SIGI_STATE': r'<script id="SIGI_STATE" type="application/json">(.*?)</script>',
            'UNIVERSAL_DATA': r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
            'window.SIGI_STATE': r'window\[\'SIGI_STATE\'\]\s*=\s*({.*?});',
            'userInfo': r'"userInfo":({.*?})',
            'props":': r'"props":({.*?})',
        }
        
        found_data = {}
        for name, pattern in json_patterns.items():
            match = re.search(pattern, html, re.DOTALL)
            if match:
                print(f"     ✓ {name}: DITEMUKAN")
                json_str = match.group(1)
                try:
                    data = json.loads(json_str)
                    found_data[name] = data
                    
                    # Simpan data JSON terpisah
                    filename = f'debug_{username}_{name.lower()}.json'
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"       Data disimpan: {filename}")
                    
                    # Cek struktur data
                    print(f"       Struktur data: {list(data.keys())[:5]}...")
                    
                except json.JSONDecodeError as e:
                    print(f"     ✗ {name}: JSON ERROR - {e}")
                    # Simpan string mentah untuk debug
                    with open(f'debug_{username}_{name.lower()}_raw.txt', 'w', encoding='utf-8') as f:
                        f.write(json_str[:500])
            else:
                print(f"     ✗ {name}: TIDAK DITEMUKAN")
        
        # Cek apakah ada error message
        if "Account banned" in html:
            print("\n⚠️  AKUN DIBANNED")
        elif "This page is not available" in html:
            print("\n⚠️  HALAMAN TIDAK TERSEDIA")
        elif "private" in html.lower():
            print("\n⚠️  AKUN PRIVATE")
        
        # Ekstrak info dasar dari HTML
        extract_basic_info(html, username)
        
        # Coba API endpoint
        print(f"\n5. MENCOBA API ENDPOINT:")
        test_api_endpoints(username)
        
        print(f"\n" + "=" * 60)
        print("FILE YANG DIHASILKAN:")
        print("=" * 60)
        print(f"1. debug_{username}_raw.html       - HTML lengkap")
        for name in json_patterns.keys():
            if name.lower() in [f.lower() for f in found_data.keys()]:
                print(f"2. debug_{username}_{name.lower()}.json - Data JSON {name}")
        
    except requests.exceptions.Timeout:
        print("\n✗ TIMEOUT: Request terlalu lama")
    except requests.exceptions.ConnectionError:
        print("\n✗ CONNECTION ERROR: Tidak bisa terhubung")
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {str(e)}")

def extract_title(html):
    """Ekstrak title dari HTML"""
    match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
    if match:
        return match.group(1)
    return "No title found"

def extract_basic_info(html, username):
    """Ekstrak info dasar dari HTML"""
    print(f"\n6. INFO DASAR DARI HTML:")
    
    # Cari nickname
    nickname_match = re.search(r'"nickname":"(.*?)"', html)
    if nickname_match:
        print(f"   Nickname: {nickname_match.group(1)}")
    
    # Cari follower count
    follower_match = re.search(r'"followerCount":"?(\d+)"?', html)
    if follower_match:
        print(f"   Followers: {follower_match.group(1)}")
    
    # Cari following count
    following_match = re.search(r'"followingCount":"?(\d+)"?', html)
    if following_match:
        print(f"   Following: {following_match.group(1)}")
    
    # Cari video count
    video_match = re.search(r'"videoCount":"?(\d+)"?', html)
    if video_match:
        print(f"   Videos: {video_match.group(1)}")
    
    # Cari signature/bio
    bio_match = re.search(r'"signature":"(.*?)"', html)
    if bio_match:
        bio = bio_match.group(1).replace('\\n', ' ').replace('\\"', '"')
        print(f"   Bio: {bio[:100]}...")

def test_api_endpoints(username):
    """Test berbagai API endpoint TikTok"""
    endpoints = [
        f"https://www.tiktok.com/api/user/detail/?uniqueId={username}",
        f"https://m.tiktok.com/api/user/detail/?uniqueId={username}",
        f"https://t.tiktok.com/api/user/detail/?uniqueId={username}",
    ]
    
    for api_url in endpoints:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(api_url, headers=headers, timeout=5)
            print(f"   {api_url.split('//')[1][:30]}...: HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                filename = f'debug_{username}_api_{api_url.split("//")[1].split("/")[0]}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f"     Data disimpan: {filename}")
                
        except Exception as e:
            print(f"   {api_url.split('//')[1][:30]}...: ERROR - {type(e).__name__}")

# Versi sederhana langsung
def simple_check(username):
    print("\n" + "=" * 60)
    print("SIMPLE CHECK - Langsung cari pola umum")
    print("=" * 60)
    
    url = f"https://www.tiktok.com/@{username}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # Simpan HTML
        with open('simple_check.html', 'w', encoding='utf-8') as f:
            f.write(response.text[:5000])
        
        print("5000 karakter pertama HTML disimpan di: simple_check.html")
        print("\nContoh isi HTML:")
        print("-" * 40)
        print(response.text[:2000])
        print("-" * 40)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    username = "mdqiv_"
    
    # Pilih metode
    print("Pilih metode:")
    print("1. Debug lengkap (rekomendasi)")
    print("2. Simple check (cepat)")
    choice = input("Masukkan pilihan (1/2): ").strip()
    
    if choice == "2":
        simple_check(username)
    else:
        debug_tiktok_profile(username)
    
    print("\n📁 Semua file debug dimulai dengan 'debug_' atau 'simple_'")