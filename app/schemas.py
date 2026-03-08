# app/schemas.py
# Clases Pydantic que validan los datos que entran y salen de cada endpoint.
# FastAPI las usa automáticamente — si el request no cumple el schema, retorna error 422.

from pydantic import BaseModel
from typing import List


# ─── SESIONES ────────────────────────────────────────────────────────────────

class SesionCreate(BaseModel):
    """Request para crear una sesión — se llama cuando el usuario da su nombre."""
    nombre: str      # nombre(s) del usuario
    apellido: str    # apellido(s) del usuario


class SesionResponse(BaseModel):
    """Response tras crear una sesión."""
    sesion_id: int       # ID de la sesión generada
    usuario_id: int      # ID del usuario (nuevo o existente)
    mensaje: str         # "Sesión iniciada correctamente" o "Usuario existente..."
    usuario_nuevo: bool  # True si se creó un usuario nuevo

    class Config:
        from_attributes = True


class CancelarSesionRequest(BaseModel):
    """Request para cancelar una sesión activa."""
    sesion_id: int       # ID de la sesión a cancelar


class CancelarSesionResponse(BaseModel):
    """Response tras cancelar una sesión."""
    mensaje: str
    estado: str          # "cancelada"


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
    """Response con la lista de columnas clasificadas del dataset activo."""
    columnas: List[str]                  # todas las columnas
    cuantitativas: List[str]             # columnas numéricas (int, float)
    cualitativas: List[str]              # columnas categóricas (object, string, bool)
    identidad: List[str] = []            # columnas de identidad detectadas (excluidas de cuant/cual)


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


# ─── OUTLIERS ────────────────────────────────────────────────────────────────

class TratarOutliersRequest(BaseModel):
    """Request para tratar outliers en columnas cuantitativas."""
    dataset_id: int                      # ID del dataset activo
    metodo: str                          # "media", "mediana" o "moda"
    columnas: List[str]                  # columnas cuantitativas a tratar


class TratarOutliersResponse(BaseModel):
    """Response tras tratar los outliers."""
    mensaje: str
    metodo_usado: str
    columnas_tratadas: dict              # { "col": { "outliers_detectados": N, "valor_reemplazo": X } }
    graficos: List[str]                  # rutas de PNG antes/después


# ─── PDF ─────────────────────────────────────────────────────────────────────

class PdfRequest(BaseModel):
    """Request para generar el informe PDF."""
    dataset_id: int              # ID del dataset cuyos resultados se incluyen en el PDF
    incluir_outliers: bool = False  # True para incluir sección de outliers en el informe


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
    sesion_id: int           # ID de la sesión — para obtener el nombre del usuario


class CorreoResponse(BaseModel):
    """Response tras enviar el correo exitosamente."""
    mensaje: str             # "Informe enviado"
    correo: str              # confirma la dirección a la que se envió