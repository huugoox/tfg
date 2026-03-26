import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DOWNLOAD_PATH = r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool\ExcelFilesNoProcessed\Volumes\2020"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

def wait_for_new_file(path, initial_count, timeout=30):
    """Espera a que aparezca un nuevo archivo y desaparezcan los temporales"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_files = os.listdir(path)
        # Si hay más archivos que al inicio y ninguno es un temporal .crdownload
        if len(current_files) > initial_count and not any(f.endswith('.crdownload') for f in current_files):
            return True
        time.sleep(1)
    return False

def run_extractor():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)
    
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_PATH
        }
    )

    current_date = datetime(2020, 5, 30)
    end_date = datetime(2020, 12, 31)
    
    areas = "EE,LT,LV,AT,BE,FR,GER,NL,DK1,DK2,FI,NO1,NO2,NO3,NO4,NO5,SE1,SE2,SE3,SE4"

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        # Prices
        #url = f"https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate={date_str}&currency=EUR&aggregation=DeliveryPeriod&deliveryAreas={areas}"
        # Volumes 
        url = f"https://data.nordpoolgroup.com/auction/day-ahead/volumes?deliveryDate={date_str}&deliveryAreas={areas}"

        
        print(f"📅 Procesando: {date_str}", end="\r")
        
        try:
            driver.get(url)
            initial_count = len(os.listdir(DOWNLOAD_PATH))

            # 1. Esperar a que el botón exista y sea visible
            btn_id = "export-excel-button"
            export_btn = wait.until(EC.element_to_be_clickable((By.ID, btn_id)))
            
            # 2. Pequeña pausa para que la web procese los datos internos
            time.sleep(2) 
            
            # 3. Clic mediante JavaScript (más fiable en esta web)
            driver.execute_script("arguments[0].click();", export_btn)
            
            time.sleep(2) 
            
            current_date += timedelta(days=1)
                
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}. Reintentando en 5s...")
            time.sleep(5)

    print("\n🏁 ¡Proceso completado!")

if __name__ == "__main__":
    run_extractor()