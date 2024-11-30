from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict, Union
from bson import ObjectId
import os

# Configuración de MongoDB
MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority"
)
client = AsyncIOMotorClient(MONGO_URL)
database = client['Hogar']

# Colecciones

collection_cliente = database['Usuarios']
collection_casa = database['Casas']

# Modelos de datos
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value, config):
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)
    
    
def serialize_object_id(obj):
    """Convierte ObjectId a string en un diccionario"""
    if isinstance(obj, dict):
        return {key: serialize_object_id(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_object_id(element) for element in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj


    
class Cliente(BaseModel):
    id: PyObjectId | None = Field(None, alias="_id")
    nombre: str | None = None
    correo: str
    contraseña: str | None = None
    rol: str | None = None
    casas: list[PyObjectId] = []
    
    class Config:
        # Esta configuración es para permitir el uso de ObjectId como tipo válido en Pydantic
        json_encoders = {
            ObjectId: str  # Convierte ObjectId a string para la serialización
        }

class Casa(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    direccion: str
    sensores: Optional[List[Dict[str, Union[PyObjectId, str]]]] = []

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str
        }
        
class TokenData(BaseModel):
    correo: str 
    role: str 

class SensorRequest(BaseModel):
    tipo_sensor: str
    sensor_data: Dict[str, Any]
    class Config:
        arbitrary_types_allowed = True
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    
class CambiarContraseñaRequest(BaseModel):
    nueva_contraseña: str
