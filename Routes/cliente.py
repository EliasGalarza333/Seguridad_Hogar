from email.quoprimime import unquote

from bson import ObjectId
from fastapi import APIRouter
from fastapi import HTTPException, Depends, status

from auth import get_current_user, oauth2_scheme, encriptar_contraseña
from Modelos.models import collection_gas, collection_humo, collection_magnetico, collection_movimiento, collection_sonido
from Modelos.user_models import Cliente, CambiarContraseñaRequest
from Modelos.user_models import collection_cliente, collection_casa
from pymongo import errors
from pydantic import ValidationError

router = APIRouter()

@router.get("/clientes/casas/{cliente_correo}")
async def get_casas(cliente_correo: str, token: str = Depends(oauth2_scheme)):


        # Verificar si el correo recibido es correcto
    print(f"Correo recibido: {cliente_correo}")
    """
    Obtiene todas las casas asociadas a un cliente.
    """
    print(f"Solicitud recibida para {cliente_correo}")

    try:
        # Validar token y obtener usuario actual
        current_user = await get_current_user(token)

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
        casas_serializable = [
            {
                "_id": str(casa["_id"]),
                "nombre": casa["nombre"],
                "direccion": casa["direccion"]
            }
            for casa in casas
        ]

        return {"data": casas_serializable}

    except ValidationError as ve:
        raise HTTPException(
            status_code=400,
            detail=f"Error de validación de datos: {str(ve)}"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error en la solicitud: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las casas: {str(e)}"
        )

# Obtener los sensores de la casa de cada cliente
@router.get("/clientes/casas/{usuario_id}/{casa_id}/sensores")
async def obtener_sensores_de_casa(
        usuario_id: str,
        casa_id: str,
        token: str = Depends(oauth2_scheme)
):
    try:
        # Validar el token y obtener usuario
        current_user = await get_current_user(token)

        # Validar permisos: Admin o el mismo usuario
        if str(current_user.id) != usuario_id and current_user.rol != "cliente":
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
                    "estado": sensor_info.get("estado", "desconocido"),
                    "fecha_hora": sensor_info.get("fecha_hora", ""),
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


# Endpoint para obtener la información del cliente
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

        # Eliminar la contraseña para no devolverla
        cliente_db.pop("_id", None)
        cliente_db.pop("contraseña", None)

        # Serializamos y devolvemos el cliente
        cliente = Cliente(**cliente_db)
        return cliente

    except Exception as e:
        # Agregar detalles del error en la respuesta para facilitar la depuración
        print(f"Error al obtener el perfil del cliente: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el perfil del cliente: {str(e)}"
        )


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