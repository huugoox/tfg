import os
import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DOWNLOAD_PATH = r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\NordPoool\ExcelFilesNoProcessed\Flows\2020\NO4"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

def wait_for_new_file(path, initial_count, timeout=40):
    """Espera a que aparezca un nuevo archivo y desaparezcan los temporales."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_files = os.listdir(path)
        if len(current_files) > initial_count and not any(f.endswith('.crdownload') for f in current_files):
            return True
        time.sleep(0.5)
    return False

def file_already_exists(path, date_str):
    """Comprueba si ya existe un archivo descargado para esa fecha."""
    return any(date_str in f for f in os.listdir(path))

def run_extractor():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 12)

    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {
            "behavior": "allow",
            "downloadPath": DOWNLOAD_PATH
        }
    )

    current_date = datetime(2020, 11, 6)
    end_date = datetime(2020, 12, 31)

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        url = f"https://data.nordpoolgroup.com/auction/day-ahead/flows?deliveryDate={date_str}&deliveryArea=NO4&displayImportExport=true"

        print(f"📅 Procesando: {date_str}")

        # Si reinicias el script, evita repetir fechas ya descargadas
        if file_already_exists(DOWNLOAD_PATH, date_str):
            print(f"⏭️ Ya existe archivo para {date_str}, se omite.")
            current_date += timedelta(days=1)
            continue

        try:
            driver.get(url)

            initial_count = len(os.listdir(DOWNLOAD_PATH))

            export_btn = wait.until(
                EC.element_to_be_clickable((By.ID, "export-excel-button"))
            )

            # Pausa corta, suficiente para que la tabla termine de asentarse
            time.sleep(random.uniform(0.8, 1.4))

            driver.execute_script("arguments[0].click();", export_btn)

            # Esperar realmente a que aparezca el archivo
            downloaded = wait_for_new_file(DOWNLOAD_PATH, initial_count, timeout=40)

            if downloaded:
                print(f"✅ Descargado: {date_str}")
                current_date += timedelta(days=1)

                # Pausa pequeña y variable entre descargas
                time.sleep(random.uniform(1.2, 2.3))
            else:
                print(f"⚠️ No se detectó descarga para {date_str}. Reintentando en 5s...")
                time.sleep(random.uniform(4.5, 6.0))

        except Exception as e:
            print(f"❌ Error en {date_str}: {type(e).__name__}. Reintentando en 5s...")
            time.sleep(random.uniform(4.5, 6.0))

    print("\n🏁 ¡Proceso completado!")

if __name__ == "__main__":
    run_extractor()