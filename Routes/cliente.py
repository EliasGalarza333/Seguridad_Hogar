from bson import ObjectId
from fastapi import APIRouter
from fastapi import HTTPException, Depends, status
from typing import List
from auth import get_current_user, oauth2_scheme, encriptar_contraseña, generar_contraseña_aleatoria
from Modelos.models import collection_gas, collection_humo, collection_magnetico, collection_movimiento, collection_sonido
from Modelos.user_models import Cliente, CambiarContraseñaRequest, CasaInfo, CasaInfo1, RecuperarContraseñaRequest
from Modelos.user_models import collection_cliente, collection_casa
from enviar_email import enviar_correo_recuperacion
router = APIRouter()




# Ruta para actualizar la contraseña
@router.put("/clientes/actualizar-contraseña")
async def actualizar_contraseña(
        nueva_contraseña: CambiarContraseñaRequest,
        current_user: Cliente = Depends(get_current_user)
):
    # Lógica para cambiar la contraseña
    hashed_password = encriptar_contraseña(nueva_contraseña.nueva_contraseña)
    await collection_cliente.update_one(
        {"correo": current_user.correo},
        {"$set": {"contraseña": hashed_password}}
    )
    return {"detail": "Contraseña actualizada correctamente"}




# Función para convertir ObjectId a str
def convert_objectid(casas: List[dict]) -> List[CasaInfo]:
    """Convierte todos los ObjectIds dentro de un objeto o lista a strings y crea instancias de CasaInfo."""
    return [
        CasaInfo(
            id=str(casa["_id"]),
            nombre=casa["nombre"]
        ) for casa in casas
    ]
    
    # Función para convertir ObjectId a str
def convert1_objectid(casas: List[dict]) -> List[CasaInfo1]:
    """Convierte todos los ObjectIds dentro de un objeto o lista a strings y crea instancias de CasaInfo."""
    return [
        CasaInfo1(
            id=str(casa["_id"]),
            nombre=casa["nombre"],
            direccion=casa["direccion"]
        ) for casa in casas
    ]
    
# Endpoint para obtener solamente las casas y su ID
@router.get("/clientes/{cliente_id}/casas")
async def get_casas_de_cliente(cliente_id: str, token: str = Depends(oauth2_scheme)):
    try:
        # Validar el token y obtener el usuario actual
        current_user = await get_current_user(token)

        # Verificar que el cliente autenticado sea el propietario o tenga permisos de administrador
        if str(current_user.id) != cliente_id and current_user.rol != "admin":
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para acceder a estas casas"
            )

        # Buscar todas las casas asociadas al cliente
        casas = await collection_casa.find({"usuario_id": ObjectId(cliente_id)}).to_list(length=None)

        # Convertir los ObjectId a string y crear instancias de CasaInfo
        casas_serializable = convert_objectid(casas)

        # Ajuste de la estructura de la respuesta
        return {"data": casas_serializable}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las casas: {str(e)}"
        )

# Endpoint para obtener solamente las casas y su ID
@router.get("/clientes/{cliente_id}/casas-direccion")
async def get_casas_de_cliente(cliente_id: str, token: str = Depends(oauth2_scheme)):
    try:
        # Validar el token y obtener el usuario actual
        current_user = await get_current_user(token)

        # Verificar que el cliente autenticado sea el propietario o tenga permisos de administrador
        if str(current_user.id) != cliente_id and current_user.rol != "admin":
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para acceder a estas casas"
            )

        # Buscar todas las casas asociadas al cliente
        casas = await collection_casa.find({"usuario_id": ObjectId(cliente_id)}).to_list(length=None)

        # Convertir los ObjectId a string y crear instancias de CasaInfo
        casas_serializable = convert1_objectid(casas)

        # Ajuste de la estructura de la respuesta
        return {"data": casas_serializable}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las casas: {str(e)}"
        )


# En cliente.py

