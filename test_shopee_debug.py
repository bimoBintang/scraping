"""Quick test: fresh session search - does it still work?"""
import asyncio
import logging
from shopee.browser import ShopeeBrowser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

async def test():
    print("=== Fresh Session Search Test ===\n")
    
    async with ShopeeBrowser(
        cookies_file='shopee/shopeeCookies.json', 
        headless=True,
        min_delay=2, 
        max_delay=4
    ) as sb:
        # Test 1: Simple search
        products = await sb.search("tinta epson 003", max_results=5)
        
        if products:
            print(f"Found {len(products)} products:\n")
            for i, p in enumerate(products, 1):
                price_str = f"Rp {p.price:,.0f}".replace(",", ".")
                print(f"  {i}. {p.name[:55]}")
                print(f"     {price_str} | ID:{p.item_id} | Shop:{p.shop_id}")
            print("\n✅ Search works!")
        else:
            print("❌ Search failed")

asyncio.run(test())
