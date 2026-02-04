import requests
import re
import json

def check_tiktok_profile(username):
    """Cek profil TikTok tanpa library khusus"""
    url = f"https://www.tiktok.com/@{username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        print(f"Mengakses: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            
            # Coba beberapa pola pencarian data JSON
            patterns = [
                r'<script id="SIGI_STATE" type="application/json">(.*?)</script>',
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
                r'window\[\'SIGI_STATE\'\]\s*=\s*({.*?});',
                r'"userInfo":({.*?})',
            ]
            
            json_data = None
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        json_data = json.loads(json_str)
                        print(f"✓ Data ditemukan dengan pattern: {pattern[:50]}...")
                        break
                    except json.JSONDecodeError:
                        continue
            
            if json_data:
                # Simpan semua data ke file
                with open(f'tiktok_{username}_full.json', 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                print(f"✓ Data lengkap disimpan di: tiktok_{username}_full.json")
                
                # Coba ekstrak info user
                user_info = None
                
                # Coba beberapa kemungkinan struktur
                if 'UserModule' in json_data and 'users' in json_data['UserModule']:
                    for key, user in json_data['UserModule']['users'].items():
                        if username.lower() in key.lower():
                            user_info = user
                            break
                
                if not user_info and 'UserPage' in json_data:
                    user_info = json_data['UserPage'].get('userInfo', {})
                
                if user_info:
                    print("\n=== PROFIL TIKTOK ===")
                    print(f"Username: @{user_info.get('uniqueId', username)}")
                    print(f"Nickname: {user_info.get('nickname', 'N/A')}")
                    print(f"Following: {user_info.get('following', user_info.get('followingCount', 'N/A'))}")
                    print(f"Followers: {user_info.get('follower', user_info.get('followerCount', 'N/A'))}")
                    print(f"Likes: {user_info.get('heart', user_info.get('heartCount', 'N/A'))}")
                    print(f"Video Count: {user_info.get('videoCount', 'N/A')}")
                    print(f"Bio: {user_info.get('signature', 'N/A')}")
                    print(f"Verified: {user_info.get('verified', 'N/A')}")
                else:
                    print("ℹ️ Struktur data berbeda. Lihat file JSON untuk detail.")
                    
            else:
                print("✗ Tidak menemukan data JSON dalam halaman")
                # Simpan HTML untuk debugging
                with open(f'tiktok_{username}_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html[:5000])  # Simpan sebagian
                print(f"✓ HTML disimpan untuk debugging: tiktok_{username}_debug.html")
                
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")

if __name__ == "__main__":
    # Test dengan username yang diminta
    check_tiktok_profile("dikacstro")