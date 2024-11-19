# crud.py

from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Optional
from datetime import datetime
import os
from fastapi import HTTPException

# Modelos base
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

# Modelos para cada colección
class Admin(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    correo: str
    contraseña: str

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Cliente(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    nombres: str
    apellidos: str
    correo: str
    contraseña: str
    fecha_registro: datetime = Field(default_factory=datetime.utcnow)
    estado: str = "activo"
    sensores: List[str] = []  # Lista de IDs de sensores asignados al cliente

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Configura la conexión con MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = AsyncIOMotorClient(MONGO_URL)
database = client['Usuarios']

# Colecciones
collection_admin = database['admin']
collection_clientes = database['clientes']

# Funciones CRUD para Admin
async def create_admin(admin: Admin):
    admin_dict = admin.dict(by_alias=True)
    del admin_dict['_id']
    # Verificar si ya existe un admin con ese correo
    if await collection_admin.find_one({"correo": admin.correo}):
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    result = await collection_admin.insert_one(admin_dict)
    return await get_admin(result.inserted_id)

async def get_admin(admin_id: ObjectId):
    admin = await collection_admin.find_one({"_id": admin_id})
    if admin:
        return Admin(**admin)
    return None

async def get_admin_by_email(correo: str):
    admin = await collection_admin.find_one({"correo": correo})
    if admin:
        return Admin(**admin)
    return None

# Funciones CRUD para Clientes
async def create_cliente(cliente: Cliente):
    cliente_dict = cliente.dict(by_alias=True)
    del cliente_dict['_id']
    # Verificar si ya existe un cliente con ese correo
    if await collection_clientes.find_one({"correo": cliente.correo}):
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    result = await collection_clientes.insert_one(cliente_dict)
    return await get_cliente(result.inserted_id)

async def get_cliente(cliente_id: ObjectId):
    cliente = await collection_clientes.find_one({"_id": cliente_id})
    if cliente:
        return Cliente(**cliente)
    return None

async def get_cliente_by_email(correo: str):
    cliente = await collection_clientes.find_one({"correo": correo})
    if cliente:
        return Cliente(**cliente)
    return None

async def get_all_clientes():
    clientes = []
    async for cliente in collection_clientes.find():
        clientes.append(Cliente(**cliente))
    return clientes

async def update_cliente(cliente_id: ObjectId, cliente_data: dict):
    cliente = await collection_clientes.find_one({"_id": cliente_id})
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Evitar actualizar el ID
    if "_id" in cliente_data:
        del cliente_data["_id"]
    
    await collection_clientes.update_one(
        {"_id": cliente_id}, {"$set": cliente_data}
    )
    return await get_cliente(cliente_id)

async def delete_cliente(cliente_id: ObjectId):
    result = await collection_clientes.delete_one({"_id": cliente_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return {"detail": "Cliente eliminado exitosamente"}

# Funciones para manejar la relación entre clientes y sensores
async def assign_sensor_to_cliente(cliente_id: ObjectId, sensor_id: str):
    """Asigna un sensor a un cliente"""
    result = await collection_clientes.update_one(
        {"_id": cliente_id},
        {"$addToSet": {"sensores": sensor_id}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado o sensor ya asignado")
    return await get_cliente(cliente_id)

async def remove_sensor_from_cliente(cliente_id: ObjectId, sensor_id: str):
    """Elimina un sensor de un cliente"""
    result = await collection_clientes.update_one(
        {"_id": cliente_id},
        {"$pull": {"sensores": sensor_id}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado o sensor no asignado")
    return await get_cliente(cliente_id)

async def get_cliente_sensors(cliente_id: ObjectId):
    """Obtiene todos los sensores asignados a un cliente"""
    cliente = await get_cliente(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente.sensores

# crud.py

from pydantic import BaseModel, Field, EmailStr, validator
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Optional
from datetime import datetime
import os, re
from fastapi import HTTPException
from auth import get_password_hash, verify_password

# Modelos base
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

# Validadores comunes
class LocationValidator:
    @validator('ubicacion')
    def validate_ubicacion(cls, v):
        allowed_locations = ['sala', 'cocina', 'dormitorio', 'garage', 'jardín', 'entrada']
        if v.lower() not in allowed_locations:
            raise ValueError(f'Ubicación debe ser una de: {", ".join(allowed_locations)}')
        return v.lower()

# Modelos para cada colección con validaciones adicionales
class Admin(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    nombre: str
    correo: EmailStr
    contraseña: str

    @validator('nombre')
    def validate_nombre(cls, v):
        if not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{2,50}$', v):
            raise ValueError('El nombre solo puede contener letras y espacios (2-50 caracteres)')
        return v.title()

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Cliente(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    nombres: str
    apellidos: str
    correo: EmailStr
    contraseña: str
    fecha_registro: datetime = Field(default_factory=datetime.utcnow)
    estado: str = "activo"
    sensores: List[str] = []
    telefono: Optional[str] = None
    direccion: Optional[str] = None

    @validator('nombres', 'apellidos')
    def validate_nombres(cls, v):
        if not v.strip():
            raise ValueError('El campo no puede estar vacío')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{2,50}$', v):
            raise ValueError('Solo puede contener letras y espacios (2-50 caracteres)')
        return v.title()

    @validator('estado')
    def validate_estado(cls, v):
        estados_validos = ['activo', 'inactivo', 'suspendido']
        if v.lower() not in estados_validos:
            raise ValueError(f'Estado debe ser uno de: {", ".join(estados_validos)}')
        return v.lower()

    @validator('telefono')
    def validate_telefono(cls, v):
        if v is not None:
            if not re.match(r'^\+?1?\d{9,15}$', v):
                raise ValueError('Número de teléfono inválido')
        return v

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Configuración de MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = AsyncIOMotorClient(MONGO_URL)
database = client['Usuarios']

# Colecciones
collection_admin = database['admin']
collection_clientes = database['clientes']

# Funciones CRUD para Admin con seguridad mejorada
async def create_admin(admin: Admin):
    admin_dict = admin.dict(by_alias=True)
    # Encriptar contraseña
    admin_dict['contraseña'] = get_password_hash(admin_dict['contraseña'])
    del admin_dict['_id']
    
    # Verificar si ya existe un admin con ese correo
    if await collection_admin.find_one({"correo": admin.correo}):
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # Crear índice único para correo si no existe
    await collection_admin.create_index("correo", unique=True)
    
    result = await collection_admin.insert_one(admin_dict)
    return await get_admin(result.inserted_id)

async def verify_admin_credentials(correo: str, contraseña: str):
    admin = await collection_admin.find_one({"correo": correo})
    if not admin:
        return False
    if not verify_password(contraseña, admin['contraseña']):
        return False
    return Admin(**admin)

# Funciones CRUD para Clientes con seguridad mejorada
async def create_cliente(cliente: Cliente):
    cliente_dict = cliente.dict(by_alias=True)
    # Encriptar contraseña
    cliente_dict['contraseña'] = get_password_hash(cliente_dict['contraseña'])
    del cliente_dict['_id']
    
    # Verificar si ya existe un cliente con ese correo
    if await collection_clientes.find_one({"correo": cliente.correo}):
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    # Crear índice único para correo si no existe
    await collection_clientes.create_index("correo", unique=True)
    
    result = await collection_clientes.insert_one(cliente_dict)
    return await get_cliente(result.inserted_id)

async def verify_cliente_credentials(correo: str, contraseña: str):
    cliente = await collection_clientes.find_one({"correo": correo})
    if not cliente:
        return False
    if not verify_password(contraseña, cliente['contraseña']):
        return False
    return Cliente(**cliente)

async def update_cliente_password(cliente_id: ObjectId, old_password: str, new_password: str):
    cliente = await get_cliente(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Verificar la contraseña actual
    if not verify_password(old_password, cliente.contraseña):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    
    # Actualizar con la nueva contraseña hasheada
    await collection_clientes.update_one(
        {"_id": cliente_id},
        {"$set": {"contraseña": get_password_hash(new_password)}}
    )
    return {"detail": "Contraseña actualizada exitosamente"}

# Función de validación de sensor
async def validate_sensor_assignment(cliente_id: ObjectId, sensor_id: str):
    """Valida si un sensor puede ser asignado a un cliente"""
    # Verificar si el cliente existe
    cliente = await get_cliente(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Verificar si el sensor ya está asignado a otro cliente
    existing_assignment = await collection_clientes.find_one(
        {"sensores": sensor_id, "_id": {"$ne": cliente_id}}
    )
    if existing_assignment:
        raise HTTPException(
            status_code=400, 
            detail="Este sensor ya está asignado a otro cliente"
        )
    
    # Verificar límite de sensores por cliente (ejemplo: máximo 10)
    if len(cliente.sensores) >= 10:
        raise HTTPException(
            status_code=400,
            detail="El cliente ha alcanzado el límite máximo de sensores"
        )
    
    return True

# Las demás funciones CRUD permanecen igual...