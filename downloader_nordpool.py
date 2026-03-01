import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CREDENTIALS CONFIGURATION ---
USER = "hfs2@alumnes.udl.cat"
PASS = "Emmajana-03"
FOLDER = "ExcelFiles"

def setup_driver():
    """Initializes the Chrome driver with specific download preferences."""
    if not os.path.exists(FOLDER):
        os.makedirs(FOLDER)
    
    chrome_options = Options()
    prefs = {
        "download.default_directory": os.path.abspath(FOLDER),
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--start-maximized")
    
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def automate_nordpool():
    """Automates the login and data download process from Nord Pool."""
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)
    
    try:
        # 1. LOGIN
        print("🔐 Accessing Login page...")
        driver.get("https://sso.nordpoolgroup.com/login")
        
        # Wait for input fields to be clickable
        user_input = wait.until(EC.element_to_be_clickable((By.ID, "username")))
        pass_input = driver.find_element(By.ID, "password")
        
        user_input.send_keys(USER)
        pass_input.send_keys(PASS)
        
        # Click Sign In
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        print("⏳ Authenticating...")
        time.sleep(5) # Allow time for SSO processing and redirection

        # 2. NAVIGATE TO DATA URL
        # Note: This URL includes specific delivery areas and the start date for 2025
        data_url = "https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate=2025-01-01&currency=EUR&aggregation=DeliveryPeriod&deliveryAreas=EE,LT,LV,AT,BE,FR,GER,NL,PL,DK1,DK2,FI,NO1,NO2,NO3,NO4,NO5,SE1,SE2,SE3,SE4,BG,TEL,SYS"
        print("🌐 Navigating to data table...")
        driver.get(data_url)
        
        # 3. HANDLE COOKIES (If they reappear after login)
        try:
            cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Allow')]")))
            cookie_btn.click()
            print("✅ Cookies accepted.")
        except:
            print("ℹ️ Cookie banner not found.")

        # 4. DOWNLOAD DATA
        print("🖱️ Searching for Download button...")
        time.sleep(5) # Extra wait for the dynamic table to load
        
        # Locate the Download button by its text
        download_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Download')]")))
        driver.execute_script("arguments[0].scrollIntoView(true);", download_btn)
        time.sleep(1)
        download_btn.click()
        
        # Select CSV format from the dropdown
        print("📄 Selecting CSV format...")
        csv_option = wait.until(EC.element_to_be_clickable((By.XPATH, "//li[contains(., 'CSV')] | //button[contains(., 'CSV')]")))
        csv_option.click()

        print(f"🚀 Download started in '{FOLDER}'. Waiting 10s for completion...")
        time.sleep(10)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        driver.save_screenshot("automation_error.png")
    
    finally:
        driver.quit()
        print("🔌 Browser closed.")

if __name__ == "__main__":
    automate_nordpool()