---
title: API Analisis Exploratorio
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# API Análisis Exploratorio

API REST construida con **FastAPI** + **PostgreSQL (Neon)** para ejecutar Análisis Exploratorio de Datos (EDA) sobre datasets públicos.

Desplegada localmente o en tu proveedor Cloud favorito — Documentación Swagger en `/docs`

## Requisitos

- Python 3.12+
- PostgreSQL (Neon)
- Dependencias: `pip install -r requirements.txt`

## Ejecución local

```bash
uvicorn app.main:app --reload --port 8000
```

La documentación interactiva (Swagger) estará disponible en: `http://127.0.0.1:8000/docs`

## Despliegue en Cloud (Ej. Google Cloud Run, Instancia VM)

1. Asegúrate de configurar las variables de entorno en el entorno de despliegue:
   - `DATABASE_URL` — URL de conexión a Neon (PostgreSQL)
   - `SMTP_EMAIL` — Correo para envío de informes
   - `SMTP_PASSWORD` — Contraseña de aplicación
2. Construir y ejecutar la imagen Docker:
   - `docker build -t api-eda .`
   - `docker run -p 8000:8000 -e DATABASE_URL='...' -e SMTP_EMAIL='...' -e SMTP_PASSWORD='...' api-eda`

---

## Base de datos — Modelo relacional

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   usuarios   │       │   sesiones   │       │   datasets   │       │   informes   │
├──────────────┤       ├──────────────┤       ├──────────────┤       ├──────────────┤
│ id       PK  │◄──┐   │ id       PK  │       │ id       PK  │◄──┐   │ id       PK  │
│ nombre       │   └───│ usuario_id FK│       │ sesion_id FK │   └───│ dataset_id FK│
│ apellido     │       │ fecha_consulta│      │ url_origen   │       │ ruta_pdf     │
│ correo       │       │ estado_sesion │      │ tipo_archivo │       │ correo_enviad│
│ fecha_registro│      └──────────────┘       │ columnas_*   │       │ estado_envio │
└──────────────┘                               │ total_filas  │       │ fecha_gen    │
                                               │ total_columnas│      │ fecha_envio  │
                                               │ tiene_nulos  │       └──────────────┘
                                               │ fecha_carga  │
                                               └──────────────┘
