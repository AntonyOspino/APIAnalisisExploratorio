# app/services/servicioBase.py

import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session


class BaseService:
    """
    Clase base de la que heredan todos los services.
    Provee tres cosas a todos los hijos:
      1. self.db     → sesión de Neon lista para hacer queries
      2. self.logger → logger con el nombre de la clase hija
      3. _handle_error() → manejo uniforme de excepciones
    """

    def __init__(self, db: Session):
        # Recibe la sesión de Neon inyectada desde el route vía Depends(get_db)
        # Queda disponible en self.db para todos los métodos de las clases hijas
        self.db = db

        # Crea un logger con el nombre real de la clase hija
        # Si instancias DatosService, el logger se llama "DatosService"
        # Si instancias PdfService, el logger se llama "PdfService"
        # Así los logs son fáciles de identificar en consola
        self.logger = logging.getLogger(type(self).__name__)

    def _handle_error(self, e: Exception, mensaje: str = "Error interno del servidor"):
        """
        Método protegido — lo llaman todos los hijos desde sus bloques except.

        Hace dos cosas:
          1. Registra el error completo en el logger (visible en consola)
          2. Lanza HTTPException para que FastAPI retorne un JSON de error al cliente

        Ejemplo de uso en una clase hija:
            try:
                ...
            except Exception as e:
                self._handle_error(e, "Error al cargar el dataset")
        """
        # Registra el error con el stack trace completo en consola
        self.logger.error(f"{mensaje}: {str(e)}", exc_info=True)

        # Lanza la excepción HTTP que FastAPI convierte en respuesta JSON
        # El cliente (Java) recibirá: { "detail": "Error al cargar el dataset: ..." }
        raise HTTPException(
            status_code=500,
            detail=f"{mensaje}: {str(e)}"
        )