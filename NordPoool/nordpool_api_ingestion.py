# NOT WORKING
import requests
import os

def descarrega_directa_nordpool():
    # Anys que vols
    anys = [2020, 2021, 2022, 2023, 2024]
    
    folder = "ExcelFilesNoProcessed"
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Aquesta és la ruta que sol funcionar per a descàrregues directes
    # Si aquesta falla, t'explicaré com treure la URL exacta del teu navegador
    base_url = "https://www.nordpoolgroup.com/globalassets/marketdata-excel-files/elspot-prices_{}_hourly.xls"

    for any_tfg in anys:
        url = base_url.format(any_tfg)
        file_name = f"nordpool_{any_tfg}.xls"
        path = os.path.join(folder, file_name)
        
        print(f"Intentant baixar {any_tfg}...", end=" ")
        
        # Afegim un User-Agent per semblar un navegador, sinó Nord Pool ens bloqueja
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        r = requests.get(url, headers=headers)
        
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            print("✅ BAIXAT")
        else:
            print(f"❌ ERROR {r.status_code}")

if __name__ == "__main__":
    descarrega_directa_nordpool()