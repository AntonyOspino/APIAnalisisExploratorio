# app/services/datos_service.py

import json
import io
import requests
import pandas as pd
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.models import Dataset, Sesion


class DatosService(BaseService):
    """
    Gestiona la carga del dataset desde URL y consultas básicas.
    Hereda de BaseService: self.db, self.logger, self._handle_error()
    """

    def __init__(self, db: Session):
        # Llama al constructor del padre — configura self.db y self.logger
        super().__init__(db)

        # DataFrame activo en memoria — None hasta que se cargue un dataset
        self.df: pd.DataFrame | None = None

        # ID del Dataset guardado en Neon tras carga exitosa
        self.dataset_id: int | None = None

        # Estado interno del proceso
        # Valores: "sin_datos" | "cargado" | "analizando" | "listo"
        self._estado: str = "sin_datos"

    # ─── MÉTODOS PÚBLICOS ────────────────────────────────────────────────────

    def cargar_datos(self, url: str, tipo: str, sesion_id: int) -> dict:
        """
        Descarga el CSV o XLSX desde la URL y lo carga en self.df.
        Guarda los metadatos del dataset en la tabla datasets de Neon.
        Retorna un dict con los metadatos para que el route lo devuelva a Java.
        """
        try:
            self.logger.info(f"Iniciando carga de datos desde: {url}")

            # Cambia el estado a analizando mientras descarga
            self._estado = "analizando"

            # Descarga el archivo y lo convierte a DataFrame
            self.df = self._descargar_df(url, tipo)

            # Detecta si hay valores nulos en alguna columna
            tiene_nulos = bool(self.df.isnull().any().any())

            # Guarda los metadatos en Neon y obtiene el dataset_id generado
            self.dataset_id = self._guardar_dataset(
                sesion_id=sesion_id,
                url=url,
                tipo=tipo,
                filas=self.df.shape[0],
                columnas=self.df.shape[1],
                cols_json=self.df.columns.tolist(),
                tiene_nulos=tiene_nulos
            )

            # Actualiza el estado a cargado
            self._estado = "cargado"

            self.logger.info(f"Dataset cargado: {self.df.shape[0]} filas x {self.df.shape[1]} columnas")

            return {
                "mensaje": "Conjunto de datos cargados",
                "dataset_id": self.dataset_id,
                "total_filas": self.df.shape[0],
                "total_columnas": self.df.shape[1],
                "tiene_nulos": tiene_nulos
            }

        except Exception as e:
            # Resetea el estado si algo falla
            self._estado = "sin_datos"
            self._handle_error(e, "Error al cargar el dataset")

    def obtener_columnas(self) -> dict:
        """
        Retorna la lista de columnas del DataFrame activo.
        Si no hay dataset cargado lanza error 500.
        """
        try:
            # Verifica que haya un DataFrame cargado antes de continuar
            self._verificar_df_cargado()

            columnas = self.df.columns.tolist()
            self.logger.info(f"Columnas retornadas: {columnas}")

            return {"columnas": columnas}

        except Exception as e:
            self._handle_error(e, "Error al obtener columnas")

    def obtener_estado(self) -> dict:
        """
        Retorna el estado actual del proceso.
        Java hace polling a este endpoint para saber cuándo desbloquear la UI.
        """
        return {"estado": self._estado}

    # ─── MÉTODOS PRIVADOS ────────────────────────────────────────────────────

    def _descargar_df(self, url: str, tipo: str) -> pd.DataFrame:
        """
        Descarga el archivo desde la URL y lo convierte a DataFrame.
        Soporta CSV y XLSX desde cualquier URL pública.
        """
        self.logger.info(f"Descargando archivo tipo '{tipo}' desde URL")

        # Descarga el contenido raw de la URL con headers para evitar bloqueos
        respuesta = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)

        # Si la URL retorna error (404, 403, etc.) lanza excepción
        respuesta.raise_for_status()

        if tipo == "csv":
            # Convierte el contenido de texto a DataFrame
            return pd.read_csv(io.StringIO(respuesta.text))

        elif tipo == "xlsx":
            # Convierte el contenido binario a DataFrame
            return pd.read_excel(io.BytesIO(respuesta.content))

        else:
            raise ValueError(f"Tipo de archivo no soportado: '{tipo}'. Use 'csv' o 'xlsx'")

    def _guardar_dataset(
        self,
        sesion_id: int,
        url: str,
        tipo: str,
        filas: int,
        columnas: int,
        cols_json: list,
        tiene_nulos: bool
    ) -> int:
        """
        Inserta un registro en la tabla datasets de Neon.
        Retorna el ID generado automáticamente por la base de datos.
        """
        # Crea el objeto ORM con los metadatos del dataset
        nuevo_dataset = Dataset(
            sesion_id=sesion_id,
            url_origen=url,
            tipo_archivo=tipo,
            total_filas=filas,
            total_columnas=columnas,
            # Guarda la lista de columnas como string JSON
            columnas_json=json.dumps(cols_json),
            tiene_nulos=tiene_nulos
        )

        # Agrega, confirma y refresca para obtener el ID generado por Neon
        self.db.add(nuevo_dataset)
        self.db.commit()
        self.db.refresh(nuevo_dataset)

        self.logger.info(f"Dataset guardado en Neon con ID: {nuevo_dataset.id}")

        return nuevo_dataset.id

    def _verificar_df_cargado(self):
        """
        Verifica que haya un DataFrame en memoria antes de operar.
        Lo llaman los métodos que dependen de self.df.
        """
        if self.df is None:
            raise ValueError("No hay ningún dataset cargado. Llame primero a cargar_datos()")