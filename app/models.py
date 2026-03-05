from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


# ─── TABLA: sesiones ─────────────────────────────────────────────────────────
# Registra cada vez que un usuario inicia el flujo del chat
class Sesion(Base):
    __tablename__ = "sesiones"

    # Identificador único autoincremental
    id             = Column(Integer, primary_key=True, index=True)

    # Nombre completo ingresado por el usuario al inicio del chat
    nombre_usuario = Column(String(200), nullable=False)

    # Correo — se guarda al final del flujo cuando el usuario lo proporciona
    correo         = Column(String(200), nullable=True)

    # Timestamp automático del momento en que se creó la sesión
    fecha_consulta = Column(DateTime, server_default=func.now())

    # Estado del flujo: activa | completada | cancelada (si dijo "no" al EDA)
    estado_sesion  = Column(String(50), default="activa")


# ─── TABLA: datasets ─────────────────────────────────────────────────────────
# Registra cada dataset cargado — guarda metadatos, no el contenido completo
class Dataset(Base):
    __tablename__ = "datasets"

    # Identificador único autoincremental
    id                     = Column(Integer, primary_key=True, index=True)

    # Referencia a la sesión que cargó este dataset
    sesion_id              = Column(Integer, ForeignKey("sesiones.id"), nullable=False)

    # URL exacta proporcionada por el usuario para descargar el archivo
    url_origen             = Column(Text, nullable=False)

    # Formato del archivo descargado: "csv" o "xlsx"
    tipo_archivo           = Column(String(10), nullable=False)

    # Columnas que el usuario identificó como cuantitativas (separadas por coma)
    columnas_cuantitativas = Column(Text, nullable=True)

    # Columnas que el usuario identificó como cualitativas (separadas por coma)
    columnas_cualitativas  = Column(Text, nullable=True)

    # Lista completa de columnas del dataset en formato JSON (para referencia)
    columnas_json          = Column(Text, nullable=True)

    # Número de filas del dataset — obtenido con df.shape[0]
    total_filas            = Column(Integer, nullable=True)

    # Número de columnas del dataset — obtenido con df.shape[1]
    total_columnas         = Column(Integer, nullable=True)

    # True si al menos una columna tiene valores nulos
    tiene_nulos            = Column(Boolean, default=False)

    # Timestamp automático del momento en que el dataset fue cargado
    fecha_carga            = Column(DateTime, server_default=func.now())


# ─── TABLA: informes ─────────────────────────────────────────────────────────
# Registra cada PDF generado y el estado de su envío por correo
class Informe(Base):
    __tablename__ = "informes"

    # Identificador único autoincremental
    id               = Column(Integer, primary_key=True, index=True)

    # Referencia al dataset que originó este informe
    dataset_id       = Column(Integer, ForeignKey("datasets.id"), nullable=False)

    # Ruta local donde quedó guardado el PDF (ej: /informes/informe_3.pdf)
    ruta_pdf         = Column(Text, nullable=False)

    # Correo al que se envió el informe
    correo_enviado   = Column(String(200), nullable=True)

    # Estado del envío: pendiente | enviado | error_envio
    estado_envio     = Column(String(50), default="pendiente")

    # Timestamp automático del momento en que el PDF fue generado
    fecha_generacion = Column(DateTime, server_default=func.now())

    # Timestamp del envío exitoso — null hasta que el correo sea confirmado
    fecha_envio      = Column(DateTime, nullable=True)