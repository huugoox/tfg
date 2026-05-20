from pathlib import Path
from datetime import date
import requests
import pandas as pd
import os


# =========================
# API CONFIG
# =========================
USERNAME = os.getenv("NORDPOOL_USERNAME")
PASSWORD = os.getenv("NORDPOOL_PASSWORD")

if USERNAME is None or PASSWORD is None:
    raise ValueError("Faltan las variables de entorno NORDPOOL_USERNAME o NORDPOOL_PASSWORD")

TOKEN_URL = "https://sts.nordpoolgroup.com/connect/token"
VOLUMES_URL = "https://data-api.nordpoolgroup.com/api/v2/Auction/Volumes/ByAreas"

AREAS = [
    "DK1", "DK2",
    "EE", "FI", "LT", "LV",
    "NO1", "NO2", "NO3", "NO4", "NO5",
    "SE1", "SE2", "SE3", "SE4"
]

MARKET = "DayAhead"
DAY = date(2020, 1, 1)


# =========================
# GET ACCESS TOKEN
# =========================
def get_access_token(username: str, password: str) -> str:
    headers = {
        "Authorization": "Basic Y2xpZW50X21hcmtldGRhdGFfYXBpOmNsaWVudF9tYXJrZXRkYXRhX2FwaQ==",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "password",
        "scope": "marketdata_api",
        "username": username,
        "password": password,
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code != 200:
        raise RuntimeError(
            f"Error obteniendo token: {response.status_code}\n{response.text[:1000]}"
        )

    return response.json()["access_token"]


# =========================
# TEST VOLUMES API
# =========================
print("Obteniendo access token...")
access_token = get_access_token(USERNAME, PASSWORD)

headers = {
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
}

params = {
    "areas": AREAS,
    "market": MARKET,
    "date": DAY.strftime("%Y-%m-%d"),
}

response = requests.get(
    VOLUMES_URL,
    headers=headers,
    params=params
)

print("Status code:", response.status_code)
print("URL:", response.url)
print(response.text[:3000])

if response.status_code == 200:
    data = response.json()

    print("\nTipo:", type(data))
    print("Número de zonas:", len(data))

    if len(data) > 0:
        print("\nKeys primera zona:")
        print(data[0].keys())

        print("\nPrimera zona:")
        print(data[0])