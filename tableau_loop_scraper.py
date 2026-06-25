import os
import time
import glob
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TARGET_URL = "https://analytics.fiu.edu/t/AIMAccountability/views/CoursePerformanceDashboard/GradeDistributionDashboard?iframeSizedToWindow=true&%3Aembed=y"
DOWNLOAD_DIR = os.path.join(os.getcwd(), "temp_downloads")
MASTER_FILE_PATH = "fiu_master_grade_distribution.csv"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def setup_browser():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.maximize_window()
    return driver

def human_hover_and_click(driver, element):
    """Scrolls to the element, physically hovers to wake up React listeners, and clicks."""
    # Scroll the element to the center of the screen so it isn't blocked by top/bottom menus
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
    time.sleep(1.5) # Wait for the smooth scroll animation to finish
    
    # Physically move the mouse, PAUSE to let the funnel icon render, then click
    actions = ActionChains(driver)
    actions.move_to_element(element).pause(1.5).click().perform()

def wait_for_download_and_rename(professor_name):
    print(f"Waiting for download to complete for: {professor_name}...")
    timeout = 45 
    seconds_passed = 0
    
    while seconds_passed < timeout:
        time.sleep(1)
        csv_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))
        crdownload_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.crdownload"))
        
        if csv_files and not crdownload_files:
            latest_file = max(csv_files, key=os.path.getctime)
            try:
                df = pd.read_csv(latest_file)
                df['Professor'] = professor_name 
                
                if not os.path.exists(MASTER_FILE_PATH):
                    df.to_csv(MASTER_FILE_PATH, index=False)
                else:
                    df.to_csv(MASTER_FILE_PATH, mode='a', header=False, index=False)
                
                print(f"Successfully processed and merged data for {professor_name}.")
                os.remove(latest_file)
                return True
                
            except Exception as e:
                print(f"Error processing CSV: {e}")
                return False
                
        seconds_passed += 1
    
    print(f"Download timed out for {professor_name}.")
    return False

def execute_automation():
    driver = setup_browser()
    wait = WebDriverWait(driver, 60) 
    
    try:
        print("Navigating to Dashboard...")
        driver.get(TARGET_URL)
        time.sleep(30) 

        # 1. Open the filter sidebar
        print("Opening the filter sidebar...")
        filter_toggle = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@title, 'Vertical Container')] | //div[contains(@aria-label, 'Vertical Container')]")))
        human_hover_and_click(driver, filter_toggle)
        time.sleep(5) 

        # 2. Open the Instructor Name filter explicitly
        print("Hovering to wake up the Instructor dropdown...")
        instructor_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h3[@title='Instructor Name']")))
        # In Tableau, the clickable filter box is usually the first button right after the header
        instructor_dropdown_box = instructor_header.find_element(By.XPATH, "./following::button[1]")
        
        human_hover_and_click(driver, instructor_dropdown_box)
        time.sleep(5) 

        # 3. Harvest professor names
        print("Harvesting professor names...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[text()='(All)']")))
        
        list_items = driver.find_elements(By.XPATH, "//*[@role='checkbox'] | //div[contains(@class, 'tab-tv-node')] | //*[text()='(All)']/following::span")
        professor_names = [elem.text.strip() for elem in list_items if elem.text.strip()]
        
        valid_professors = [name for name in professor_names if name and name != "(All)" and "," in name]
        valid_professors = list(dict.fromkeys(valid_professors)) 
        print(f"Discovered {len(valid_professors)} currently visible professors.")

        if len(valid_professors) == 0:
            raise Exception("Zero professors found. The filter list did not expand.")

        test_run_list = valid_professors[:3]
        print(f"Executing trial run on: {test_run_list}")

        # 4. Deselect "(All)" to completely clear the board
        print("Deselecting '(All)'...")
        all_checkbox = driver.find_element(By.XPATH, "//*[text()='(All)']")
        human_hover_and_click(driver, all_checkbox)
        time.sleep(4)

        # 5. Sequential Extraction Loop
        for name in test_run_list:
            print(f"\n--- Checking Professor: {name} ---")
            
            # Select the current professor
            target_prof = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()=\"{name}\"]")))
            human_hover_and_click(driver, target_prof)
            time.sleep(6) # Wait for Tableau background calculation
            
            # Click the main visual canvas to lock in the filter and reveal the download button
            main_viz = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@aria-label, 'Data Visualization') or contains(@aria-label, 'Grade Distribution Report')]")))
            human_hover_and_click(driver, main_viz)
            time.sleep(2)
            
            # Initiate download sequence
            print("Triggering download...")
            download_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Download']")))
            human_hover_and_click(driver, download_btn)
            time.sleep(3)
            
            crosstab_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Crosstab')]")))
            human_hover_and_click(driver, crosstab_btn)
            time.sleep(4)

            # Handle secondary confirmation if required by server
            try:
                modal_confirm_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Download') and contains(@class, 'tab-')]")
                human_hover_and_click(driver, modal_confirm_btn)
            except:
                pass 
            
            wait_for_download_and_rename(name)
            
            # Re-open the Instructor menu to prep for the next loop
            print(f"Unchecking {name} to reset board...")
            filter_toggle = driver.find_element(By.XPATH, "//div[contains(@title, 'Vertical Container')] | //div[contains(@aria-label, 'Vertical Container')]")
            human_hover_and_click(driver, filter_toggle)
            time.sleep(4)
            
            # Deselect the completed professor
            target_prof = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()=\"{name}\"]")))
            human_hover_and_click(driver, target_prof)
            time.sleep(3)
            
        print(f"\nExtraction complete! Master file generated: {MASTER_FILE_PATH}")

    except Exception as e:
        print(f"\nCRASH DETECTED: {e}")
        driver.save_screenshot("crash_screenshot_v5.png")
        print("--> Saved 'crash_screenshot_v5.png'.")
    finally:
        driver.quit()
        if os.path.exists(DOWNLOAD_DIR) and not os.listdir(DOWNLOAD_DIR):
            try:
                os.rmdir(DOWNLOAD_DIR)
            except:
                pass

if __name__ == "__main__":
    execute_automation()