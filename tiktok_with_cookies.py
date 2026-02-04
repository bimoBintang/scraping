import requests
import json
import re

def get_tiktok_profile_with_cookies(username):
    url = f"https://www.tiktok.com/@{username}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    cookies = {
        'csrfToken': '81JMzb4n-QH7aFlVUbAiotBLTHGIFXGDpovw',
        # Cookie lainnya bisa ditambahkan jika ada
    }
    
    try:
        print(f"Mengakses profil: @{username}")
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Cari data JSON
            pattern = r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>'
            match = re.search(pattern, html, re.DOTALL)
            
            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                
                # Simpan semua data
                with open(f'tiktok_{username}_data.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"✓ Data disimpan: tiktok_{username}_data.json")
                
                # Ekstrak informasi user
                extract_user_info(data, username)
                
            else:
                # Coba pattern lain
                pattern2 = r'<script id="SIGI_STATE" type="application/json">(.*?)</script>'
                match2 = re.search(pattern2, html, re.DOTALL)
                
                if match2:
                    json_str = match2.group(1)
                    data = json.loads(json_str)
                    
                    with open(f'tiktok_{username}_sigi.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"✓ Data SIGI disimpan: tiktok_{username}_sigi.json")
                    
                    extract_sigi_info(data, username)
                else:
                    print("✗ Tidak menemukan data JSON")
                    # Debug: simpan sebagian HTML
                    with open(f'tiktok_{username}_debug.html', 'w', encoding='utf-8') as f:
                        f.write(html[:10000])
                    
        else:
            print(f"✗ Gagal mengakses: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")

def extract_user_info(data, username):
    """Ekstrak info dari format data baru"""
    try:
        # Coba berbagai struktur data
        user_data = None
        
        # Format 1: Default content
        if 'DefaultContent' in data:
            user_data = data['DefaultContent'].get('shareInfo', {})
        
        # Format 2: User detail
        if 'WebappUserDetail' in data:
            user_data = data['WebappUserDetail'].get('userInfo', {})
            
        if user_data:
            print("\n=== PROFIL TIKTOK ===")
            print(f"Username: @{user_data.get('uniqueId', username)}")
            print(f"Nickname: {user_data.get('nickname', 'N/A')}")
            print(f"Following: {format_number(user_data.get('followingCount'))}")
            print(f"Followers: {format_number(user_data.get('followerCount'))}")
            print(f"Likes: {format_number(user_data.get('heartCount'))}")
            print(f"Video Count: {format_number(user_data.get('videoCount'))}")
            print(f"Bio: {user_data.get('signature', 'N/A')[:100]}...")
            print(f"Verified: {user_data.get('verified', False)}")
            
            # Cek apakah private account
            if user_data.get('privateAccount', False):
                print("⚠️  PRIVATE ACCOUNT - Data terbatas")
                
    except Exception as e:
        print(f"Error extracting info: {e}")

def extract_sigi_info(data, username):
    """Ekstrak info dari format SIGI_STATE"""
    try:
        # Cari user dalam UserModule
        if 'UserModule' in data and 'users' in data['UserModule']:
            users = data['UserModule']['users']
            
            # Cari user dengan username yang cocok
            user_key = None
            for key in users.keys():
                if username.lower() in key.lower():
                    user_key = key
                    break
            
            if user_key:
                user_info = users[user_key]
                print("\n=== PROFIL TIKTOK (SIGI) ===")
                print(f"Username: @{user_info.get('uniqueId', username)}")
                print(f"Nickname: {user_info.get('nickname', 'N/A')}")
                print(f"Following: {format_number(user_info.get('following'))}")
                print(f"Followers: {format_number(user_info.get('follower'))}")
                print(f"Likes: {format_number(user_info.get('heart'))}")
                print(f"Video Count: {format_number(user_info.get('videoCount'))}")
                print(f"Bio: {user_info.get('signature', 'N/A')[:100]}...")
                print(f"Verified: {user_info.get('verified', False)}")
                
                # Cek stats tambahan
                if 'stats' in user_info:
                    stats = user_info['stats']
                    print(f"\n=== STATS DETAIL ===")
                    for key, value in stats.items():
                        print(f"{key}: {format_number(value)}")
            else:
                print("✗ User tidak ditemukan dalam data")
                
    except Exception as e:
        print(f"Error extracting SIGI info: {e}")

def format_number(num):
    """Format angka dengan K, M, B"""
    if not num:
        return 'N/A'
    
    try:
        num = int(num)
        if num >= 1000000000:
            return f"{num/1000000000:.1f}B"
        elif num >= 1000000:
            return f"{num/1000000:.1f}M"
        elif num >= 1000:
            return f"{num/1000:.1f}K"
        else:
            return str(num)
    except:
        return str(num)

# Fungsi untuk mendapatkan data via API
def get_tiktok_api(username):
    """Coba akses via TikTok API unofficial"""
    api_url = f"https://www.tiktok.com/api/user/detail/?uniqueId={username}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'https://www.tiktok.com/@{username}',
    }
    
    cookies = {
        'csrfToken': '81JMzb4n-QH7aFlVUbAiotBLTHGIFXGDpovw',
    }
    
    try:
        print(f"\n=== Mencoba API TikTok ===")
        response = requests.get(api_url, headers=headers, cookies=cookies, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            with open(f'tiktok_{username}_api.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✓ API Data disimpan: tiktok_{username}_api.json")
            
            if 'userInfo' in data:
                user = data['userInfo']
                print(f"API Result - Followers: {format_number(user.get('followerCount'))}")
                print(f"API Result - Following: {format_number(user.get('followingCount'))}")
                
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    username = "mdqiv_"
    
    # Method 1: Scrape website
    get_tiktok_profile_with_cookies(username)
    
    # Method 2: Try API
    get_tiktok_api(username)
    
    print("\n📁 File yang dihasilkan:")
    print(f"- tiktok_{username}_data.json (data utama)")
    print(f"- tiktok_{username}_sigi.json (data SIGI jika ada)")
    print(f"- tiktok_{username}_api.json (data API)")
    print(f"- tiktok_{username}_debug.html (debug jika perlu)")
    