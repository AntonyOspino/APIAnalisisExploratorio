import requests, json

BASE = "http://127.0.0.1:8000"

def crear_sesion():
    r = requests.post(f"{BASE}/sesiones/crear", json={"nombre": "Test", "apellido": "Identidad"})
    return r.json()["sesion_id"]

# --- Test 1: CSV airtravel (no deberia tener ID) ---
print("=== CSV: airtravel ===")
sid = crear_sesion()
print(f"Sesion: {sid}")
url_csv = "https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv"
r = requests.post(f"{BASE}/datos/cargar", json={"sesion_id": sid, "url": url_csv, "tipo": "csv"})
print(f"Cargar: {r.status_code}")
r = requests.get(f"{BASE}/datos/columnas")
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# --- Test 2: XLSX Microsoft Financial (no deberia tener ID) ---
print("\n=== XLSX: Microsoft Financial ===")
sid2 = crear_sesion()
url_xlsx = "https://go.microsoft.com/fwlink/?LinkID=521962"
r = requests.post(f"{BASE}/datos/cargar", json={"sesion_id": sid2, "url": url_xlsx, "tipo": "xlsx"})
print(f"Cargar: {r.status_code}")
r = requests.get(f"{BASE}/datos/columnas")
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

# --- Test 3: CSV Titanic (tiene PassengerId = identidad) ---
print("\n=== CSV: Titanic (PassengerId deberia ser identidad) ===")
sid3 = crear_sesion()
url_titanic = "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv"
r = requests.post(f"{BASE}/datos/cargar", json={"sesion_id": sid3, "url": url_titanic, "tipo": "csv"})
print(f"Cargar: {r.status_code}")
r = requests.get(f"{BASE}/datos/columnas")
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
