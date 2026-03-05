# Carga las variables del archivo .env (DATABASE_URL, credenciales, etc.)
from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Lee la URL de conexión a Neon desde el .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Crea el motor de conexión a PostgreSQL (Neon)
# connect_args: SSL obligatorio para Neon
# pool_pre_ping: reintenta la conexión si Neon está en cold start
# pool_recycle: renueva conexiones cada 5 minutos para evitar timeouts
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True,
    pool_recycle=300
)

# Fábrica de sesiones — cada petición HTTP abre y cierra su propia sesión
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Clase base de la que heredan todos los modelos ORM
Base = declarative_base()

# Función generadora que FastAPI inyecta como dependencia en cada endpoint
# Garantiza que la sesión siempre se cierre, aunque ocurra un error
def get_db():
    db = SessionLocal()
    try:
        yield db        # entrega la sesión al endpoint
    finally:
        db.close()      # siempre se cierra al terminar la petición