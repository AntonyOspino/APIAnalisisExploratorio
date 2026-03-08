# app/services/analisis_service.py

import os
import re
import json
import matplotlib
matplotlib.use("Agg")  # evita errores de GUI en servidor — debe ir antes de importar pyplot
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select
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

    async def ejecutar(self, df: pd.DataFrame, dataset_id: int,
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

            # 1. Análisis de valores nulos (ANTES de limpiar)
            self.resultados["nulos"] = self._analizar_nulos(df)

            # 2. Limpieza de datos
            df, self.resultados["limpieza"] = self._limpiar_datos(df, cols_cuant, cols_cual)

            # 3. Tablas de frecuencia para columnas cualitativas
            self.resultados["frecuencias"] = self._tablas_frecuencia(df, cols_cual)

            # 4. Estadísticas descriptivas para columnas cuantitativas
            self.resultados["estadisticas"] = self._estadisticas_cuant(df, cols_cuant)

            # 5. Tabla de contingencia entre las dos primeras cualitativas
            self.resultados["contingencia"] = self._tabla_contingencia(df, cols_cual)

            # 6. Gráficos para cada columna cualitativa
            for col in cols_cual:
                if col in df.columns:
                    ruta = self._grafico_cualitativo(df, col)
                    self.rutas_graficos.append(ruta)

            # 7. Gráficos para cada columna cuantitativa
            for col in cols_cuant:
                if col in df.columns:
                    ruta = self._grafico_cuantitativo(df, col)
                    self.rutas_graficos.append(ruta)

            # 8. Interpretación en lenguaje natural
            self.resultados["interpretacion"] = self.generar_interpretacion(
                df, cols_cuant, cols_cual
            )

            # 9. Guarda las columnas seleccionadas en Neon
            await self._guardar_columnas(dataset_id, cols_cuant, cols_cual)

            self.logger.info(f"EDA completado. Gráficos generados: {len(self.rutas_graficos)}")

            return {
                "mensaje": "Análisis completado",
                "graficos": self.rutas_graficos
            }

        except Exception as e:
            self._handle_error(e, "Error al ejecutar el análisis exploratorio")

    # ─── MÉTODOS PRIVADOS — LIMPIEZA ───────────────────────────────────────────

    def _limpiar_datos(self, df: pd.DataFrame, cols_cuant: list, cols_cual: list) -> tuple:
        """
        Limpia el DataFrame antes del análisis:
          - Elimina filas completamente vacías
          - Elimina filas duplicadas
          - Rellena nulos en cuantitativas con la mediana
          - Rellena nulos en cualitativas con la moda
          - Corrige tipos: fuerza numéricas en cuantitativas, string en cualitativas
          - Recorta espacios en blanco en columnas de texto
        Retorna (df_limpio, reporte_limpieza).
        """
        self.logger.info("Iniciando limpieza de datos")
        reporte = {}
        filas_antes = len(df)

        # 1. Eliminar filas completamente vacías
        df = df.dropna(how="all")
        reporte["filas_vacias_eliminadas"] = filas_antes - len(df)

        # 2. Eliminar duplicados
        filas_pre_dup = len(df)
        df = df.drop_duplicates()
        reporte["duplicados_eliminados"] = filas_pre_dup - len(df)

        # 3. Corregir tipos y limpiar cuantitativas
        for col in cols_cuant:
            if col not in df.columns:
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")
            mediana = df[col].median()
            nulos = int(df[col].isnull().sum())
            if nulos > 0:
                df[col] = df[col].fillna(mediana)
                reporte[f"{col}_nulos_rellenados"] = nulos

        # 4. Corregir tipos y limpiar cualitativas
        for col in cols_cual:
            if col not in df.columns:
                continue
            df[col] = df[col].astype(str).str.strip()
            # Reemplazar 'nan' (resultado de astype(str) sobre NaN) con la moda
            moda = df.loc[df[col] != "nan", col].mode()
            valor_moda = moda.iloc[0] if not moda.empty else "Desconocido"
            mask = df[col] == "nan"
            nulos = int(mask.sum())
            if nulos > 0:
                df.loc[mask, col] = valor_moda
                reporte[f"{col}_nulos_rellenados"] = nulos

        reporte["filas_despues"] = len(df)
        reporte["filas_antes"] = filas_antes
        self.logger.info(f"Limpieza completada: {filas_antes} → {len(df)} filas")

        return df, reporte

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
        # Incluye nombres de las variables para el PDF
        return {
            "tabla": tabla.to_dict(),
            "variable_fila": col1,
            "variable_columna": col2,
        }

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
        sns.barplot(x=top_valores.index, y=top_valores.values, ax=ax1, hue=top_valores.index, palette="Blues_d", legend=False)
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

        nombre_seguro = self._sanitizar_nombre(col)
        ruta = os.path.join(self.carpeta_graficos, f"cual_{nombre_seguro}.png")
        plt.savefig(ruta, dpi=150, bbox_inches="tight")
        plt.close()  # libera memoria — importante en servidor

        return ruta

    def _grafico_cuantitativo(self, df: pd.DataFrame, col: str) -> str:
        """
        Genera tres gráficos para una columna cuantitativa:
          - Histograma con curva KDE
          - Boxplot (con stripplot si la distribución está muy concentrada)
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
        sns.boxplot(y=serie, ax=ax2, color="lightblue", width=0.4)

        # Si IQR ≈ 0 (distribución muy concentrada), agrega puntos individuales
        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        if q3 - q1 < 0.01 * (serie.max() - serie.min() + 1):
            sns.stripplot(y=serie, ax=ax2, color="steelblue", alpha=0.3, size=3, jitter=True)
            ax2.set_title("Boxplot + puntos (datos muy concentrados)")
        else:
            ax2.set_title("Boxplot — detección de outliers")

        ax2.set_ylabel(col)

        plt.tight_layout()

        nombre_seguro = self._sanitizar_nombre(col)
        ruta = os.path.join(self.carpeta_graficos, f"cuant_{nombre_seguro}.png")
        plt.savefig(ruta, dpi=150, bbox_inches="tight")
        plt.close()

        return ruta

    @staticmethod
    def _sanitizar_nombre(nombre: str) -> str:
        """Elimina caracteres no válidos para nombres de archivo en Windows."""
        return re.sub(r'[<>:"/\\|?*\s]+', '_', nombre).strip('_')

    # ─── MÉTODO PRIVADO — PERSISTENCIA ───────────────────────────────────────

    async def _guardar_columnas(self, dataset_id: int, cols_cuant: list, cols_cual: list):
        """
        Actualiza el registro del dataset en Neon con las columnas
        cuantitativas y cualitativas indicadas por el usuario.
        """
        self.logger.info(f"Guardando columnas en Neon para dataset_id={dataset_id}")

        result = await self.db.execute(
        select(Dataset).filter(Dataset.id == dataset_id)
        )
        dataset = result.scalar_one_or_none()

        if not dataset:
            raise ValueError(f"No se encontró dataset con id={dataset_id}")

        dataset.columnas_cuantitativas = ",".join(cols_cuant)
        dataset.columnas_cualitativas  = ",".join(cols_cual)

        await self.db.commit()
        self.logger.info("Columnas guardadas correctamente en Neon")

    # ─── MÉTODO PRIVADO — INTERPRETACIÓN ─────────────────────────────────────

    def generar_interpretacion(self, df: pd.DataFrame,
                                cols_cuant: list, cols_cual: list) -> list:
        """
        Genera una lista de párrafos interpretativos en lenguaje natural
        a partir de los resultados del EDA. Se usa en el informe PDF.
        """
        textos = []
        total_filas = len(df)
        total_cols = len(df.columns)

        # ── Intro general ──
        textos.append(
            f"El conjunto de datos analizado contiene {total_filas} registros "
            f"y {total_cols} columnas. De estas, {len(cols_cuant)} son cuantitativas "
            f"({', '.join(cols_cuant)}) y {len(cols_cual)} son cualitativas "
            f"({', '.join(cols_cual)})."
        )

        # ── Interpretación de nulos ──
        nulos = self.resultados.get("nulos", {})
        cols_con_nulos = {k: v for k, v in nulos.items() if v["cantidad"] > 0}
        if cols_con_nulos:
            lineas = [f"Se detectaron valores nulos en {len(cols_con_nulos)} columna(s):"]
            for col, info in cols_con_nulos.items():
                lineas.append(
                    f"  - '{col}' tiene {info['cantidad']} valores nulos "
                    f"({info['porcentaje']}% del total)."
                )
            textos.append("\n".join(lineas))
        else:
            textos.append("No se detectaron valores nulos en ninguna columna del dataset.")

        # ── Interpretación de limpieza ──
        limpieza = self.resultados.get("limpieza", {})
        if limpieza:
            partes = []
            vacias = limpieza.get("filas_vacias_eliminadas", 0)
            dups = limpieza.get("duplicados_eliminados", 0)
            if vacias > 0:
                partes.append(f"se eliminaron {vacias} filas completamente vacías")
            if dups > 0:
                partes.append(f"se eliminaron {dups} filas duplicadas")
            rellenos = [k for k in limpieza if k.endswith("_nulos_rellenados")]
            if rellenos:
                partes.append(
                    f"se rellenaron valores nulos en {len(rellenos)} columna(s) "
                    f"usando la mediana (cuantitativas) o la moda (cualitativas)"
                )
            if partes:
                textos.append(
                    "Durante la limpieza de datos: " + "; ".join(partes) + ". "
                    f"El dataset pasó de {limpieza.get('filas_antes', '?')} a "
                    f"{limpieza.get('filas_despues', '?')} filas."
                )

        # ── Interpretación de frecuencias (cualitativas) ──
        frecuencias = self.resultados.get("frecuencias", {})
        for col, info in frecuencias.items():
            abs_dict = info.get("absoluta", {})
            rel_dict = info.get("relativa", {})
            if abs_dict:
                top_cat = max(abs_dict, key=abs_dict.get)
                top_val = abs_dict[top_cat]
                top_pct = rel_dict.get(top_cat, 0)
                n_cats = len(abs_dict)
                textos.append(
                    f"La columna cualitativa '{col}' presenta {n_cats} categorías "
                    f"distintas. La categoría más frecuente es '{top_cat}' con "
                    f"{top_val} apariciones ({top_pct}% del total)."
                )

        # ── Interpretación de estadísticas (cuantitativas) ──
        estadisticas = self.resultados.get("estadisticas", {})
        for col, stats in estadisticas.items():
            media = stats.get("media", 0)
            mediana = stats.get("mediana", 0)
            std = stats.get("std", 0)
            minimo = stats.get("minimo", 0)
            maximo = stats.get("maximo", 0)

            # Detección de asimetría por comparación media vs mediana
            if abs(media - mediana) < 0.05 * std if std > 0 else True:
                asimetria = "simétrica"
            elif media > mediana:
                asimetria = "sesgada hacia la derecha (asimetría positiva)"
            else:
                asimetria = "sesgada hacia la izquierda (asimetría negativa)"

            textos.append(
                f"La columna cuantitativa '{col}' tiene un promedio de {media} "
                f"con desviación estándar de {std}. El valor mínimo es {minimo} "
                f"y el máximo es {maximo}. La mediana es {mediana}, lo que indica "
                f"una distribución {asimetria}."
            )

        # ── Interpretación de contingencia ──
        contingencia = self.resultados.get("contingencia", {})
        if contingencia:
            col1 = contingencia.get("variable_fila", "?")
            col2 = contingencia.get("variable_columna", "?")
            tabla_dict = contingencia.get("tabla", {})
            total_combos = sum(
                len(inner) for inner in tabla_dict.values()
            )
            textos.append(
                f"La tabla de contingencia entre '{col1}' y '{col2}' muestra "
                f"la distribución cruzada de ambas variables con "
                f"{total_combos} combinaciones registradas."
            )

        return textos

    # ─── MÉTODOS PÚBLICOS — TRATAMIENTO DE OUTLIERS ──────────────────────────

    def tratar_outliers(self, df: pd.DataFrame, columnas: list, metodo: str) -> tuple:
        """
        Detecta outliers con IQR (igual que boxplot) y los reemplaza.
        Métodos: 'media', 'mediana', 'moda'.
        Retorna (df_tratado, reporte, rutas_graficos).
        """
        metodos_validos = ("media", "mediana", "moda")
        if metodo not in metodos_validos:
            raise ValueError(f"Método '{metodo}' no válido. Use: {metodos_validos}")

        reporte = {}
        rutas = []

        for col in columnas:
            if col not in df.columns:
                self.logger.warning(f"Columna '{col}' no encontrada, se omite")
                continue

            serie = df[col].dropna()
            q1 = serie.quantile(0.25)
            q3 = serie.quantile(0.75)
            iqr = q3 - q1
            limite_inf = q1 - 1.5 * iqr
            limite_sup = q3 + 1.5 * iqr

            # Máscara de outliers
            mask = (df[col] < limite_inf) | (df[col] > limite_sup)
            n_outliers = int(mask.sum())

            if n_outliers == 0:
                reporte[col] = {
                    "outliers_detectados": 0,
                    "valor_reemplazo": None
                }
                continue

            # Calcular valor de reemplazo según el método elegido
            if metodo == "media":
                valor = round(float(serie.mean()), 4)
            elif metodo == "mediana":
                valor = round(float(serie.median()), 4)
            else:  # moda
                moda = serie.mode()
                valor = round(float(moda.iloc[0]), 4) if not moda.empty else round(float(serie.median()), 4)

            # Gráfico comparativo ANTES de reemplazar
            ruta = self._grafico_outliers(df, col, mask, limite_inf, limite_sup, valor, metodo)
            rutas.append(ruta)

            # Reemplazar outliers
            df.loc[mask, col] = valor

            reporte[col] = {
                "outliers_detectados": n_outliers,
                "valor_reemplazo": valor,
                "limite_inferior": round(float(limite_inf), 4),
                "limite_superior": round(float(limite_sup), 4),
                "q1": round(float(q1), 4),
                "q3": round(float(q3), 4),
                "iqr": round(float(iqr), 4)
            }

            self.logger.info(
                f"'{col}': {n_outliers} outliers reemplazados con {metodo}={valor}"
            )

        return df, reporte, rutas

    def _grafico_outliers(self, df: pd.DataFrame, col: str,
                          mask: pd.Series, lim_inf: float, lim_sup: float,
                          valor_reemplazo: float, metodo: str) -> str:
        """
        Genera un gráfico comparativo: boxplot ANTES vs boxplot DESPUÉS
        del tratamiento de outliers. Usa misma escala en ambos ejes para
        que la diferencia sea visualmente clara.
        """
        serie_antes = df[col].dropna()
        serie_despues = df[col].copy()
        serie_despues.loc[mask] = valor_reemplazo
        serie_despues = serie_despues.dropna()
        n_out = int(mask.sum())

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(
            f"Tratamiento de outliers en '{col}' (método: {metodo})",
            fontsize=14, fontweight="bold"
        )

        # Escala compartida para que se note la diferencia
        y_min = min(serie_antes.min(), serie_despues.min())
        y_max = max(serie_antes.max(), serie_despues.max())
        margen = (y_max - y_min) * 0.08
        for ax in axes:
            ax.set_ylim(y_min - margen, y_max + margen)

        # ── ANTES ──
        ax1 = axes[0]
        sns.boxplot(y=serie_antes, ax=ax1, color="salmon", width=0.4)
        # Resaltar los outliers como puntos rojos
        outlier_vals = serie_antes[mask.reindex(serie_antes.index, fill_value=False)]
        if len(outlier_vals) > 0:
            ax1.scatter(
                [0] * len(outlier_vals), outlier_vals,
                color="red", zorder=5, s=30, alpha=0.6, label=f"Outliers ({n_out})"
            )
        ax1.axhline(y=lim_sup, color="darkred", linestyle="--", alpha=0.7,
                     label=f"Lím. sup: {lim_sup:,.2f}")
        ax1.axhline(y=lim_inf, color="darkred", linestyle="--", alpha=0.7,
                     label=f"Lím. inf: {lim_inf:,.2f}")
        ax1.set_title(f"ANTES — {n_out} outliers detectados", fontsize=12)
        ax1.set_ylabel(col)
        ax1.legend(fontsize=8, loc="upper right")
        ax1.grid(axis="y", alpha=0.3)

        # ── DESPUÉS ──
        ax2 = axes[1]
        sns.boxplot(y=serie_despues, ax=ax2, color="lightgreen", width=0.4)
        ax2.axhline(y=valor_reemplazo, color="blue", linestyle="--", alpha=0.8,
                     label=f"{metodo}: {valor_reemplazo:,.2f}")
        ax2.set_title(f"DESPUÉS — outliers reemplazados por {metodo}", fontsize=12)
        ax2.set_ylabel(col)
        ax2.legend(fontsize=8, loc="upper right")
        ax2.grid(axis="y", alpha=0.3)

        # Caja de texto con resumen numérico
        resumen = (
            f"Outliers: {n_out}\n"
            f"Valor reemplazo: {valor_reemplazo:,.2f}\n"
            f"IQR: {(lim_sup - lim_inf) / 3:,.2f}\n"
            f"Rango original: [{serie_antes.min():,.2f}, {serie_antes.max():,.2f}]\n"
            f"Rango nuevo: [{serie_despues.min():,.2f}, {serie_despues.max():,.2f}]"
        )
        fig.text(0.5, -0.02, resumen, ha="center", fontsize=9,
                 fontstyle="italic", color="gray",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8))

        plt.tight_layout(rect=[0, 0.08, 1, 0.95])

        nombre_seguro = self._sanitizar_nombre(col)
        ruta = os.path.join(self.carpeta_graficos, f"outliers_{nombre_seguro}.png")
        plt.savefig(ruta, dpi=150, bbox_inches="tight")
        plt.close()

        return ruta

    @staticmethod
    def generar_interpretacion_outliers(reporte: dict, metodo: str) -> list:
        """
        Genera párrafos interpretativos sobre el tratamiento de outliers.
        Se usa en el informe PDF cuando el usuario lo solicita.
        """
        textos = []

        total_outliers = sum(info["outliers_detectados"] for info in reporte.values())
        cols_afectadas = [col for col, info in reporte.items() if info["outliers_detectados"] > 0]
        cols_sin = [col for col, info in reporte.items() if info["outliers_detectados"] == 0]

        if total_outliers == 0:
            textos.append(
                "No se detectaron valores atípicos (outliers) en ninguna de las "
                "columnas analizadas mediante el método del rango intercuartílico (IQR)."
            )
            return textos

        textos.append(
            f"Se realizó un tratamiento de valores atípicos (outliers) utilizando el "
            f"método del rango intercuartílico (IQR). Los valores fuera del rango "
            f"[Q1 − 1.5×IQR, Q3 + 1.5×IQR] fueron reemplazados por la {metodo} "
            f"de cada columna. En total se detectaron {total_outliers} outliers "
            f"distribuidos en {len(cols_afectadas)} columna(s)."
        )

        for col in cols_afectadas:
            info = reporte[col]
            n = info["outliers_detectados"]
            val = info["valor_reemplazo"]
            q1 = info.get("q1", 0)
            q3 = info.get("q3", 0)
            lim_inf = info.get("limite_inferior", 0)
            lim_sup = info.get("limite_superior", 0)
            iqr = info.get("iqr", 0)

            textos.append(
                f"En la columna '{col}' se encontraron {n} valores atípicos. "
                f"El rango intercuartílico es {iqr:,.2f} (Q1={q1:,.2f}, Q3={q3:,.2f}), "
                f"lo que define límites aceptables entre {lim_inf:,.2f} y {lim_sup:,.2f}. "
                f"Los {n} valores fuera de este rango fueron reemplazados por la "
                f"{metodo} ({val:,.2f}), reduciendo la dispersión y el impacto del "
                f"ruido en los análisis posteriores."
            )

        if cols_sin:
            textos.append(
                f"Las columnas {', '.join(cols_sin)} no presentaron outliers según "
                f"el criterio IQR, por lo que no requirieron tratamiento."
            )

        return textos