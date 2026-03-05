# app/services/analisis_service.py

import os
import json
import matplotlib
matplotlib.use("Agg")  # evita errores de GUI en servidor — debe ir antes de importar pyplot
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.models import Dataset


class AnalisisService(BaseService):
    """
    Ejecuta el EDA completo sobre el DataFrame recibido.
    Genera gráficos PNG en /graficos/ y retorna los resultados
    para que PdfService los use al construir el informe.
    Hereda de BaseService: self.db, self.logger, self._handle_error()
    """

    def __init__(self, db: Session):
        super().__init__(db)

        # Diccionario con todos los resultados del EDA
        # Estructura: { "nulos": {...}, "frecuencias": {...}, "estadisticas": {...}, "contingencia": {...} }
        self.resultados: dict = {}

        # Lista de rutas PNG generados — se pasan a PdfService
        self.rutas_graficos: list = []

        # Carpeta donde se guardan los PNG
        self.carpeta_graficos = "graficos"
        os.makedirs(self.carpeta_graficos, exist_ok=True)

    # ─── MÉTODO PÚBLICO PRINCIPAL ────────────────────────────────────────────

    def ejecutar(self, df: pd.DataFrame, dataset_id: int,
                 cols_cuant: list, cols_cual: list) -> dict:
        """
        Orquesta todo el EDA en orden.
        Recibe el DataFrame desde el route (que lo obtiene de DatosService).
        Actualiza las columnas cuant/cual en la tabla datasets de Neon.
        """
        try:
            self.logger.info(f"Iniciando EDA para dataset_id={dataset_id}")

            # Limpia resultados anteriores si se llama más de una vez
            self.resultados = {}
            self.rutas_graficos = []

            # 1. Análisis de valores nulos
            self.resultados["nulos"] = self._analizar_nulos(df)

            # 2. Tablas de frecuencia para columnas cualitativas
            self.resultados["frecuencias"] = self._tablas_frecuencia(df, cols_cual)

            # 3. Estadísticas descriptivas para columnas cuantitativas
            self.resultados["estadisticas"] = self._estadisticas_cuant(df, cols_cuant)

            # 4. Tabla de contingencia entre las dos primeras cualitativas
            self.resultados["contingencia"] = self._tabla_contingencia(df, cols_cual)

            # 5. Gráficos para cada columna cualitativa
            for col in cols_cual:
                if col in df.columns:
                    ruta = self._grafico_cualitativo(df, col)
                    self.rutas_graficos.append(ruta)

            # 6. Gráficos para cada columna cuantitativa
            for col in cols_cuant:
                if col in df.columns:
                    ruta = self._grafico_cuantitativo(df, col)
                    self.rutas_graficos.append(ruta)

            # 7. Guarda las columnas seleccionadas en Neon
            self._guardar_columnas(dataset_id, cols_cuant, cols_cual)

            self.logger.info(f"EDA completado. Gráficos generados: {len(self.rutas_graficos)}")

            return {
                "mensaje": "Análisis completado",
                "graficos": self.rutas_graficos
            }

        except Exception as e:
            self._handle_error(e, "Error al ejecutar el análisis exploratorio")

    # ─── MÉTODOS PRIVADOS — ANÁLISIS ─────────────────────────────────────────

    def _analizar_nulos(self, df: pd.DataFrame) -> dict:
        """
        Detecta valores nulos por columna.
        Retorna cantidad y porcentaje de nulos para cada columna.
        """
        self.logger.info("Analizando valores nulos")

        total_filas = len(df)
        resultado = {}

        for col in df.columns:
            cantidad = int(df[col].isnull().sum())
            porcentaje = round((cantidad / total_filas) * 100, 2)
            resultado[col] = {
                "cantidad": cantidad,
                "porcentaje": porcentaje
            }

        return resultado

    def _tablas_frecuencia(self, df: pd.DataFrame, cols_cual: list) -> dict:
        """
        Genera tabla de frecuencias para cada columna cualitativa.
        Retorna frecuencia absoluta y relativa por valor.
        """
        self.logger.info(f"Generando tablas de frecuencia para: {cols_cual}")

        resultado = {}

        for col in cols_cual:
            if col not in df.columns:
                self.logger.warning(f"Columna '{col}' no encontrada en el dataset")
                continue

            # Frecuencia absoluta
            frec_abs = df[col].value_counts()

            # Frecuencia relativa en porcentaje
            frec_rel = df[col].value_counts(normalize=True) * 100

            resultado[col] = {
                # Convierte a dict para que sea serializable a JSON
                "absoluta": frec_abs.to_dict(),
                "relativa": {k: round(v, 2) for k, v in frec_rel.to_dict().items()}
            }

        return resultado

    def _estadisticas_cuant(self, df: pd.DataFrame, cols_cuant: list) -> dict:
        """
        Calcula estadísticas descriptivas para columnas cuantitativas.
        Incluye media, mediana, desviación estándar, mínimo, máximo y cuartiles.
        """
        self.logger.info(f"Calculando estadísticas para: {cols_cuant}")

        resultado = {}

        for col in cols_cuant:
            if col not in df.columns:
                self.logger.warning(f"Columna '{col}' no encontrada en el dataset")
                continue

            serie = df[col].dropna()  # ignora nulos para el cálculo

            resultado[col] = {
                "media":     round(float(serie.mean()), 2),
                "mediana":   round(float(serie.median()), 2),
                "std":       round(float(serie.std()), 2),
                "minimo":    round(float(serie.min()), 2),
                "maximo":    round(float(serie.max()), 2),
                "q1":        round(float(serie.quantile(0.25)), 2),
                "q3":        round(float(serie.quantile(0.75)), 2),
                "varianza":  round(float(serie.var()), 2)
            }

        return resultado

    def _tabla_contingencia(self, df: pd.DataFrame, cols_cual: list) -> dict:
        """
        Genera tabla de contingencia cruzando las dos primeras columnas cualitativas.
        Si hay menos de dos cualitativas retorna dict vacío.
        """
        if len(cols_cual) < 2:
            self.logger.warning("Se necesitan al menos 2 columnas cualitativas para la contingencia")
            return {}

        col1, col2 = cols_cual[0], cols_cual[1]
        self.logger.info(f"Generando tabla de contingencia: '{col1}' x '{col2}'")

        tabla = pd.crosstab(df[col1], df[col2])

        # Convierte a dict anidado para serialización JSON
        return tabla.to_dict()

    # ─── MÉTODOS PRIVADOS — GRÁFICOS ─────────────────────────────────────────

    def _grafico_cualitativo(self, df: pd.DataFrame, col: str) -> str:
        """
        Genera dos gráficos para una columna cualitativa:
          - Gráfico de barras (countplot)
          - Gráfico de torta (pie)
        Los guarda como un solo PNG en /graficos/ y retorna la ruta.
        """
        self.logger.info(f"Generando gráfico cualitativo para: {col}")

        # Limita a los 10 valores más frecuentes para legibilidad
        top_valores = df[col].value_counts().head(10)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f"Análisis de '{col}'", fontsize=14, fontweight="bold")

        # ── Gráfico de barras ──
        sns.barplot(x=top_valores.index, y=top_valores.values, ax=ax1, palette="Blues_d")
        ax1.set_title("Frecuencia por categoría")
        ax1.set_xlabel(col)
        ax1.set_ylabel("Cantidad")
        ax1.tick_params(axis="x", rotation=45)

        # ── Gráfico de torta ──
        ax2.pie(
            top_valores.values,
            labels=top_valores.index,
            autopct="%1.1f%%",  # muestra el porcentaje en cada sector
            startangle=90
        )
        ax2.set_title("Distribución porcentual")

        plt.tight_layout()

        # Nombre del archivo — reemplaza espacios por guiones bajos
        ruta = os.path.join(self.carpeta_graficos, f"cual_{col.replace(' ', '_')}.png")
        plt.savefig(ruta, dpi=150, bbox_inches="tight")
        plt.close()  # libera memoria — importante en servidor

        return ruta

    def _grafico_cuantitativo(self, df: pd.DataFrame, col: str) -> str:
        """
        Genera tres gráficos para una columna cuantitativa:
          - Histograma con curva KDE
          - Boxplot
        Los guarda como un solo PNG en /graficos/ y retorna la ruta.
        """
        self.logger.info(f"Generando gráfico cuantitativo para: {col}")

        serie = df[col].dropna()  # ignora nulos para graficar

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle(f"Distribución de '{col}'", fontsize=14, fontweight="bold")

        # ── Histograma con KDE ──
        sns.histplot(serie, kde=True, ax=ax1, color="steelblue")
        ax1.set_title("Histograma + Densidad (KDE)")
        ax1.set_xlabel(col)
        ax1.set_ylabel("Frecuencia")

        # ── Boxplot ──
        sns.boxplot(y=serie, ax=ax2, color="lightblue")
        ax2.set_title("Boxplot — detección de outliers")
        ax2.set_ylabel(col)

        plt.tight_layout()

        ruta = os.path.join(self.carpeta_graficos, f"cuant_{col.replace(' ', '_')}.png")
        plt.savefig(ruta, dpi=150, bbox_inches="tight")
        plt.close()

        return ruta

    # ─── MÉTODO PRIVADO — PERSISTENCIA ───────────────────────────────────────

    def _guardar_columnas(self, dataset_id: int, cols_cuant: list, cols_cual: list):
        """
        Actualiza el registro del dataset en Neon con las columnas
        cuantitativas y cualitativas indicadas por el usuario.
        """
        self.logger.info(f"Guardando columnas en Neon para dataset_id={dataset_id}")

        dataset = self.db.query(Dataset).filter(Dataset.id == dataset_id).first()

        if not dataset:
            raise ValueError(f"No se encontró dataset con id={dataset_id}")

        # Guarda como string separado por comas
        dataset.columnas_cuantitativas = ",".join(cols_cuant)
        dataset.columnas_cualitativas  = ",".join(cols_cual)

        self.db.commit()
        self.logger.info("Columnas guardadas correctamente en Neon")