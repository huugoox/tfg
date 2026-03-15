##  & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\HUGO\Desktop\SeleniumProfile"
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from datetime import datetime, timedelta

DOWNLOAD_PATH = r"C:\Users\HUGO\Desktop\Q8 - NORUEGA\TFG\tfg\ExcelFilesNoProcessed"

os.makedirs(DOWNLOAD_PATH, exist_ok=True)


def wait_for_download(path, timeout=60):
    """Espera a que empiece y termine una descarga de Chrome"""

    start = time.time()
    download_started = False

    while time.time() - start < timeout:

        files = os.listdir(path)

        crdownloads = [f for f in files if f.endswith(".crdownload")]

        # Detectar inicio
        if crdownloads:
            download_started = True

        # Detectar final
        if download_started and not crdownloads:
            print("  📥 Descarga completada")
            return True

        time.sleep(1)

    print("  ⚠️ Timeout esperando descarga")
    return False


def run_parasite_extractor():

    chrome_options = Options()

    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    driver = webdriver.Chrome(options=chrome_options)

    wait = WebDriverWait(driver, 20)

    print("🔗 Connectat al Chrome! Iniciant descàrregues...")

    start_date = datetime(2020, 1, 1)
    end_date = datetime(2025, 12, 31)

    current_date = start_date

    while current_date <= end_date:

        date_str = current_date.strftime("%Y-%m-%d")

        url = f"https://data.nordpoolgroup.com/auction/day-ahead/prices?deliveryDate={date_str}&currency=EUR&aggregation=DeliveryPeriod&deliveryAreas=EE,LT,LV,AT,BE,FR,GER,NL,PL,DK1,DK2,FI,NO1,NO2,NO3,NO4,NO5,SE1,SE2,SE3,SE4"

        print(f"\n📅 Procesando: {date_str}")

        success = False
        retries = 3

        while not success and retries > 0:

            try:

                driver.get(url)

                export_btn = wait.until(
                    EC.element_to_be_clickable((By.ID, "export-excel-button"))
                )

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", export_btn
                )

                time.sleep(1)
                
                wait_for_download(DOWNLOAD_PATH, 5)

                driver.execute_script("arguments[0].click();", export_btn)

                print("  🖱️ Botó Export Excel clicat")

                success = wait_for_download(DOWNLOAD_PATH)

            except Exception as e:

                retries -= 1
                print(f"  ❌ Error: {e}")
                print(f"  🔁 Reintentando... ({retries} intentos restantes)")
                time.sleep(3)

        if not success:
            print(f"  ⚠️ No se pudo descargar {date_str}")

        current_date += timedelta(days=1)

    print("\n🏁 Procés finalitzat!")


if __name__ == "__main__":
    run_parasite_extractor()