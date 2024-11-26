import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext  # instalar bycricpt pip install bcrypt

from Modelos.user_models import Cliente, collection_cliente

# Configuración del JWT
SECRET_KEY = os.getenv("SECRET_KEY", "clave_por_defecto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Crear token
# Funciones de autenticación
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Decodificar token
def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido o expirado"
        )

async def get_current_user_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        rol: str = payload.get("rol")
        if correo is None:
            return None
        
        # Verificar si el usuario existe en la base de datos
        user = await collection_cliente.find_one({"correo": correo})
        if user is None:
            return None
            
        return {"correo": correo, "rol": rol}
    except JWTError:
        return None
    
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Cliente:
    try:
        # Decodificar el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        rol: str = payload.get("rol")

        # Validar los datos extraídos del token
        if correo is None or rol is None:
            raise HTTPException(status_code=401, detail="Token inválido")

        # Buscar el usuario en la base de datos
        user = await collection_cliente.find_one({"correo": correo})
        if user is None:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")

        # Retornar el usuario como un objeto Cliente
        return Cliente(**user)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")




# Esta función decodifica el token JWT y devuelve el usuario correspondiente
async def get_current_user_id(token: str = Depends(oauth2_scheme))-> Cliente:
    credentials_exception = HTTPException(
        status_code=401,
        detail="No se pudo validar las credenciales",
    )
    
    try:
        # Decodificar el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Buscar el usuario en la base de datos usando el ID
        user = await collection_cliente.find_one({"_id": user_id})
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception



# Verificar rol
def verify_admin(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if payload.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para realizar esta acción"
        )
    return payload



# Configuración de bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generar_contraseña_aleatoria():
    import random
    import string
    longitud = 12
    caracteres = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choices(caracteres, k=longitud))

def encriptar_contraseña(contraseña: str) -> str:
    return pwd_context.hash(contraseña)

def verificar_contraseña(contraseña_plana: str, contraseña_encriptada: str) -> bool:
    return pwd_context.verify(contraseña_plana, contraseña_encriptada)