```

### Tabla `usuarios`
| Campo           | Tipo         | Descripción                              |
|-----------------|--------------|------------------------------------------|
| `id`            | int (PK)     | Identificador autoincremental            |
| `nombre`        | string(100)  | Nombre(s) del usuario                    |
| `apellido`      | string(100)  | Apellido(s) del usuario                  |
| `correo`        | string(200)  | Correo — se guarda al enviar el informe  |
| `fecha_registro`| datetime     | Timestamp de creación                    |

### Tabla `sesiones`
| Campo           | Tipo         | Descripción                              |
|-----------------|--------------|------------------------------------------|
| `id`            | int (PK)     | Identificador autoincremental            |
| `usuario_id`    | int (FK)     | Referencia a `usuarios.id`               |
| `fecha_consulta`| datetime     | Timestamp de creación                    |
| `estado_sesion` | string(50)   | `activa` → `completada` o `cancelada`    |

### Estados de sesión

| Estado        | Cuándo se asigna                              |
|---------------|-----------------------------------------------|
| `activa`      | Al crear la sesión (`POST /sesiones/crear`)    |
| `completada`  | Al enviar el correo (`POST /correo/enviar`)    |
| `cancelada`   | Al cancelar (`POST /sesiones/cancelar`)        |

### Tabla `datasets`
| Campo                    | Tipo       | Descripción                          |
|--------------------------|------------|--------------------------------------|
| `id`                     | int (PK)   | Identificador autoincremental        |
| `sesion_id`              | int (FK)   | Referencia a `sesiones.id`           |
| `url_origen`             | text       | URL de descarga del archivo          |
| `tipo_archivo`           | string(10) | `"csv"`, `"xlsx"` o `"xls"`    |
| `columnas_cuantitativas` | text       | Columnas numéricas (separadas por ,) |
| `columnas_cualitativas`  | text       | Columnas categóricas (separadas por ,)|
| `columnas_json`          | text       | Todas las columnas en JSON           |
| `total_filas`            | int        | Número de filas del dataset          |
| `total_columnas`         | int        | Número de columnas del dataset       |
| `tiene_nulos`            | bool       | `true` si hay valores nulos          |
| `fecha_carga`            | datetime   | Timestamp de carga                   |

### Tabla `informes`
| Campo            | Tipo         | Descripción                          |
|------------------|--------------|--------------------------------------|
| `id`             | int (PK)     | Identificador autoincremental        |
| `dataset_id`     | int (FK)     | Referencia a `datasets.id`           |
| `ruta_pdf`       | text         | Ruta local del PDF generado          |
| `correo_enviado` | string(200)  | Correo al que se envió               |
| `estado_envio`   | string(50)   | `pendiente` / `enviado` / `error`    |
| `fecha_generacion`| datetime    | Timestamp de creación del PDF        |
| `fecha_envio`    | datetime     | Timestamp de envío exitoso           |

---

## Flujo de uso

Los endpoints deben llamarse **en este orden**:

```
1. POST /sesiones/crear            → obtener sesion_id y usuario_id
2. POST /datos/cargar              → obtener dataset_id
3. GET  /datos/columnas            → ver columnas clasificadas
4. POST /analisis/ejecutar         → ejecutar EDA completo
5. POST /analisis/tratar-outliers  → (opcional) tratar outliers
6. POST /pdf/generar               → generar informe PDF
7. POST /correo/enviar             → enviar PDF por correo (sesión → "completada")
```

**Flujo alternativo — cancelar:**
```
1. POST /sesiones/crear            → obtener sesion_id
   ... el usuario decide no continuar ...
   POST /sesiones/cancelar         → sesión → "cancelada"
```

> **Nota:** Si el servidor se reinicia, el DataFrame en memoria se pierde y se debe volver a llamar `/datos/cargar` antes de `/analisis/ejecutar`.

> **Nota:** El paso 5 es **opcional**. Solo es necesario si desea incluir la sección de outliers en el informe PDF.

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

Registra un usuario y crea una sesión. Si ya existe un usuario con exactamente el mismo nombre y apellido, lo reutiliza.

**Request:**
```json
{
  "nombre": "Alejandro",
  "apellido": "Cantillo"
}
```

| Campo     | Tipo   | Descripción              |
|-----------|--------|--------------------------|
| `nombre`  | string | Nombre(s) del usuario    |
| `apellido`| string | Apellido(s) del usuario  |

**Response (usuario nuevo):**
```json
{
  "sesion_id": 1,
  "usuario_id": 1,
  "mensaje": "Sesión iniciada correctamente para Alejandro Cantillo",
  "usuario_nuevo": true
}
```

**Response (usuario existente):**
```json
{
  "sesion_id": 2,
  "usuario_id": 1,
  "mensaje": "Bienvenido de nuevo, Alejandro Cantillo",
  "usuario_nuevo": false
}
```

---

### `POST /sesiones/cancelar` — Cancelar sesión

Marca una sesión activa como cancelada. Solo se pueden cancelar sesiones con estado `activa`.

**Request:**
```json
{
  "sesion_id": 3
}
```

**Response:**
```json
{
  "mensaje": "Sesión cancelada correctamente",
  "estado": "cancelada"
}
```

**Errores:**
- `404` — Sesión no encontrada
- `400` — La sesión ya está completada o cancelada

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
| `tipo`      | string | `"csv"`, `"xlsx"` o `"xls"`              |
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

Retorna las columnas del dataset activo, clasificadas automáticamente en cuantitativas, cualitativas y de identidad.

Las **columnas de identidad** (ID, index, claves primarias, enteros secuenciales únicos) se detectan automáticamente y se excluyen de las listas cuantitativas/cualitativas para que no se analicen estadísticamente.

**Request:** Sin body

**Response (dataset sin columna de identidad):**
```json
{
  "columnas": [
    "Segment", "Country", "Product", "Units Sold", "Sales", "Profit"
  ],
  "cuantitativas": ["Units Sold", "Sales", "Profit"],
  "cualitativas": ["Segment", "Country", "Product"],
  "identidad": []
}
```

**Response (dataset con columna de identidad):**
```json
{
  "columnas": [
    "PassengerId", "Survived", "Pclass", "Name", "Sex", "Age", "Fare"
  ],
  "cuantitativas": ["Survived", "Pclass", "Age", "Fare"],
  "cualitativas": ["Name", "Sex"],
  "identidad": ["PassengerId"]
}
```

| Campo           | Tipo     | Descripción                                              |
|-----------------|----------|----------------------------------------------------------|
| `columnas`      | string[] | Todas las columnas del dataset                           |
| `cuantitativas` | string[] | Columnas numéricas (excluye identidad)                    |
| `cualitativas`  | string[] | Columnas categóricas (excluye identidad)                  |
| `identidad`     | string[] | Columnas detectadas como ID/índice (excluidas del análisis) |

> **Detección automática:** Se identifican por nombre (`id`, `index`, `pk`, `key`, `row`, `#`, `unnamed`) o por datos (columnas enteras con >95% valores únicos y secuencia incremental).

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

