import json
import sys

def check():
    files = ["manekineko_pdf_urls.json"]
    for fpath in files:
        print(f"--- Checking {fpath} ---")
        try:
            content = ""
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
            except UnicodeDecodeError:
                with open(fpath, 'r', encoding='utf-16') as f:
                    content = f.read().strip()
            
            if content:
                if content.endswith(","): content = content[:-1]
                if not content.endswith("]"): content += "]"
                data = json.loads(content)
                print(f"Count: {len(data)}")
                if len(data) > 0:
                    print("Sample:", json.dumps(data[0], ensure_ascii=True, indent=2))
            else:
                print("Empty file")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check()
