import os
import time
import requests
import pandas as pd
import urllib.parse
from io import BytesIO

# --- 1. YOUR AUTHENTICATION ---
# NOTE: If your PC was asleep for a few hours, your FIU session may have expired.
# If the script immediately fails, grab fresh cookies/tokens from Chrome and paste them here!
COOKIES = {
    '_fbp': 'fb.1.1761681956286.958659439244320117',
    '_ga': 'GA1.1.949160903.1761581596',
    'tableau_locale': 'en',
    'XSRF-TOKEN': 'bg7iPP49quSpwZGeD6j7OYTrgXeWawoy', 
}

HEADERS = {
    'Accept': 'text/csv',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'X-Tableau-Version': '2024.2',
    'X-XSRF-TOKEN': 'bg7iPP49quSpwZGeD6j7OYTrgXeWawoy',
}

MASTER_FILE_PATH = "fiu_master_grade_distribution.csv"
TXT_FILE_PATH = "professor_list.txt"

# --- 2. RESUME SETTINGS ---
# The script will start extracting at this exact item number in your text file.
START_AT_ITEM = 487 
# The script will stop after this item number (Leave as None to go to the very end of the file)
STOP_AT_ITEM = 2027 

def load_professors_from_file():
    if not os.path.exists(TXT_FILE_PATH):
        print(f"CRITICAL ERROR: Could not find '{TXT_FILE_PATH}'.")
        return []
        
    with open(TXT_FILE_PATH, 'r', encoding='utf-8') as f:
        professors = [line.strip() for line in f if line.strip()]
        
    return professors

def download_and_merge():
    professor_list = load_professors_from_file()
    
    if not professor_list:
        return 

    # Calculate the exact slice of the list we need to process
    slice_start = START_AT_ITEM - 1
    slice_end = STOP_AT_ITEM if STOP_AT_ITEM else len(professor_list)
    working_list = professor_list[slice_start:slice_end]

    base_url = "https://bigdataonline.fiu.edu/t/AIMAccountability/views/CoursePerformanceDashboard/GradeDistributionDashboard.csv"
    
    print(f"Resuming extraction from item {START_AT_ITEM} to {slice_end}...")
    print("Initiating Lightning API Scraper...\n")
    
    success_count = 0
    fail_count = 0
    skipped_count = 0

    for index, name in enumerate(working_list):
        # Calculate the actual visual number for the print statement
        actual_item_number = START_AT_ITEM + index
        print(f"[{actual_item_number}/{len(professor_list)}] Fetching data for: {name}...")
        
        encoded_name = urllib.parse.quote(name)
        target_url = f"{base_url}?Instructor%20Name={encoded_name}"
        
        try:
            response = requests.get(target_url, headers=HEADERS, cookies=COOKIES)
            
            if response.status_code == 200:
                if "<html" in response.text[:20].lower():
                    print("\nCRITICAL ERROR: FIU Server returned a login webpage.")
                    print("Your session cookies have expired while the PC was asleep. Please update them!")
                    break
                
                # Enforcing strict string types prevents Pandas indexing/conversion crashes
                df = pd.read_csv(BytesIO(response.content), dtype=str)
                
                df['Professor'] = name
                
                if not os.path.exists(MASTER_FILE_PATH):
                    df.to_csv(MASTER_FILE_PATH, index=False)
                else:
                    df.to_csv(MASTER_FILE_PATH, mode='a', header=False, index=False)
                
                success_count += 1
                
            else:
                print(f"  -> Error: Server returned status {response.status_code}")
                fail_count += 1
                
        except pd.errors.EmptyDataError:
            print(f"  -> Skipped: FIU database has no historic grades for {name}.")
            skipped_count += 1
        except Exception as e:
            print(f"  -> Failed: Data processing error for {name}: {e}")
            fail_count += 1
            
        time.sleep(0.5)

    print(f"\n--- BATCH EXTRACTION COMPLETE ---")
    print(f"Successfully processed and merged: {success_count} professors")
    print(f"Skipped (No Data): {skipped_count}")
    print(f"Failed (Server/Code Error): {fail_count}")

if __name__ == "__main__":
    download_and_merge()