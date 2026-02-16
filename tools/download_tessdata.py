
import requests
import os

def download_file(url, local_path):
    print(f"Downloading {url} to {local_path}...")
    try:
        r = requests.get(url, allow_redirects=True, stream=True)
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                 f.write(chunk)
        print(f"Done. Size: {os.path.getsize(local_path)} bytes")
    except Exception as e:
        print(f"Failed: {e}")

os.makedirs("tessdata", exist_ok=True)
download_file("https://github.com/tesseract-ocr/tessdata/raw/main/jpn.traineddata", "tessdata/jpn.traineddata")
# download_file("https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata", "tessdata/eng.traineddata")
