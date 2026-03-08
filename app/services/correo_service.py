# app/services/correo_service.py
# Servicio para el envío de informes por correo electrónico vía SMTP.

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.header import Header
from email import encoders
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base_service import BaseService
from app.models import Informe, Sesion, Usuario

load_dotenv()


class CorreoService(BaseService):
    """
    Envía el informe PDF por correo electrónico usando SMTP (Gmail).
    Variables de entorno requeridas: SMTP_EMAIL, SMTP_PASSWORD
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.smtp_email = os.getenv("SMTP_EMAIL", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))

    # ─── MÉTODO PÚBLICO PRINCIPAL ────────────────────────────────────────────

    async def enviar_informe(self, informe_id: int, correo_destino: str,
                              sesion_id: int, resultados: dict = None,
                              outliers_data: dict = None) -> dict:
        """
        Envía el PDF adjunto al correo del usuario.
        Obtiene el nombre del usuario a partir de la sesión.
        Actualiza el registro del informe en la BD con el estado del envío.
        """
        try:
            self.logger.info(f"Enviando informe {informe_id} a {correo_destino}")

            # Obtener el informe de la BD
            result = await self.db.execute(
                select(Informe).filter(Informe.id == informe_id)
            )
            informe = result.scalar_one_or_none()
            if not informe:
                raise ValueError(f"No se encontró informe con id={informe_id}")

            if not os.path.exists(informe.ruta_pdf):
                raise FileNotFoundError(f"PDF no encontrado: {informe.ruta_pdf}")

            # Obtener nombre del usuario a partir de la sesión
            result_sesion = await self.db.execute(
                select(Sesion).filter(Sesion.id == sesion_id)
            )
            sesion = result_sesion.scalar_one_or_none()
            if not sesion:
                raise ValueError(f"No se encontró sesión con id={sesion_id}")

            result_usuario = await self.db.execute(
                select(Usuario).filter(Usuario.id == sesion.usuario_id)
            )
            usuario = result_usuario.scalar_one_or_none()
            if not usuario:
                raise ValueError(f"No se encontró usuario con id={sesion.usuario_id}")

            nombre_completo = f"{usuario.nombre} {usuario.apellido}"

            # Guardar el correo en el usuario si aún no lo tiene
            if not usuario.correo:
                usuario.correo = correo_destino

            # Enviar el correo
            self._enviar_smtp(
                destino=correo_destino,
                nombre=nombre_completo,
                ruta_pdf=informe.ruta_pdf,
                resultados=resultados,
                outliers_data=outliers_data,
            )

            # Actualizar estado en BD
            informe.correo_enviado = correo_destino
            informe.estado_envio = "enviado"
            informe.fecha_envio = datetime.utcnow()

            # Marcar la sesión como completada — el flujo terminó
            sesion.estado_sesion = "completada"

            await self.db.commit()

            self.logger.info(f"Informe enviado exitosamente a {correo_destino}")

            return {
                "mensaje": "Informe enviado",
                "correo": correo_destino,
            }

        except Exception as e:
            # Marcar error en BD si se pudo obtener el informe
            try:
                if informe:
                    informe.estado_envio = "error_envio"
                    await self.db.commit()
            except Exception:
                pass
            self._handle_error(e, "Error al enviar el informe por correo")

    # ─── MÉTODO PRIVADO — ENVÍO SMTP ────────────────────────────────────────

    def _enviar_smtp(self, destino: str, nombre: str, ruta_pdf: str,
                     resultados: dict = None, outliers_data: dict = None):
        """Construye y envía el email con el PDF adjunto."""

        if not self.smtp_email or not self.smtp_password:
            raise ValueError(
                "Credenciales SMTP no configuradas. "
                "Defina SMTP_EMAIL y SMTP_PASSWORD en el archivo .env"
            )

        msg = MIMEMultipart("mixed")
        msg["From"] = self.smtp_email
        msg["To"] = destino
        msg["Subject"] = Header(
            f"Informe de Analisis Exploratorio - {nombre}", "utf-8"
        )

        fecha_str = datetime.now().strftime("%d/%m/%Y a las %H:%M")

        # Parte alternativa (texto plano + HTML)
        cuerpo = MIMEMultipart("alternative")
        texto_plano = (
            f"Estimado/a {nombre},\n\n"
            f"Adjunto encontrará el informe de análisis exploratorio de datos "
            f"generado el {fecha_str}.\n\n"
            f"Saludos cordiales,\n"
            f"Equipo de Análisis de Datos"
        )
        cuerpo.attach(MIMEText(texto_plano, "plain", "utf-8"))

        # Cuerpo HTML profesional
        html = f"""\
        <html>
        <head>
          <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            .header {{ background: linear-gradient(135deg, #0f2b46, #1a5276); padding: 28px 30px; text-align: center; }}
            .header h1 {{ color: #ffffff; font-size: 20px; margin: 0 0 4px 0; }}
            .header p {{ color: #d4ac0d; font-size: 12px; margin: 0; letter-spacing: 1px; }}
            .body-content {{ padding: 28px 30px; color: #2c3e50; line-height: 1.7; font-size: 14px; }}
            .body-content p {{ margin: 0 0 14px 0; }}
            .greeting {{ font-size: 16px; font-weight: 600; }}
            .info-box {{ background: #d6eaf8; border-left: 4px solid #2e86c1; padding: 14px 18px; border-radius: 4px; margin: 18px 0; }}
            .info-box h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #1a5276; }}
            .info-box ul {{ margin: 0; padding-left: 18px; color: #2c3e50; font-size: 13px; }}
            .info-box li {{ margin-bottom: 4px; }}
            .footer {{ background: #0f2b46; padding: 18px 30px; text-align: center; }}
            .footer p {{ color: #aab7c4; font-size: 11px; margin: 0 0 4px 0; }}
            .footer a {{ color: #d4ac0d; text-decoration: none; }}
            .divider {{ height: 2px; background: linear-gradient(90deg, #d4ac0d, #2e86c1); margin: 0; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1>📊 Informe de Análisis Exploratorio</h1>
              <p>MINERÍA DE DATOS — GENERADO EL {fecha_str.upper()}</p>
            </div>
            <div class="divider"></div>
            <div class="body-content">
              <p class="greeting">Estimado/a {nombre},</p>
              <p>
                Se ha generado exitosamente su informe de análisis exploratorio de datos.
                El documento PDF se encuentra adjunto a este correo para su revisión.
              </p>
              <div class="info-box">
                <h3>📋 Análisis realizados</h3>
                <ul>
{self._generar_lista_analisis_html(resultados, outliers_data)}
                </ul>
              </div>
              <p>
                Si tiene alguna pregunta sobre los resultados, no dude en contactarnos.
              </p>
              <p style="margin-top: 24px;">
                Atentamente,<br/>
                <strong>Equipo de Análisis de Datos</strong><br/>
                <span style="color: #7f8c8d; font-size: 12px;">Minería de Datos — Análisis Exploratorio</span>
              </p>
            </div>
            <div class="footer">
              <p>Este es un correo generado automáticamente.</p>
              <p>© {datetime.now().year} — Equipo de Análisis de Datos</p>
            </div>
          </div>
        </body>
        </html>
        """
        cuerpo.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(cuerpo)

        # Adjuntar PDF
        nombre_archivo = os.path.basename(ruta_pdf)
        with open(ruta_pdf, "rb") as f:
            adjunto = MIMEBase("application", "octet-stream")
            adjunto.set_payload(f.read())
        encoders.encode_base64(adjunto)
        adjunto.add_header(
            "Content-Disposition",
            f"attachment; filename={nombre_archivo}"
        )
        msg.attach(adjunto)

        # Conectar y enviar
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_email, self.smtp_password)
            server.send_message(msg)

    def _generar_lista_analisis_html(self, resultados: dict = None,
                                      outliers_data: dict = None) -> str:
        """Genera las líneas <li> con el resumen de análisis para el email HTML."""
        if not resultados:
            return (
                "                  <li>Interpretación general del conjunto de datos</li>\n"
                "                  <li>Análisis de valores nulos y limpieza de datos</li>\n"
                "                  <li>Tablas de frecuencia por variable cualitativa</li>\n"
                "                  <li>Estadísticas descriptivas por variable cuantitativa</li>\n"
                "                  <li>Gráficos de distribución y frecuencia</li>"
            )

        items = []

        # Valores nulos
        nulos = resultados.get("nulos", {})
        if nulos:
            items.append("✅ Análisis de valores nulos")
        else:
            items.append("❌ Análisis de valores nulos — no ejecutado")

        # Limpieza
        limpieza = resultados.get("limpieza", {})
        if limpieza:
            items.append("✅ Limpieza de datos")
        else:
            items.append("❌ Limpieza de datos — no ejecutada")

        # Frecuencias
        frecuencias = resultados.get("frecuencias", {})
        if frecuencias:
            items.append(f"✅ Tablas de frecuencia ({len(frecuencias)} columnas)")
        else:
            items.append("❌ Tablas de frecuencia — sin columnas cualitativas")

        # Estadísticas
        estadisticas = resultados.get("estadisticas", {})
        if estadisticas:
            items.append(f"✅ Estadísticas descriptivas ({len(estadisticas)} columnas)")
        else:
            items.append("❌ Estadísticas descriptivas — sin columnas cuantitativas")

        # Contingencia
        contingencia = resultados.get("contingencia", {})
        if contingencia:
            items.append("✅ Tabla de contingencia")
        else:
            items.append("❌ Tabla de contingencia — se requieren al menos 2 columnas cualitativas")

        # Gráficos
        items.append("✅ Gráficos de distribución y frecuencia")

        # Outliers
        if outliers_data:
            items.append(f"✅ Tratamiento de outliers (método: {outliers_data.get('metodo', '?')})")
        else:
            items.append("❌ Tratamiento de outliers — no solicitado")

        return "\n".join(f"                  <li>{item}</li>" for item in items)
