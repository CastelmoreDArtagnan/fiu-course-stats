import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://analytics.fiu.edu/t/AIMAccountability/views/CoursePerformanceDashboard/GradeDistributionDashboard?iframeSizedToWindow=true&%3Aembed=y"

def run_root_diagnostic():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        print("Launching diagnostic window... Loading FIU portal...")
        driver.get(TARGET_URL)
        time.sleep(15) # Wait for all custom FIU React components to fully render
        
        print("Scanning ROOT document directly (ignoring decoy iframes)...")
        
        # Grab everything that has text, an ARIA accessibility label, a title tooltip, or acts as a button
        elements = driver.find_elements(By.XPATH, "//*[string-length(normalize-space(text())) > 0 or @aria-label or @title or @role='button']")
        
        log_entries = []
        for index, elem in enumerate(elements):
            try:
                tag = elem.tag_name
                elem_aria = elem.get_attribute("aria-label") or ""
                elem_title = elem.get_attribute("title") or ""
                text = elem.text.strip().replace('\n', ' | ')[:60]
                
                # Filter out pure garbage tags to keep the map clean
                if text or elem_aria or elem_title:
                    log_entries.append(f"[{index}] TAG: <{tag}> | ARIA: '{elem_aria}' | TITLE: '{elem_title}' | TEXT: '{text}'")
            except:
                continue 
        
        log_file = "tableau_root_map.txt"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(log_entries))
            
        print(f"\nScan complete! Found {len(log_entries)} visual items on the root layer.")
        print(f"Please look for a new file in your workspace named: {log_file}")

    except Exception as e:
        print(f"Diagnostic failed midway: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_root_diagnostic()