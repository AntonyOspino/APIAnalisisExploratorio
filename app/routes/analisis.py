# app/routes/analisis.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalisisRequest, AnalisisResponse
from app.services.analisis_service import AnalisisService
from app.routes.datos import get_datos_service
from app.services.datos_service import DatosService

router = APIRouter()


@router.post("/ejecutar", response_model=AnalisisResponse)
def ejecutar_analisis(
    request: AnalisisRequest,
    db: Session = Depends(get_db),
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

    return service.ejecutar(
        df=datos_service.df,          # DataFrame ya cargado en memoria
        dataset_id=request.dataset_id,
        cols_cuant=request.columnas_cuantitativas,
        cols_cual=request.columnas_cualitativas
    )