
import sys
sys.stdout.reconfigure(encoding='utf-8')
import re
import os

filepath = "website/public/stations/なんば/index.html"
if not os.path.exists(filepath):
    print(f"File not found: {filepath}")
    exit(1)

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

print(f"File size: {len(content)}")

matches = re.findall(r'<div class="store-card" data-chain="manekineko".*?</div>', content, re.DOTALL)
print(f"Found {len(matches)} Manekineko cards.")

for i, m in enumerate(matches):
    print(f"--- Card {i+1} ---")
    # Extract name (flexible)
    name_m = re.search(r'<h3 class="store-name">.*?</span>\s*(.*?)\s*</h3>', m, re.DOTALL)
    name = name_m.group(1).strip() if name_m else "Unknown Name"
    
    # Extract price (flexible) - finding the first price-value which is 30min
    # <span class="price-value">...</span>
    prices = re.findall(r'<span class="price-value">\s*(.*?)\s*</span>', m, re.DOTALL)
    price_30 = prices[0] if len(prices) > 0 else "Unknown Price"
    
    # Check PDF link
    has_pdf = "pdf-link" in m
    
    print(f"Store: {name}")
    print(f"Price (30min): {price_30}")
    print(f"Has PDF Link: {has_pdf}")
    print("-" * 20)
