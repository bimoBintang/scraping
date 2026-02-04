import requests
import sys

username = "mdqiv_"
url = f"https://www.tiktok.com/@{username}"

print(f"Mengakses: {url}")
print("-" * 50)

try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content Length: {len(response.text)}")
    
    # Cek jika ada pesan error
    html_lower = response.text.lower()
    
    if "not available" in html_lower:
        print("❌ Halaman tidak tersedia")
    elif "private" in html_lower:
        print("🔒 Akun private")
    elif "banned" in html_lower:
        print("🚫 Akun banned")
    elif "suspended" in html_lower:
        print("⏸️ Akun suspended")
    elif len(response.text) < 1000:
        print("⚠️ HTML terlalu pendek, mungkin diblokir")
    else:
        print("✅ Halaman berhasil diakses")
        
        # Simpan 10 baris pertama
        lines = response.text.split('\n')
        with open('minimal_output.txt', 'w', encoding='utf-8') as f:
            for i, line in enumerate(lines[:20]):
                f.write(f"Line {i+1}: {line[:200]}\n")
        
        print("\n📄 20 baris pertama disimpan di: minimal_output.txt")
        
except Exception as e:
    print(f"❌ Error: {e}")