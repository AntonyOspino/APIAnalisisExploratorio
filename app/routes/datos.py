# app/routes/datos.py
# Route delgado — solo recibe, delega al service y retorna.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CargarDatosRequest, CargarDatosResponse,
    ColumnasResponse, EstadoResponse
)
from app.services.datos_service import DatosService

router = APIRouter()

# Instancia global del service — persiste el DataFrame entre peticiones
# Sin esto self.df se resetea en cada request
_service: DatosService | None = None


def get_datos_service(db: Session = Depends(get_db)) -> DatosService:
    """
    Retorna la instancia global de DatosService.
    Si no existe la crea. Inyecta siempre una sesión de DB fresca.
    """
    global _service
    if _service is None:
        _service = DatosService(db)
    else:
        # Actualiza la sesión de DB sin perder el DataFrame en memoria
        _service.db = db
    return _service


@router.post("/cargar", response_model=CargarDatosResponse)
def cargar_datos(request: CargarDatosRequest, service: DatosService = Depends(get_datos_service)):
    return service.cargar_datos(request.url, request.tipo, request.sesion_id)


@router.get("/columnas", response_model=ColumnasResponse)
def obtener_columnas(service: DatosService = Depends(get_datos_service)):
    return service.obtener_columnas()


@router.get("/estado", response_model=EstadoResponse)
def obtener_estado(service: DatosService = Depends(get_datos_service)):
    return service.obtener_estado()