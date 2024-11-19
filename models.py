import json
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import os
import time

# Configura la conexión con MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = AsyncIOMotorClient(MONGO_URL)
database = client['Ejemplos']

# Colecciones
collection_gas = database['Sensores_gas']
collection_humo = database['Sensores_humo']
collection_movimiento = database['Sensores_movimiento']
collection_sonido = database['Sensores_sonido']
collection_magnetico = database['Sensores_magnetico']

# Modelos de los sensores
class SensorGas(BaseModel):
    sensor_id: str
    ubicacion: str
    nivel_gas: int
    fecha_hora: datetime
    estado: str

class SensorHumo(BaseModel):
    sensor_id: str
    ubicacion: str
    nivel_humo: int
    nivel_toxicidad: int
    fecha_hora: datetime
    estado: str

class SensorMovimiento(BaseModel):
    sensor_id: str
    ubicacion: str
    intensidad: int
    fecha_hora: datetime
    estado: str

class SensorSonido(BaseModel):
    sensor_id: str
    ubicacion: str
    nivel_sonido: int
    fecha_hora: datetime
    estado: str

class SensorMagnetico(BaseModel):
    sensor_id: str
    ubicacion: str
    estado: str
    fecha_hora: datetime


