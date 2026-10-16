import requests
import json
import time

url = "https://api.gdeltproject.org/api/v2/doc/doc"

params = {
    "query": '"Niger" -Nigeria -"Niger Delta"',
    "mode": "ArtList",
    "maxrecords": 50,
    "format": "json"
}

headers = {
    "User-Agent": "Geopolitical-OSINT-Platform/0.1"
}

for intento in range(3):

    response = requests.get(url, params=params, headers=headers)

    print("Geopolitical OSINT Platform - GDELT Collector")
    print("Intento:", intento + 1)
    print("Código HTTP:", response.status_code)

    if response.status_code == 200:
        data = response.json()

        with open("data/raw/gdelt_niger.json", "w") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

        for article in data["articles"]:
            print(article["title"])

        break

    elif response.status_code == 429:
    	if intento < 2:
        	espera = 5 * (intento + 1)
        	print("GDELT ha limitado las peticiones. Esperando", espera, "segundos...")
        	time.sleep(espera)
    	else:
        	print("GDELT sigue limitando las peticiones. Se han agotado los intentos.")

    else:
        print("Error al consultar GDELT:", response.status_code)
        break
