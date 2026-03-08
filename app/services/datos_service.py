# app/services/datos_service.py
# Servicio encargado de descargar datasets (CSV/XLSX), mantener el DataFrame
# en memoria y registrar los metadatos en la base de datos Neon.

import json
import io
import requests
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base_service import BaseService
from app.models import Dataset


class DatosService(BaseService):

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.df: pd.DataFrame | None = None       # DataFrame activo en memoria
        self.dataset_id: int | None = None         # ID del dataset en Neon
        self._estado: str = "sin_datos"             # sin_datos → analizando → cargado

    # ─── MÉTODOS PÚBLICOS ────────────────────────────────────────────────────

    async def cargar_datos(self, url: str, tipo: str, sesion_id: int) -> dict:
        """Descarga el dataset y guarda metadatos en Neon."""
        try:
            self.logger.info(f"Iniciando carga desde: {url}")
            self._estado = "analizando"

            self.df = self._descargar_df(url, tipo)  # sincrónico — pandas no es async
            tiene_nulos = bool(self.df.isnull().any().any())

            self.dataset_id = await self._guardar_dataset(
                sesion_id=sesion_id,
                url=url,
                tipo=tipo,
                filas=self.df.shape[0],
                columnas=self.df.shape[1],
                cols_json=self.df.columns.tolist(),
                tiene_nulos=tiene_nulos
            )

            self._estado = "cargado"
            self.logger.info(f"Dataset cargado: {self.df.shape[0]}x{self.df.shape[1]}")

            return {
                "mensaje": "Conjunto de datos cargados",
                "dataset_id": self.dataset_id,
                "total_filas": self.df.shape[0],
                "total_columnas": self.df.shape[1],
                "tiene_nulos": tiene_nulos
            }

        except Exception as e:
            self._estado = "sin_datos"
            self._handle_error(e, "Error al cargar el dataset")

    async def obtener_columnas(self) -> dict:
        """Retorna columnas del DataFrame clasificadas en cuantitativas y cualitativas."""
        try:
            self._verificar_df_cargado()
            cuantitativas = self.df.select_dtypes(include=["number"]).columns.tolist()
            cualitativas = self.df.select_dtypes(exclude=["number"]).columns.tolist()
            return {
                "columnas": self.df.columns.tolist(),
                "cuantitativas": cuantitativas,
                "cualitativas": cualitativas
            }
        except Exception as e:
            self._handle_error(e, "Error al obtener columnas")

    def obtener_estado(self) -> dict:
        """Retorna el estado actual — no necesita async porque no toca la DB."""
        return {"estado": self._estado}

    # ─── MÉTODOS PRIVADOS ────────────────────────────────────────────────────

    def _descargar_df(self, url: str, tipo: str) -> pd.DataFrame:
        """Descarga el archivo y lo convierte a DataFrame — sincrónico."""
        respuesta = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            allow_redirects=True,
        )
        respuesta.raise_for_status()

        if tipo == "csv":
            df = pd.read_csv(io.StringIO(respuesta.text))
        elif tipo in ("xlsx", "xls"):
            engine = "xlrd" if tipo == "xls" else "openpyxl"
            df = pd.read_excel(io.BytesIO(respuesta.content), engine=engine)
        else:
            raise ValueError(f"Tipo no soportado: '{tipo}'. Use 'csv', 'xlsx' o 'xls'")

        # Limpia nombres de columnas: elimina espacios al inicio/final
        df.columns = df.columns.str.strip()
        return df

    async def _guardar_dataset(self, sesion_id, url, tipo,
                                filas, columnas, cols_json, tiene_nulos) -> int:
        """INSERT en tabla datasets — asíncrono."""
        nuevo = Dataset(
            sesion_id=sesion_id,
            url_origen=url,
            tipo_archivo=tipo,
            total_filas=filas,
            total_columnas=columnas,
            columnas_json=json.dumps(cols_json),
            tiene_nulos=tiene_nulos
        )
        self.db.add(nuevo)
        await self.db.commit()
        await self.db.refresh(nuevo)

        self.logger.info(f"Dataset guardado en Neon con ID: {nuevo.id}")
        return nuevo.id

    def _verificar_df_cargado(self):
        """Verifica que haya un DataFrame en memoria."""
        if self.df is None:
            raise ValueError("No hay dataset cargado. Llame primero a cargar_datos()")