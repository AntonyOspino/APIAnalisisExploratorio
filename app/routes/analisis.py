# app/routes/analisis.py
# Endpoint para ejecutar el análisis exploratorio de datos (EDA).
# Reutiliza el DataFrame ya cargado en DatosService — no vuelve a descargarlo.

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AnalisisRequest, AnalisisResponse, TratarOutliersRequest, TratarOutliersResponse
from app.services.analisis_service import AnalisisService
from app.routes.datos import get_datos_service  # comparte la instancia global de DatosService
from app.services.datos_service import DatosService

router = APIRouter()

# Cache para compartir los resultados del último análisis con el endpoint de PDF
_analisis_service_cache: dict = {}


@router.post("/ejecutar", response_model=AnalisisResponse)
async def ejecutar_analisis(
    request: AnalisisRequest,
    db: AsyncSession = Depends(get_db),
    datos_service: DatosService = Depends(get_datos_service)
):
    """
    Obtiene el DataFrame activo de DatosService y lo pasa a AnalisisService.
    Así no se vuelve a descargar el dataset — se reutiliza el que ya está en memoria.
    """
    # Verifica que haya un dataset cargado antes de analizar
    datos_service._verificar_df_cargado()

    # Instancia el service de análisis con la sesión de DB
    service = AnalisisService(db)

    result = await service.ejecutar(
        df=datos_service.df,          # DataFrame ya cargado en memoria
        dataset_id=request.dataset_id,
        cols_cuant=request.columnas_cuantitativas,
        cols_cual=request.columnas_cualitativas
    )

    # Guardar columnas de identidad detectadas en los resultados
    identidad = [c for c in datos_service.df.columns
                 if DatosService._es_columna_identidad(datos_service.df, c)]
    service.resultados["identidad"] = identidad

    # Guardar el service para que /pdf/generar pueda acceder a resultados y gráficos
    _analisis_service_cache["ultima"] = service

    return result


@router.post("/tratar-outliers", response_model=TratarOutliersResponse)
async def tratar_outliers(
    request: TratarOutliersRequest,
    db: AsyncSession = Depends(get_db),
    datos_service: DatosService = Depends(get_datos_service)
):
    """
    Detecta y reemplaza outliers en columnas cuantitativas usando IQR.
    Métodos disponibles: 'media', 'mediana', 'moda'.
    Genera gráficos comparativos antes/después por cada columna.
    """
    datos_service._verificar_df_cargado()

    service = AnalisisService(db)

    df_tratado, reporte, graficos = service.tratar_outliers(
        df=datos_service.df,
        columnas=request.columnas,
        metodo=request.metodo
    )

    # Actualizar el DataFrame en memoria con los outliers tratados
    datos_service.df = df_tratado

    # Guardar resultados de outliers en cache para que el PDF pueda usarlos
    _analisis_service_cache["outliers"] = {
        "reporte": reporte,
        "graficos": graficos,
        "metodo": request.metodo,
    }

    return {
        "mensaje": f"Outliers tratados con método '{request.metodo}'",
        "metodo_usado": request.metodo,
        "columnas_tratadas": reporte,
        "graficos": graficos
    }