### `POST /analisis/tratar-outliers` — Tratar outliers (opcional)

Detecta y reemplaza outliers en columnas cuantitativas usando el método **IQR** (rango intercuartílico). El usuario elige la estrategia de reemplazo: media, mediana o moda. Se generan gráficos comparativos antes/después por cada columna que tenga outliers.

**Request:**
```json
{
  "dataset_id": 6,
  "metodo": "mediana",
  "columnas": ["canino_hembra", "canino_macho", "felino_macho"]
}
```

| Campo        | Tipo     | Descripción                                        |
|--------------|----------|----------------------------------------------------|
| `dataset_id` | int      | ID obtenido de `/datos/cargar`                     |
| `metodo`     | string   | `"media"`, `"mediana"` o `"moda"`                   |
| `columnas`   | string[] | Columnas cuantitativas en las que buscar outliers  |

**Response:**
```json
{
  "mensaje": "Outliers tratados con método 'mediana'",
  "metodo_usado": "mediana",
  "columnas_tratadas": {
    "canino_hembra": {
      "outliers_detectados": 12,
      "valor_reemplazo": 5.0,
      "limite_inferior": -3.5,
      "limite_superior": 15.5,
      "q1": 2.0,
      "q3": 9.0,
      "iqr": 7.0
    },
    "canino_macho": {
      "outliers_detectados": 0,
      "valor_reemplazo": null
    }
  },
  "graficos": [
    "graficos/outliers_canino_hembra.png"
  ]
}
```

> **Nota:** Solo se generan gráficos para columnas que tengan al menos 1 outlier. El DataFrame en memoria queda actualizado con los valores reemplazados.

---

### `POST /pdf/generar` — Generar informe PDF

Genera un informe PDF profesional con todos los resultados del EDA. **Opcionalmente** incluye una sección de tratamiento de outliers si se solicita.

#### Caso 1: PDF estándar (sin outliers)

Genera el informe con las secciones habituales del EDA.

**Request:**
```json
{
  "dataset_id": 6
}
```

> `incluir_outliers` por defecto es `false`, por lo que no es necesario enviarlo.

**Response:**
```json
{
  "mensaje": "Informe generado",
  "informe_id": 1,
  "ruta_pdf": "Informes/informe_6.pdf"
}
```

#### Caso 2: PDF con sección de outliers

Incluye todo lo del caso 1 **más** una sección adicional con:
- Texto interpretativo explicando el tratamiento realizado
- Tabla resumen de outliers por columna
- Gráficos comparativos antes/después