# Endpoint para obtener la información básica del cliente
@router.get("/clientes/perfil", response_model=Cliente)
async def get_cliente_perfil(current_user: Cliente = Depends(get_current_user)):
    try:
        # Buscar al cliente por su correo en la colección
        cliente_db = await collection_cliente.find_one({"correo": current_user.correo})
        if not cliente_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )

        # Crear un diccionario con solo la información requerida
        perfil_cliente = {
            "id": str(cliente_db["_id"]),
            "nombre": cliente_db.get("nombre", ""),
            "correo": cliente_db["correo"],
            "contraseña": None,
            "rol": None
        }

        # Serializamos y devolvemos el cliente
        cliente = Cliente(**perfil_cliente)
        return cliente

    except Exception as e:
        # Agregar detalles del error en la respuesta para facilitar la depuración
        print(f"Error al obtener el perfil del cliente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el perfil del cliente: {str(e)}"
        )

@router.post("/clientes/recuperar", status_code=status.HTTP_200_OK)
async def recuperar_contraseña(data: RecuperarContraseñaRequest):
    correo = data.correo
    try:
        # Verificar si el cliente existe
        cliente = await collection_cliente.find_one({"correo": correo})
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )

        # Generar una nueva contraseña temporal
        nueva_contraseña = generar_contraseña_aleatoria()

        # Encriptar la nueva contraseña
        nueva_contraseña_encriptada = encriptar_contraseña(nueva_contraseña)

        # Actualizar la contraseña en la base de datos
        await collection_cliente.update_one(
            {"_id": cliente["_id"]},
            {"$set": {"contraseña": nueva_contraseña_encriptada}}
        )

        # Enviar correo electrónico con la nueva contraseña
        correo_enviado = enviar_correo_recuperacion(cliente["correo"], nueva_contraseña)
        if not correo_enviado:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al enviar el correo electrónico"
            )

        return {"message": "Se ha enviado una nueva contraseña a tu correo electrónico"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al recuperar la contraseña: {str(e)}"
        )


# Nueva ruta para obtener sensores de una casa específica del cliente
@router.get("/clientes/{usuario_id}/casas/{casa_id}/sensores")
async def obtener_sensores_de_casa_especifica(
    
        usuario_id: str,
        casa_id: str,
        current_user: Cliente = Depends(get_current_user)
):
    try:
        # Validar permisos: Solo el propietario puede ver sus sensores
        if str(current_user.id) != usuario_id:
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para ver los sensores de esta casa"
            )

        # Verificar que la casa existe y pertenece al usuario
        casa = await collection_casa.find_one({"_id": ObjectId(casa_id), "usuario_id": ObjectId(usuario_id)})
        if not casa:
            raise HTTPException(status_code=404, detail="Casa no encontrada o no pertenece al usuario")

        # Obtener los sensores de la casa
        sensores_referencias = casa.get("sensores", [])
        sensores_detallados = []

        for sensor_ref in sensores_referencias:
            sensor_obj_id = sensor_ref.get("sensor_obj_id")
            sensor_tipo = sensor_ref.get("sensor_tipo")

            if not sensor_obj_id or not sensor_tipo:
                continue  # Saltar si la referencia no es válida

            sensor_info = None
            if sensor_tipo == "gas":
                sensor_info = await collection_gas.find_one({"_id": ObjectId(sensor_obj_id)})
            elif sensor_tipo == "humo":
                sensor_info = await collection_humo.find_one({"_id": ObjectId(sensor_obj_id)})
            elif sensor_tipo == "movimiento":
                sensor_info = await collection_movimiento.find_one({"_id": ObjectId(sensor_obj_id)})
            elif sensor_tipo == "sonido":
                sensor_info = await collection_sonido.find_one({"_id": ObjectId(sensor_obj_id)})
            elif sensor_tipo == "magnetico":
                sensor_info = await collection_magnetico.find_one({"_id": ObjectId(sensor_obj_id)})

            if sensor_info:
                # Formatear los datos del sensor para la respuesta
                sensor_serializable = {
                    "_id": str(sensor_info["_id"]),
                    "tipo": sensor_tipo,
                    "ubicacion": sensor_info.get("ubicacion", ""),
                    # Otros campos específicos del sensor según su tipo
                }
                sensores_detallados.append(sensor_serializable)

        return {"message": "Sensores obtenidos con éxito", "data": sensores_detallados}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los sensores: {str(e)}"
        )