from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict, Union
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
import os

from auth import get_current_user

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

# Utilidad para manejar ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)

# Función para serializar objetos de MongoDB
def serialize_object_id(obj):
    if isinstance(obj, dict):
        return {key: serialize_object_id(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_object_id(element) for element in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj

# Modelos de datos
class Cliente(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    nombre: Optional[str] = None
    correo: str
    contraseña: Optional[str] = None
    rol: Optional[str] = None
    casas: List[str] = []

    class Config:
        json_encoders = {
            ObjectId: str
        }

class Casa(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    nombre: str
    direccion: str
    sensores: Optional[List[Dict[str, Union[str, Any]]]] = []

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

# Endpoint corregido
router = APIRouter()

@router.get("/clientes/casas/{cliente_correo}")
async def get_casas(cliente_correo: str, token: str = Depends(...)):  # Reemplaza `...` con tu dependencia de token.
    """
    Obtiene todas las casas asociadas a un cliente.
    """
    print(f"Correo recibido: {cliente_correo}")

    try:
        # Validar token y obtener usuario actual
        current_user = await get_current_user(token)  # Asegúrate de implementar `get_current_user`.

        # Validar que el correo coincida con el usuario autenticado
        if current_user.correo.strip().lower() != cliente_correo.strip().lower():
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para ver estas casas"
            )

        # Obtener el usuario en la base de datos
        usuario_db = await collection_cliente.find_one({"correo": cliente_correo})
        if not usuario_db:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        usuario_id = usuario_db["_id"]

        # Obtener las casas asociadas al usuario
        casas = await collection_casa.find({"usuario_id": usuario_id}).to_list(length=None)
        casas_serializable = serialize_object_id(casas)

        return {"data": casas_serializable}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error en la solicitud: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las casas: {str(e)}"
        )
