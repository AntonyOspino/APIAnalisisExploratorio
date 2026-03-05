# app/schemas.py
# Clases Pydantic que validan los datos que entran y salen de cada endpoint.
# FastAPI las usa automáticamente — si el request no cumple el schema, retorna error 422.

from pydantic import BaseModel
from typing import List


# ─── SESIONES ────────────────────────────────────────────────────────────────

class SesionCreate(BaseModel):
    """Request para crear una sesión — se llama cuando el usuario da su nombre."""
    nombre_usuario: str  # nombre completo ingresado en el chat


class SesionResponse(BaseModel):
    """Response tras crear una sesión."""
    sesion_id: int       # ID generado por Neon — Java lo guarda para usarlo después
    mensaje: str         # "Sesión iniciada correctamente"

    class Config:
        from_attributes = True  # permite convertir objetos ORM directamente a este schema


# ─── DATOS ───────────────────────────────────────────────────────────────────

class CargarDatosRequest(BaseModel):
    """Request para cargar un dataset desde URL."""
    url: str             # URL del CSV o XLSX — copiada por el usuario en el chat
    tipo: str            # "csv" o "xlsx"
    sesion_id: int       # ID de la sesión activa — para enlazar el dataset con el usuario


class CargarDatosResponse(BaseModel):
    """Response tras cargar el dataset exitosamente."""
    mensaje: str         # "Conjunto de datos cargados"
    dataset_id: int      # ID del Dataset guardado en Neon — Java lo guarda para después
    total_filas: int     # df.shape[0]
    total_columnas: int  # df.shape[1]
    tiene_nulos: bool    # True si alguna columna tiene valores nulos


class ColumnasResponse(BaseModel):
    """Response con la lista de columnas del dataset activo."""
    columnas: List[str]  # ["Nombre", "Edad", "Ciudad", "Salario", ...]


class EstadoResponse(BaseModel):
    """Response con el estado actual del proceso."""
    # Valores posibles: sin_datos | cargado | analizando | listo
    estado: str


# ─── ANÁLISIS ────────────────────────────────────────────────────────────────

class AnalisisRequest(BaseModel):
    """Request para ejecutar el EDA completo."""
    dataset_id: int                      # ID del dataset a analizar
    columnas_cuantitativas: List[str]    # ["Edad", "Salario"]
    columnas_cualitativas: List[str]     # ["Ciudad", "Genero"]


class AnalisisResponse(BaseModel):
    """Response tras completar el análisis exploratorio."""
    mensaje: str                         # "Análisis completado"
    graficos: List[str]                  # rutas de los PNG generados


# ─── PDF ─────────────────────────────────────────────────────────────────────

class PdfRequest(BaseModel):
    """Request para generar el informe PDF."""
    dataset_id: int      # ID del dataset cuyos resultados se incluyen en el PDF


class PdfResponse(BaseModel):
    """Response tras generar el PDF exitosamente."""
    mensaje: str         # "Informe generado"
    informe_id: int      # ID del Informe guardado en Neon
    ruta_pdf: str        # "informes/informe_7.pdf"


# ─── CORREO ──────────────────────────────────────────────────────────────────

class CorreoRequest(BaseModel):
    """Request para enviar el informe por correo."""
    informe_id: int          # ID del informe a enviar
    correo: str              # dirección de correo del usuario
    nombre_usuario: str      # para personalizar el asunto del correo


class CorreoResponse(BaseModel):
    """Response tras enviar el correo exitosamente."""
    mensaje: str             # "Informe enviado"
    correo: str              # confirma la dirección a la que se envió