**Requisito previo:** Debe haberse ejecutado `/analisis/tratar-outliers` antes de generar el PDF. Si no se ha ejecutado, el endpoint retorna error 400.

**Request:**
```json
{
  "dataset_id": 6,
  "incluir_outliers": true
}
```

| Campo              | Tipo   | Descripción                                                  |
|--------------------|--------|--------------------------------------------------------------|
| `dataset_id`       | int    | ID obtenido de `/datos/cargar`                               |
| `incluir_outliers` | bool   | `true` para incluir la sección de outliers (default: `false`)|

**Response:**
```json
{
  "mensaje": "Informe generado",
  "informe_id": 2,
  "ruta_pdf": "Informes/informe_6.pdf"
}
```

El PDF incluye:
- Encabezado con franja de color y fecha
- Ficha técnica del dataset
- Nombres de integrantes del equipo
- Interpretación general en lenguaje natural
- Tabla de valores nulos
- Tablas de frecuencia por columna cualitativa
- Estadísticas descriptivas por columna cuantitativa
- Tabla de contingencia
- Gráficos incrustados
- **(Solo si `incluir_outliers: true`)** Sección de tratamiento de outliers con interpretación, tabla y gráficos
- Pie de página con número de página

---

### `POST /correo/enviar` — Enviar informe por correo

Envía el PDF generado al correo indicado. Obtiene el nombre del usuario automáticamente desde la sesión. **Marca la sesión como `completada`.**

**Request:**
```json
{
  "informe_id": 1,
  "correo": "usuario@mail.com",
  "sesion_id": 5
}
```

| Campo        | Tipo   | Descripción                          |
|--------------|--------|--------------------------------------|
| `informe_id` | int    | ID obtenido de `/pdf/generar`        |
| `correo`     | string | Dirección de correo del usuario      |
| `sesion_id`  | int    | ID de la sesión activa               |

**Response:**
```json
{
  "mensaje": "Informe enviado",
  "correo": "usuario@mail.com"
}
```

> Al enviar el correo, la sesión pasa automáticamente a estado `completada` y el correo se guarda en el registro del usuario.

> **Requisito:** Definir `SMTP_EMAIL` y `SMTP_PASSWORD` en el archivo `.env`. Para Gmail, usar una [contraseña de aplicación](https://myaccount.google.com/apppasswords).

---

## Estructura del proyecto

```
app/
├── main.py              # Punto de entrada — FastAPI app + lifespan
├── database.py          # Motor async SQLAlchemy + sesión (Neon)
├── models.py            # Modelos ORM: Usuario, Sesion, Dataset, Informe
├── schemas.py           # Schemas Pydantic (request/response)
├── routes/
│   ├── sesiones.py      # POST /sesiones/crear, POST /sesiones/cancelar
│   ├── datos.py         # POST /datos/cargar, GET /columnas, GET /estado
│   ├── analisis.py      # POST /analisis/ejecutar, POST /analisis/tratar-outliers
│   ├── pdf.py           # POST /pdf/generar (con o sin outliers)
│   └── correo.py        # POST /correo/enviar
└── services/
    ├── base_service.py      # Clase base con logger y manejo de errores
    ├── datos_service.py     # Descarga, limpieza y persistencia de datasets
    ├── analisis_service.py  # EDA: estadísticas, frecuencias, gráficos, interpretación
    ├── pdf_service.py       # Generación de informe PDF con reportlab
    └── correo_service.py    # Envío de PDF por correo (SMTP + HTML)
graficos/                # PNGs generados por el análisis
Informes/                # PDFs generados
```

## Variables de entorno (`.env`)

```env
DATABASE_URL=postgresql://user:pass@host/db
SMTP_EMAIL=correo@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_HOST=smtp.gmail.com        # opcional, default: smtp.gmail.com
SMTP_PORT=587                   # opcional, default: 587
```

## Dataset de prueba

URL usada para testing:

```
https://www.datos.gov.co/resource/ezzu-ke2k.csv
```

Contiene 472 filas y 10 columnas sobre jornadas de esterilización animal.
