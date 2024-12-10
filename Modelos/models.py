
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
import os
from bson import ObjectId

# Configura la conexión con MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = AsyncIOMotorClient(MONGO_URL)
database = client['Hogar']

# Colecciones
collection_gas = database['Sensores_gas']
collection_humo = database['Sensores_humo']
collection_movimiento = database['Sensores_movimiento']
collection_sonido = database['Sensores_sonido']
collection_magnetico = database['Sensores_magnetico']

# Configuración del puerto serie
#arduino_port = 'COM6'  # Cambia el puerto según tu configuración
#baud_rate = 9600
#ser = serial.Serial(arduino_port, baud_rate)

# Modelos de datos
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
# Modelos de los sensores
class SensorGas(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    ubicacion: str
    tipo: str

class SensorHumo(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    ubicacion: str
    tipo: str

class SensorMovimiento(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    ubicacion: str
    tipo: str

class SensorSonido(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    ubicacion: str
    tipo: str

class SensorMagnetico(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    sensor_id: str
    ubicacion: str
    tipo: str

