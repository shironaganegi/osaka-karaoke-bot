import os

file_path = r'website\layouts\partials\head.html'
with open(file_path, 'rb') as f:
    content = f.read()

print(f"File size: {len(content)}")
if b'partial " author.html"' in content:
    print("CRITICAL: Found space in ' author.html'")
else:
    print("SUCCESS: ' author.html' NOT found")

if b'partial "author.html"' in content:
    print("Found correct 'author.html'")
else:
    print("Correct 'author.html' NOT found")
