"""
Test completo del flujo: sesion → cargar → columnas → analisis → pdf → correo
Prueba con Titanic (tiene PassengerId como identidad) y Microsoft Financial (sin identidad).
"""
import requests, json, time, sys

BASE = "http://127.0.0.1:8000"
EMAIL = "aleduard.230315@gmail.com"
RESULTADOS = []


def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTADOS.append((test_name, passed))
    print(f"  [{status}] {test_name}" + (f" — {detail}" if detail else ""))


def crear_sesion(nombre, apellido):
    r = requests.post(f"{BASE}/sesiones/crear", json={"nombre": nombre, "apellido": apellido})
    r.raise_for_status()
    return r.json()["sesion_id"]


def flujo_completo(label, url, tipo, cols_cuant, cols_cual, tiene_identidad, enviar_correo=False):
    """Ejecuta el flujo completo y valida cada paso."""
    print(f"\n{'='*60}")
    print(f"  FLUJO: {label}")
    print(f"{'='*60}")

    # 1. Sesion
    sid = crear_sesion("Test", label)
    log(f"{label} - Crear sesion", sid > 0, f"sesion_id={sid}")

    # 2. Cargar dataset
    r = requests.post(f"{BASE}/datos/cargar", json={"sesion_id": sid, "url": url, "tipo": tipo})
    data = r.json()
    dataset_id = data.get("dataset_id", 0)
    log(f"{label} - Cargar dataset", r.status_code == 200, f"dataset_id={dataset_id}")

    # 3. Columnas (verificar identidad)
    r = requests.get(f"{BASE}/datos/columnas")
    cols = r.json()
    id_cols = cols.get("identidad", [])
    if tiene_identidad:
        log(f"{label} - Identidad detectada", len(id_cols) > 0, f"identidad={id_cols}")
    else:
        log(f"{label} - Sin identidad", len(id_cols) == 0, "identidad=[]")

    # Verificar exclusion de cuant/cual
    for id_col in id_cols:
        not_in_cuant = id_col not in cols["cuantitativas"]
        not_in_cual = id_col not in cols["cualitativas"]
        log(f"{label} - {id_col} excluida de cuant/cual", not_in_cuant and not_in_cual)

    # 4. Analisis
    r = requests.post(f"{BASE}/analisis/ejecutar", json={
        "dataset_id": dataset_id,
        "columnas_cuantitativas": cols_cuant,
        "columnas_cualitativas": cols_cual,
    })
    analisis = r.json()
    log(f"{label} - Ejecutar analisis", r.status_code == 200, analisis.get("mensaje", ""))

    # 5. PDF
    r = requests.post(f"{BASE}/pdf/generar", json={
        "dataset_id": dataset_id,
        "incluir_outliers": False,
    })
    pdf = r.json()
    informe_id = pdf.get("informe_id", 0)
    ruta_pdf = pdf.get("ruta_pdf", "")
    log(f"{label} - Generar PDF", r.status_code == 200, f"informe_id={informe_id}, ruta={ruta_pdf}")

    # Verificar tamaño del PDF
    import os
    if ruta_pdf and os.path.exists(ruta_pdf):
        size = os.path.getsize(ruta_pdf)
        log(f"{label} - PDF valido", size > 1000, f"{size:,} bytes")
    else:
        log(f"{label} - PDF valido", False, "archivo no encontrado")

    # 6. Correo (solo si se pide)
    if enviar_correo:
        r = requests.post(f"{BASE}/correo/enviar", json={
            "informe_id": informe_id,
            "correo": EMAIL,
            "sesion_id": sid,
        })
        correo_resp = r.json()
        log(f"{label} - Enviar correo", r.status_code == 200, correo_resp.get("mensaje", ""))

    return informe_id


# ══════════════════════════════════════════════════════════════════════════════
# FLUJO 1: Titanic CSV — tiene PassengerId (columna de identidad)
# ══════════════════════════════════════════════════════════════════════════════
flujo_completo(
    label="Titanic (con ID)",
    url="https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
    tipo="csv",
    cols_cuant=["Survived", "Pclass", "Age", "SibSp", "Parch", "Fare"],
    cols_cual=["Sex", "Embarked"],
    tiene_identidad=True,
    enviar_correo=True,
)

# ══════════════════════════════════════════════════════════════════════════════
# FLUJO 2: Microsoft Financial XLSX — sin columna de identidad
# ══════════════════════════════════════════════════════════════════════════════
flujo_completo(
    label="Financial (sin ID)",
    url="https://go.microsoft.com/fwlink/?LinkID=521962",
    tipo="xlsx",
    cols_cuant=["Units Sold", "Sales", "Profit", "COGS"],
    cols_cual=["Segment", "Country", "Product"],
    tiene_identidad=False,
    enviar_correo=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"  RESUMEN FINAL")
print(f"{'='*60}")
total = len(RESULTADOS)
passed = sum(1 for _, ok in RESULTADOS if ok)
failed = total - passed
for name, ok in RESULTADOS:
    print(f"  {'PASS' if ok else 'FAIL':4s}  {name}")
print(f"\n  Total: {total} | Passed: {passed} | Failed: {failed}")
if failed == 0:
    print("  *** TODOS LOS TESTS PASARON ***")
else:
    print(f"  *** {failed} TEST(S) FALLARON ***")
