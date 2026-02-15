import re

def extract_price_context_aware(text):
    """
    Extract prices based on time context (e.g., 11:00~18:00).
    Returns: (mem_30, gen_30, mem_free, gen_free)
    """
    lines = text.split('\n')
    
    # regex for time range (e.g., 11:00 ~ 18:00)
    price_pattern = re.compile(r'(\d{3,4})')
    
    current_block = "unknown" # morning, day, night
    
    mem_30, gen_30 = None, None
    mem_free, gen_free = None, None

    # Track prices found in "Day" block
    day_30_candidates = []
    day_free_candidates = []

    for i, line in enumerate(lines):
        # Detect Block
        # Look for "11:00" or "10:00" to "18:00" or "19:00"
        # OCR garbles: "⑪:00", "①⑧:00"
        line_clean = line.replace("⑪", "11").replace("①⑧", "18").replace("①", "1").replace("⑧", "8")
        
        if ("11:00" in line_clean or "10:00" in line_clean) and ("18:00" in line_clean or "19:00" in line_clean):
            current_block = "day"
            print(f"DEBUG: Found DAY block at line {i}: {line.strip()}")
            continue
        elif "18:00" in line_clean and ("23:00" in line_clean or "0:00" in line_clean or "5:00" in line_clean or "7:00" in line_clean):
            current_block = "night"
            print(f"DEBUG: Found NIGHT block at line {i}: {line.strip()}")
            continue
        elif "7:00" in line_clean and "11:00" in line_clean:
            current_block = "morning"
            continue

        if current_block == "day":
            # 30min
            if "30分" in line or "30min" in line:
                prices = price_pattern.findall(line.replace(" ", "").replace(",", ""))
                # Filter unreasonable
                valid = [int(p) for p in prices if 50 <= int(p) <= 2000]
                if valid:
                     day_30_candidates.extend(valid)
                     print(f"DEBUG: Found 30min candidates: {valid}")
            
            # Free Time
            line_no_space = line.replace(" ", "")
            if "フリー" in line_no_space or "Free" in line_no_space or "フリ-" in line_no_space or "フリ—" in line_no_space:
                prices = price_pattern.findall(line_no_space.replace(",", "")) # current line
                
                # Check next line too
                if i+1 < len(lines):
                    next_line = lines[i+1].replace(" ", "").replace(",", "")
                    prices_next = price_pattern.findall(next_line)
                    prices.extend(prices_next)

                valid = [int(p) for p in prices if 500 <= int(p) <= 3000]
                if valid:
                    day_free_candidates.extend(valid)
                    print(f"DEBUG: Found Free Time candidates: {valid}")


    # Resolve candidates
    print(f"DEBUG: Final Day 30 candidates: {day_30_candidates}")
    print(f"DEBUG: Final Day Free candidates: {day_free_candidates}")

    if len(day_30_candidates) >= 2:
        c1, c2 = day_30_candidates[0], day_30_candidates[1]
        if c1 < c2:
            mem_30, gen_30 = c1, c2
        else:
            mem_30, gen_30 = c2, c1
    elif len(day_30_candidates) == 1:
        mem_30 = day_30_candidates[0]
        gen_30 = int(mem_30 * 1.3)

    if len(day_free_candidates) >= 2:
        # Dedupe
        day_free_candidates = sorted(list(set(day_free_candidates)))
        # Filter out 800 if 1300 is present?
        # member < general
        if len(day_free_candidates) >= 2:
             # Just take first two? Smallest first?
             mem_free, gen_free = day_free_candidates[0], day_free_candidates[1]
    
    return mem_30, gen_30, mem_free, gen_free

if __name__ == "__main__":
    with open("namba_hips_ocr.txt", "r", encoding="utf-8") as f:
        text = f.read()
    
    m30, g30, mf, gf = extract_price_context_aware(text)
    print(f"\nResult: 30min={m30}/{g30}, Free={mf}/{gf}")
