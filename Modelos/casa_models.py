import os

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

# Configura la conexión con MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = AsyncIOMotorClient(MONGO_URL)
database = client['Hogar']

# Colecciones
collection_casa = database['Casa']

# Modelos de los sensores
class admin(BaseModel):
    nombre: str
    direccion: str
    sensores: str
    