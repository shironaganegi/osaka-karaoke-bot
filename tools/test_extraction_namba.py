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
        line_clean = line.replace("⑪", "11").replace("①⑧", "18").replace("①", "1").replace("⑧", "8")
        
        # New Time Block Detection (Reset if new start time found)
        # Regex for "H:00 ~"
        time_header_match = re.search(r'(\d{1,2})[:\s]00\s*~\s*', line_clean)
        if time_header_match:
            start_hour = int(time_header_match.group(1))
            
            # Day logic: Start 10 or 11. End 18 or 19.
            if start_hour in [10, 11] and ("18:00" in line_clean or "19:00" in line_clean):
                current_block = "day"
                print(f"DEBUG: Found DAY block at line {i}: {line.strip()}")
                continue
            elif start_hour in [6, 7] and ("11:00" in line_clean or "12:00" in line_clean):
                current_block = "morning"
                print(f"DEBUG: Found MORNING block at line {i}: {line.strip()}")
                continue
            elif start_hour >= 18 or start_hour == 23 or start_hour == 0:
                current_block = "night"
                print(f"DEBUG: Found NIGHT block at line {i}: {line.strip()}")
                continue
            elif start_hour == 15:
                # 15:00 is usually "Evening/Free Time B", distinct from Day
                current_block = "evening"
                print(f"DEBUG: Found EVENING block at line {i}: {line.strip()}")
                continue
            else:
                # Unknown block start
                current_block = "unknown"
        
        if current_block == "day":
            # 30min
            if "30分" in line or "30min" in line:
                # Try both raw and no-space
                raw_nums = price_pattern.findall(line.replace(",", ""))
                nospace_nums = price_pattern.findall(line.replace(" ", "").replace(",", ""))
                all_nums = raw_nums + nospace_nums
                valid = [int(p) for p in all_nums if 50 <= int(p) <= 2000]
                if valid:
                     day_30_candidates.extend(valid)
                     print(f"DEBUG: Found 30min candidates: {valid}")
            
            # Free Time
            line_norm = line.replace(" ", "")
            if "フリー" in line_norm or "Free" in line_norm or "フリ-" in line_norm or "フリ—" in line_norm:
                # Try both raw and no-space
                raw_nums = price_pattern.findall(line.replace(",", ""))
                nospace_nums = price_pattern.findall(line.replace(" ", "").replace(",", ""))
                current_nums = raw_nums + nospace_nums
                
                # Check next line too
                if i+1 < len(lines):
                    next_line = lines[i+1]
                    r_next = price_pattern.findall(next_line.replace(",", ""))
                    n_next = price_pattern.findall(next_line.replace(" ", "").replace(",", ""))
                    current_nums.extend(r_next + n_next)

                valid = [int(p) for p in current_nums if 500 <= int(p) <= 3000]
                if valid:
                    day_free_candidates.extend(valid)
                    print(f"DEBUG: Found Free Time candidates: {valid}")


    # Resolve candidates
    print(f"DEBUG: Final Day 30 candidates: {day_30_candidates}")
    print(f"DEBUG: Final Day Free candidates: {day_free_candidates}")

    # 30min Resolution with Diamond Check
    if len(day_30_candidates) >= 1:
        day_30_candidates = sorted(list(set(day_30_candidates)))
        
        # If lowest is very small (e.g. 105), assume Diamond/Student
        # Namba HIPS: 105, 150.
        if day_30_candidates[0] <= 120 and len(day_30_candidates) >= 2:
             # Skip the first one
             mem_30 = day_30_candidates[1] # 150
             # Estimate General
             if len(day_30_candidates) >= 3:
                 gen_30 = day_30_candidates[2]
             else:
                 gen_30 = int(mem_30 * 1.3) # Fallback
             print(f"DEBUG: Adjusted for Diamond. Mem={mem_30}, Gen={gen_30}")
        elif len(day_30_candidates) >= 2:
            mem_30, gen_30 = day_30_candidates[0], day_30_candidates[1]
        else:
            mem_30 = day_30_candidates[0]
            gen_30 = int(mem_30 * 1.3)
    
    # Free Time Resolution
    if len(day_free_candidates) >= 1:
        day_free_candidates = sorted(list(set(day_free_candidates)))
        # Filter garbage (e.g. 608 if it's likely a misread)
        # If we have [608, 800, 1300].
        # 608 is close to 660 (Diamond). 800 (Member). 1300 (General).
        # Member should be 800.
        
        # Heuristic: If we have > 2 candidates, middle is usually Member.
        # If we have 2 candidates... Low is Member, High is General?
        # Unless Low is Diamond.
        
        # Checking ratio with 30min Member (150).
        # 800 / 150 = 5.3. 
        # 608 / 150 = 4.0.
        # 1300 / 150 = 8.6.
        
        # If we decided Mem30 is 150.
        # We want MemFree ~ 5-7x Mem30. (750 - 1050).
        # 800 fits perfectly.
        
        best_mem_free = None
        
        if mem_30:
             # Find candidate closest to mem_30 * 6
             target = mem_30 * 6
             day_free_candidates.sort(key=lambda x: abs(x - target))
             best_mem_free = day_free_candidates[0]
             
             # General is usually higher
             # Find remaining candidates that are higher than best_mem_free
             gens = [x for x in day_free_candidates if x > best_mem_free]
             if gens:
                 best_gen_free = gens[0] # Smallest of the higher ones (next tier)
             else:
                 best_gen_free = int(best_mem_free * 1.3)
             
             mem_free, gen_free = best_mem_free, best_gen_free
        else:
             # Fallback default logic
             if len(day_free_candidates) >= 2:
                 mem_free, gen_free = day_free_candidates[0], day_free_candidates[1]
             else:
                 mem_free = day_free_candidates[0]
                 gen_free = int(mem_free * 1.3)
    
    return mem_30, gen_30, mem_free, gen_free

if __name__ == "__main__":
    with open("namba_hips_ocr.txt", "r", encoding="utf-8") as f:
        text = f.read()
    
    m30, g30, mf, gf = extract_price_context_aware(text)
    print(f"\nResult: 30min={m30}/{g30}, Free={mf}/{gf}")
