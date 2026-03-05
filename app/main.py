from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importa el motor y la base para crear las tablas al iniciar
from app.database import engine, Base

# Importa los routers de cada módulo de rutas
from app.routes import datos, analisis, pdf, correo

# Crea todas las tablas en Neon si todavía no existen
# Si ya existen, no hace nada — no destruye datos
Base.metadata.create_all(bind=engine)

# Instancia principal de la aplicación FastAPI
app = FastAPI(
    title="API Análisis Exploratorio",
    description="Parcial I — EDA con FastAPI + Neon",
    version="1.0.0"
)

# Middleware CORS — permite que Java (u otro cliente) consuma la API
# allow_origins=["*"] acepta peticiones desde cualquier origen
# En producción se reemplaza por la IP/puerto exacto del cliente Java
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra cada grupo de endpoints con su prefijo y etiqueta en Swagger
app.include_router(datos.router,     prefix="/datos",    tags=["Datos"])
app.include_router(analisis.router,  prefix="/analisis", tags=["Análisis"])
app.include_router(pdf.router,       prefix="/pdf",      tags=["PDF"])
app.include_router(correo.router,    prefix="/correo",   tags=["Correo"])

# Endpoint raíz — sirve para verificar que la API está corriendo
@app.get("/")
def root():
    return {"mensaje": "API funcionando correctamente"}