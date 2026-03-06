# API Análisis Exploratorio

API REST construida con **FastAPI** + **PostgreSQL (Neon)** para ejecutar Análisis Exploratorio de Datos (EDA) sobre datasets públicos.

## Requisitos

- Python 3.12+
- PostgreSQL (Neon)
- Dependencias: `pip install -r requirements.txt`

## Ejecución

```bash
uvicorn app.main:app --reload --port 8000
```

La documentación interactiva (Swagger) estará disponible en: `http://127.0.0.1:8000/docs`

---

## Flujo de uso

Los endpoints deben llamarse **en este orden**:

```
1. POST /sesiones/crear       → obtener sesion_id
2. POST /datos/cargar         → obtener dataset_id
3. GET  /datos/columnas       → ver columnas clasificadas
4. POST /analisis/ejecutar    → ejecutar EDA completo
```

> **Nota:** Si el servidor se reinicia, el DataFrame en memoria se pierde y se debe volver a llamar `/datos/cargar` antes de `/analisis/ejecutar`.

---

## Endpoints

### `GET /` — Health Check

Verifica que la API esté funcionando.

**Request:** Sin body

**Response:**
```json
{
  "mensaje": "API funcionando correctamente"
}
```

---

### `POST /sesiones/crear` — Crear sesión

Registra un nuevo usuario/sesión en la base de datos.

**Request:**
```json
{
  "nombre_usuario": "Alejandro"
}
```

**Response:**
```json
{
  "sesion_id": 5,
  "mensaje": "Sesión iniciada correctamente"
}
```

---

### `POST /datos/cargar` — Cargar dataset

Descarga un dataset desde una URL pública y guarda sus metadatos en Neon.

**Request:**
```json
{
  "url": "https://www.datos.gov.co/resource/ezzu-ke2k.csv",
  "tipo": "csv",
  "sesion_id": 5
}
```

| Campo       | Tipo   | Descripción                                |
|-------------|--------|--------------------------------------------|
| `url`       | string | URL pública del archivo CSV o XLSX         |
| `tipo`      | string | `"csv"` o `"xlsx"`                         |
| `sesion_id` | int    | ID obtenido de `/sesiones/crear`           |

**Response:**
```json
{
  "mensaje": "Conjunto de datos cargados",
  "dataset_id": 6,
  "total_filas": 472,
  "total_columnas": 10,
  "tiene_nulos": true
}
```

---

### `GET /datos/columnas` — Obtener columnas clasificadas

Retorna las columnas del dataset activo, clasificadas automáticamente en cuantitativas y cualitativas.

**Request:** Sin body

**Response:**
```json
{
  "columnas": [
    "item", "no", "a_o", "mes", "barrio_o_vereda",
    "poblacion_beneficiada", "canino_hembra", "canino_macho",
    "felino_hembra", "felino_macho"
  ],
  "cuantitativas": [
    "no", "poblacion_beneficiada", "canino_hembra",
    "canino_macho", "felino_hembra", "felino_macho"
  ],
  "cualitativas": [
    "item", "a_o", "mes", "barrio_o_vereda"
  ]
}
```

---

### `GET /datos/estado` — Estado del proceso

Retorna el estado actual del flujo de trabajo.

**Request:** Sin body

**Response:**
```json
{
  "estado": "cargado"
}
```

| Estado       | Significado                        |
|--------------|------------------------------------|
| `sin_datos`  | No se ha cargado ningún dataset    |
| `analizando` | Descarga/análisis en progreso      |
| `cargado`    | Dataset listo para analizar        |

---

### `POST /analisis/ejecutar` — Ejecutar EDA

Ejecuta el análisis exploratorio completo sobre el dataset cargado. Incluye:

- Detección de valores nulos (antes de limpiar)
- Limpieza de datos (duplicados, nulos, tipos)
- Tablas de frecuencia (cualitativas)
- Estadísticas descriptivas (cuantitativas)
- Tabla de contingencia
- Gráficos PNG (histogramas, boxplots, barras, tortas)

**Request:**
```json
{
  "dataset_id": 6,
  "columnas_cuantitativas": [
    "canino_hembra", "canino_macho",
    "felino_hembra", "felino_macho"
  ],
  "columnas_cualitativas": [
    "no", "barrio_o_vereda", "poblacion_beneficiada"
  ]
}
```

| Campo                      | Tipo     | Descripción                                  |
|----------------------------|----------|----------------------------------------------|
| `dataset_id`               | int      | ID obtenido de `/datos/cargar`               |
| `columnas_cuantitativas`   | string[] | Columnas numéricas a analizar                |
| `columnas_cualitativas`    | string[] | Columnas categóricas a analizar              |

**Response:**
```json
{
  "mensaje": "Análisis completado",
  "graficos": [
    "graficos/cual_no.png",
    "graficos/cual_barrio_o_vereda.png",
    "graficos/cual_poblacion_beneficiada.png",
    "graficos/cuant_canino_hembra.png",
    "graficos/cuant_canino_macho.png",
    "graficos/cuant_felino_hembra.png",
    "graficos/cuant_felino_macho.png"
  ]
}
```

---

## Estructura del proyecto

```
app/
├── main.py              # Punto de entrada — FastAPI app + lifespan
├── database.py          # Motor async SQLAlchemy + sesión (Neon)
├── models.py            # Modelos ORM: Sesion, Dataset, Informe
├── schemas.py           # Schemas Pydantic (request/response)
├── routes/
│   ├── sesiones.py      # POST /sesiones/crear
│   ├── datos.py         # POST /datos/cargar, GET /columnas, GET /estado
│   ├── analisis.py      # POST /analisis/ejecutar
│   ├── pdf.py           # (pendiente)
│   └── correo.py        # (pendiente)
└── services/
    ├── base_service.py      # Clase base con logger y manejo de errores
    ├── datos_service.py     # Descarga, limpieza y persistencia de datasets
    ├── analisis_service.py  # EDA: estadísticas, frecuencias, gráficos
    ├── correo_service.py    # (pendiente)
    └── pdf_service.py       # (pendiente — no existe aún)
graficos/                # PNGs generados por el análisis
Informes/                # PDFs generados (pendiente)
```

## Dataset de prueba

URL usada para testing:

```
https://www.datos.gov.co/resource/ezzu-ke2k.csv
```

Contiene 472 filas y 10 columnas sobre jornadas de vacunación animal.
