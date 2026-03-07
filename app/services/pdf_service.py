# app/services/pdf_service.py
# Genera el informe PDF profesional con los resultados del EDA.
# Usa reportlab para construir el documento con encabezado, gráficos e interpretación.

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base_service import BaseService
from app.services.analisis_service import AnalisisService
from app.models import Informe, Dataset

# ── Paleta de colores ──
AZUL_OSCURO  = colors.HexColor("#0f2b46")
AZUL_MEDIO   = colors.HexColor("#1a5276")
AZUL_CLARO   = colors.HexColor("#2e86c1")
AZUL_SUAVE   = colors.HexColor("#d6eaf8")
GRIS_CLARO   = colors.HexColor("#f2f3f4")
GRIS_BORDE   = colors.HexColor("#d5d8dc")
TEXTO_OSCURO = colors.HexColor("#2c3e50")
DORADO       = colors.HexColor("#d4ac0d")


class PdfService(BaseService):
    """
    Genera un informe PDF profesional con los resultados del EDA.
    Inserta gráficos, tablas de frecuencia, estadísticas e interpretaciones.
    """

    # Nombres de los integrantes — se muestran en el encabezado del informe
    INTEGRANTES = [
        "Alejandro Cantillo",
        "Junior Gutierrez",
        "Antony Ospino",
    ]

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.carpeta_informes = "Informes"
        os.makedirs(self.carpeta_informes, exist_ok=True)
        self._styles = getSampleStyleSheet()
        self._crear_estilos()

    # ─── ESTILOS PERSONALIZADOS ──────────────────────────────────────────────

    def _crear_estilos(self):
        """Define estilos personalizados para el PDF."""
        self._styles.add(ParagraphStyle(
            name="TituloInforme",
            parent=self._styles["Title"],
            fontSize=24,
            textColor=colors.white,
            spaceAfter=4,
            spaceBefore=0,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ))
        self._styles.add(ParagraphStyle(
            name="Subtitulo",
            parent=self._styles["Heading2"],
            fontSize=13,
            textColor=AZUL_OSCURO,
            spaceBefore=18,
            spaceAfter=6,
            fontName="Helvetica-Bold",
            borderPadding=(0, 0, 4, 0),
        ))
        self._styles.add(ParagraphStyle(
            name="SubtituloSeccion",
            parent=self._styles["Heading3"],
            fontSize=10,
            textColor=AZUL_MEDIO,
            spaceBefore=10,
            spaceAfter=4,
            fontName="Helvetica-BoldOblique",
        ))
        self._styles.add(ParagraphStyle(
            name="TextoCuerpo",
            parent=self._styles["BodyText"],
            fontSize=9,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=5,
            textColor=TEXTO_OSCURO,
        ))
        self._styles.add(ParagraphStyle(
            name="TextoPequeno",
            parent=self._styles["BodyText"],
            fontSize=7,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ))
        self._styles.add(ParagraphStyle(
            name="Integrantes",
            parent=self._styles["BodyText"],
            fontSize=10,
            textColor=TEXTO_OSCURO,
            alignment=TA_CENTER,
            spaceAfter=1,
        ))
        self._styles.add(ParagraphStyle(
            name="CeldaTabla",
            parent=self._styles["BodyText"],
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=TEXTO_OSCURO,
        ))
        self._styles.add(ParagraphStyle(
            name="CeldaTablaHeader",
            parent=self._styles["BodyText"],
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        ))
        self._styles.add(ParagraphStyle(
            name="InfoLabel",
            parent=self._styles["BodyText"],
            fontSize=9,
            textColor=AZUL_MEDIO,
            fontName="Helvetica-Bold",
            spaceAfter=0,
        ))
        self._styles.add(ParagraphStyle(
            name="InfoValue",
            parent=self._styles["BodyText"],
            fontSize=9,
            textColor=TEXTO_OSCURO,
            spaceAfter=0,
        ))

    # ─── HELPERS ─────────────────────────────────────────────────────────────

    def _seccion_divider(self) -> HRFlowable:
        """Línea decorativa entre secciones."""
        return HRFlowable(
            width="100%", thickness=0.5,
            color=GRIS_BORDE, spaceAfter=6, spaceBefore=6
        )

    def _tabla_estilo_base(self, header_color=AZUL_MEDIO):
        """Estilo base reutilizable para tablas."""
        return TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0), 8),
            ("FONTSIZE",       (0, 1), (-1, -1), 7),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.4, GRIS_BORDE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
        ])

    # ─── MÉTODO PÚBLICO PRINCIPAL ────────────────────────────────────────────

    async def generar_pdf(self, dataset_id: int, resultados: dict,
                          rutas_graficos: list, outliers_data: dict = None) -> dict:
        """
        Genera el informe PDF y registra en la BD.
        Retorna { mensaje, informe_id, ruta_pdf }.
        """
        try:
            self.logger.info(f"Generando informe PDF para dataset_id={dataset_id}")

            # Obtiene info del dataset desde la BD
            result = await self.db.execute(
                select(Dataset).filter(Dataset.id == dataset_id)
            )
            dataset = result.scalar_one_or_none()
            if not dataset:
                raise ValueError(f"No se encontró dataset con id={dataset_id}")

            # Nombre del archivo
            nombre_pdf = f"informe_{dataset_id}.pdf"
            ruta_pdf = os.path.join(self.carpeta_informes, nombre_pdf)

            # Construir el PDF
            self._construir_pdf(ruta_pdf, dataset, resultados, rutas_graficos, outliers_data)

            # Registrar en BD
            informe = Informe(
                dataset_id=dataset_id,
                ruta_pdf=ruta_pdf,
            )
            self.db.add(informe)
            await self.db.commit()
            await self.db.refresh(informe)

            self.logger.info(f"PDF generado: {ruta_pdf} — Informe ID: {informe.id}")

            return {
                "mensaje": "Informe generado",
                "informe_id": informe.id,
                "ruta_pdf": ruta_pdf,
            }

        except Exception as e:
            self._handle_error(e, "Error al generar el informe PDF")

    # ─── CONSTRUCCIÓN DEL PDF ────────────────────────────────────────────────

    def _construir_pdf(self, ruta: str, dataset, resultados: dict,
                       rutas_graficos: list, outliers_data: dict = None):
        """Arma el documento PDF completo con todas las secciones."""

        doc = SimpleDocTemplate(
            ruta,
            pagesize=letter,
            topMargin=1.2 * inch,
            bottomMargin=0.8 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        elementos = []

        # ── Encabezado ──
        elementos += self._seccion_encabezado(dataset)

        # ── Interpretación general ──
        elementos += self._seccion_interpretacion(resultados)

        # ── Valores nulos ──
        elementos += self._seccion_nulos(resultados)

        # ── Tablas de frecuencia ──
        elementos += self._seccion_frecuencias(resultados)

        # ── Estadísticas descriptivas ──
        elementos += self._seccion_estadisticas(resultados)

        # ── Tabla de contingencia ──
        elementos += self._seccion_contingencia(resultados)

        # ── Gráficos ──
        elementos += self._seccion_graficos(rutas_graficos)

        # ── Outliers (solo si el usuario lo pidió) ──
        if outliers_data:
            elementos += self._seccion_outliers(outliers_data)

        # Construir con encabezado/pie en cada página
        doc.build(
            elementos,
            onFirstPage=self._header_footer,
            onLaterPages=self._header_footer,
        )

    # ─── HEADER / FOOTER DE CADA PÁGINA ──────────────────────────────────────

    def _header_footer(self, canvas, doc):
        """Dibuja encabezado con franja de color y pie de página en cada hoja."""
        canvas.saveState()
        w, h = letter

        # ── Franja superior degradada (dos rectángulos) ──
        canvas.setFillColor(AZUL_OSCURO)
        canvas.rect(0, h - 44, w, 44, fill=True, stroke=False)
        # Línea dorada decorativa
        canvas.setFillColor(DORADO)
        canvas.rect(0, h - 47, w, 3, fill=True, stroke=False)

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(28, h - 28, "INFORME DE ANÁLISIS EXPLORATORIO DE DATOS")

        fecha = datetime.now().strftime("%d/%m/%Y  %H:%M")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 28, h - 28, fecha)

        # ── Pie de página ──
        # Línea dorada
        canvas.setFillColor(DORADO)
        canvas.rect(0, 27, w, 2, fill=True, stroke=False)
        # Franja oscura
        canvas.setFillColor(AZUL_OSCURO)
        canvas.rect(0, 0, w, 27, fill=True, stroke=False)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(28, 9, "Minería de Datos — Análisis Exploratorio")
        canvas.drawCentredString(w / 2, 9, "Documento generado automáticamente")
        canvas.drawRightString(w - 28, 9, f"Página {doc.page}")

        canvas.restoreState()

    # ─── SECCIONES DEL INFORME ───────────────────────────────────────────────

    def _seccion_encabezado(self, dataset) -> list:
        """Portada: título, integrantes y ficha técnica del dataset."""
        elems = []

        # ── Banner de título (tabla con fondo azul como bloque) ──
        titulo_data = [[
            Paragraph(
                "Informe de Análisis<br/>Exploratorio de Datos",
                self._styles["TituloInforme"]
            )
        ]]
        titulo_tabla = Table(titulo_data, colWidths=[6.5 * inch], rowHeights=[70])
        titulo_tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), AZUL_MEDIO),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ]))
        elems.append(Spacer(1, 6))
        elems.append(titulo_tabla)
        elems.append(Spacer(1, 12))

        # ── Integrantes ──
        nombres_str = "  •  ".join(self.INTEGRANTES)
        elems.append(Paragraph(
            f"<b>Equipo:</b>  {nombres_str}",
            self._styles["Integrantes"]
        ))
        elems.append(Spacer(1, 10))

        # ── Ficha técnica del dataset (tabla tipo tarjeta) ──
        fecha_str = datetime.now().strftime("%d de %B de %Y")
        url_corta = dataset.url_origen
        if len(url_corta) > 80:
            url_corta = url_corta[:77] + "..."

        ficha_data = [
            [Paragraph("<b>FICHA TÉCNICA DEL DATASET</b>", self._styles["CeldaTablaHeader"]),
             "", "", ""],
            [Paragraph("<b>Fuente</b>", self._styles["InfoLabel"]),
             Paragraph(url_corta, self._styles["InfoValue"]),
             Paragraph("<b>Formato</b>", self._styles["InfoLabel"]),
             Paragraph(dataset.tipo_archivo.upper(), self._styles["InfoValue"])],
            [Paragraph("<b>Filas</b>", self._styles["InfoLabel"]),
             Paragraph(f"{dataset.total_filas:,}", self._styles["InfoValue"]),
             Paragraph("<b>Columnas</b>", self._styles["InfoLabel"]),
             Paragraph(str(dataset.total_columnas), self._styles["InfoValue"])],
            [Paragraph("<b>Fecha</b>", self._styles["InfoLabel"]),
             Paragraph(fecha_str, self._styles["InfoValue"]),
             "", ""],
        ]
        ficha = Table(ficha_data, colWidths=[1 * inch, 2.5 * inch, 1 * inch, 2 * inch])
        ficha.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), AZUL_OSCURO),
            ("SPAN",          (0, 0), (-1, 0)),
            ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("BACKGROUND",    (0, 1), (-1, -1), AZUL_SUAVE),
            ("GRID",          (0, 0), (-1, -1), 0.4, GRIS_BORDE),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        elems.append(ficha)
        elems.append(Spacer(1, 8))
        elems.append(self._seccion_divider())
        return elems

    def _seccion_interpretacion(self, resultados: dict) -> list:
        """Sección de interpretación general con mensajes concatenados."""
        elems = []
        interpretacion = resultados.get("interpretacion", [])
        if not interpretacion:
            return elems

        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  1. Interpretación General',
            self._styles["Subtitulo"]
        ))

        for parrafo in interpretacion:
            parrafo_html = parrafo.replace("\n", "<br/>")
            # Envolver en tabla con borde izquierdo decorativo
            p = Paragraph(parrafo_html, self._styles["TextoCuerpo"])
            elems.append(p)

        elems.append(self._seccion_divider())
        return elems

    def _seccion_nulos(self, resultados: dict) -> list:
        """Sección de análisis de valores nulos."""
        elems = []
        nulos = resultados.get("nulos", {})
        if not nulos:
            return elems

        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  2. Análisis de Valores Nulos',
            self._styles["Subtitulo"]
        ))

        data = [["Columna", "Cantidad Nulos", "Porcentaje (%)"]]
        for col, info in nulos.items():
            data.append([col, str(info["cantidad"]), str(info["porcentaje"]) + "%"])

        tabla = Table(data, colWidths=[3.2 * inch, 1.4 * inch, 1.4 * inch])
        tabla.setStyle(self._tabla_estilo_base(AZUL_OSCURO))
        tabla.repeatRows = 1
        elems.append(tabla)
        elems.append(Spacer(1, 6))
        elems.append(self._seccion_divider())
        return elems

    def _seccion_frecuencias(self, resultados: dict) -> list:
        """Sección de tablas de frecuencia para columnas cualitativas."""
        elems = []
        frecuencias = resultados.get("frecuencias", {})
        if not frecuencias:
            return elems

        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  3. Tablas de Frecuencia',
            self._styles["Subtitulo"]
        ))

        for col, info in frecuencias.items():
            subtitulo = Paragraph(
                f"▸ Columna: <b>{col}</b>", self._styles["SubtituloSeccion"]
            )

            abs_dict = info.get("absoluta", {})
            rel_dict = info.get("relativa", {})

            data = [["Categoría", "Frec. Absoluta", "Frec. Relativa (%)"]]
            for cat in abs_dict:
                data.append([
                    str(cat),
                    str(abs_dict[cat]),
                    str(rel_dict.get(cat, "—")) + "%",
                ])

            tabla = Table(data, colWidths=[2.8 * inch, 1.5 * inch, 1.5 * inch])
            tabla.setStyle(self._tabla_estilo_base(AZUL_CLARO))
            tabla.repeatRows = 1
            # Mantener subtítulo + primeras filas juntos para evitar cortes
            elems.append(KeepTogether([subtitulo, tabla]))
            elems.append(Spacer(1, 8))

        elems.append(self._seccion_divider())
        return elems

    def _seccion_estadisticas(self, resultados: dict) -> list:
        """Sección de estadísticas descriptivas para columnas cuantitativas."""
        elems = []
        estadisticas = resultados.get("estadisticas", {})
        if not estadisticas:
            return elems

        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  4. Estadísticas Descriptivas',
            self._styles["Subtitulo"]
        ))

        for col, stats in estadisticas.items():
            subtitulo = Paragraph(
                f"▸ Columna: <b>{col}</b>", self._styles["SubtituloSeccion"]
            )

            data = [
                ["Estadístico", "Valor"],
                ["Media", str(stats.get("media", "—"))],
                ["Mediana", str(stats.get("mediana", "—"))],
                ["Desv. Estándar", str(stats.get("std", "—"))],
                ["Varianza", str(stats.get("varianza", "—"))],
                ["Mínimo", str(stats.get("minimo", "—"))],
                ["Máximo", str(stats.get("maximo", "—"))],
                ["Q1 (25%)", str(stats.get("q1", "—"))],
                ["Q3 (75%)", str(stats.get("q3", "—"))],
            ]

            tabla = Table(data, colWidths=[2.5 * inch, 2 * inch])
            estilo = self._tabla_estilo_base(AZUL_MEDIO)
            estilo.add("ALIGN", (0, 1), (0, -1), "LEFT")
            tabla.setStyle(estilo)
            tabla.repeatRows = 1
            elems.append(KeepTogether([subtitulo, tabla, Spacer(1, 8)]))

        elems.append(self._seccion_divider())
        return elems

    def _seccion_contingencia(self, resultados: dict) -> list:
        """Sección de tabla de contingencia."""
        elems = []
        contingencia = resultados.get("contingencia", {})
        if not contingencia:
            return elems

        subtitulo = Paragraph(
            '<font color="#d4ac0d">■</font>  5. Tabla de Contingencia',
            self._styles["Subtitulo"]
        )

        # Reconstruir la tabla cruzada desde el dict
        # contingencia = { col2_val: { col1_val: count, ... }, ... }
        col2_vals = list(contingencia.keys())
        col1_vals = set()
        for inner in contingencia.values():
            col1_vals.update(inner.keys())
        col1_vals = sorted(col1_vals, key=str)

        # Encabezado
        data = [[""] + [str(v) for v in col2_vals]]
        for c1 in col1_vals:
            fila = [str(c1)]
            for c2 in col2_vals:
                fila.append(str(contingencia[c2].get(c1, 0)))
            data.append(fila)

        # Calcular anchos dinámicos
        n_cols = len(col2_vals) + 1
        ancho_disponible = 6.5 * inch
        ancho_col = ancho_disponible / n_cols
        col_widths = [ancho_col] * n_cols

        tabla = Table(data, colWidths=col_widths)
        tabla.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
            ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#1a3c6e")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("TEXTCOLOR",     (0, 0), (0, -1), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4fa")]),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        tabla.repeatRows = 1
        elems.append(subtitulo)
        elems.append(tabla)
        elems.append(Spacer(1, 10))
        return elems

    def _seccion_graficos(self, rutas_graficos: list) -> list:
        """Sección con todos los gráficos generados."""
        elems = []

        graficos_validos = [r for r in rutas_graficos if os.path.exists(r)]
        if not graficos_validos:
            return elems

        elems.append(PageBreak())
        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  6. Gráficos',
            self._styles["Subtitulo"]
        ))

        for ruta in graficos_validos:
            nombre = os.path.basename(ruta).replace(".png", "").replace("_", " ").title()
            subtitulo = Paragraph(
                f"▸ <b>{nombre}</b>", self._styles["SubtituloSeccion"]
            )
            img = Image(ruta, width=6.2 * inch, height=2.6 * inch)
            img.hAlign = "CENTER"
            elems.append(KeepTogether([subtitulo, img, Spacer(1, 14)]))

        return elems

    def _seccion_outliers(self, outliers_data: dict) -> list:
        """
        Sección de tratamiento de outliers: interpretación, tabla resumen
        y gráficos comparativos antes/después. Solo se incluye si el usuario
        lo solicita con incluir_outliers=true.
        """
        elems = []
        reporte = outliers_data.get("reporte", {})
        graficos = outliers_data.get("graficos", [])
        metodo = outliers_data.get("metodo", "mediana")

        if not reporte:
            return elems

        elems.append(PageBreak())
        elems.append(Paragraph(
            '<font color="#d4ac0d">■</font>  7. Tratamiento de Outliers',
            self._styles["Subtitulo"]
        ))

        # ── Interpretación textual ──
        interpretacion = AnalisisService.generar_interpretacion_outliers(reporte, metodo)
        for parrafo in interpretacion:
            parrafo_html = parrafo.replace("\n", "<br/>")
            elems.append(Paragraph(parrafo_html, self._styles["TextoCuerpo"]))

        elems.append(Spacer(1, 10))

        # ── Tabla resumen de outliers ──
        subtitulo_resumen = Paragraph(
            f"▸ Resumen del tratamiento (método: <b>{metodo}</b>)",
            self._styles["SubtituloSeccion"]
        )

        data = [["Columna", "Outliers", "Valor Reemplazo", "Lím. Inferior", "Lím. Superior", "IQR"]]
        for col, info in reporte.items():
            n = info["outliers_detectados"]
            if n == 0:
                data.append([col, "0", "—", "—", "—", "—"])
            else:
                data.append([
                    col,
                    str(n),
                    f"{info['valor_reemplazo']:,.2f}",
                    f"{info.get('limite_inferior', 0):,.2f}",
                    f"{info.get('limite_superior', 0):,.2f}",
                    f"{info.get('iqr', 0):,.2f}",
                ])

        ancho_col = 6.5 * inch / 6
        tabla = Table(data, colWidths=[ancho_col] * 6)
        tabla.setStyle(self._tabla_estilo_base(AZUL_OSCURO))
        tabla.repeatRows = 1
        elems.append(KeepTogether([subtitulo_resumen, tabla]))
        elems.append(Spacer(1, 12))

        # ── Gráficos comparativos antes/después ──
        graficos_validos = [r for r in graficos if os.path.exists(r)]
        if graficos_validos:
            elems.append(Paragraph(
                "▸ Gráficos comparativos <b>antes / después</b>",
                self._styles["SubtituloSeccion"]
            ))

            for ruta in graficos_validos:
                nombre = os.path.basename(ruta).replace(".png", "").replace("_", " ").title()
                subtitulo_graf = Paragraph(
                    f"<b>{nombre}</b>", self._styles["SubtituloSeccion"]
                )
                img = Image(ruta, width=6.2 * inch, height=2.8 * inch)
                img.hAlign = "CENTER"
                elems.append(KeepTogether([subtitulo_graf, img, Spacer(1, 10)]))

        elems.append(self._seccion_divider())
        return elems
