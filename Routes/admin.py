from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import APIRouter
from fastapi import HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from enviar_email import enviar_correo_bienvenida
from auth import get_current_user, oauth2_scheme, create_access_token, generar_contraseña_aleatoria, \
    encriptar_contraseña, verificar_contraseña
from Modelos.models import collection_gas, collection_humo, collection_magnetico, collection_movimiento, collection_sonido
from Modelos.user_models import Cliente, Casa, SensorRequest, TokenResponse, CasaInfo
from Modelos.user_models import collection_cliente, collection_casa

router = APIRouter()


# Login (ruta /login)
@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Busca al cliente en la base de datos por correo
    cliente = await collection_cliente.find_one({"correo": form_data.username})
    if not cliente:
        raise HTTPException(status_code=400, detail="Correo o contraseña incorrectos")

    # Verifica la contraseña
    if not verificar_contraseña(form_data.password, cliente["contraseña"]):
        raise HTTPException(status_code=400, detail="Correo o contraseña incorrectos")

    # Genera el token JWT incluyendo el rol
    access_token = create_access_token(data={
        "sub": cliente["correo"],  # El correo es el 'subject' del token
        "id": str(cliente["_id"]),
        "rol": cliente["rol"]  # Agregar rol al payload
    })

    return {"access_token": access_token, "token_type": "bearer"}


#Ruta de crear clientes y enviar email
@router.post("/admin/clientes", response_model=Cliente, status_code=status.HTTP_201_CREATED)
async def create_cliente(
    cliente: Cliente,
    current_user: Cliente = Depends(get_current_user)
):
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para crear clientes"
        )

    try:
        # Verificar si ya existe un cliente con el mismo correo
        existing_cliente = await collection_cliente.find_one({"correo": cliente.correo})
        if existing_cliente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un cliente con ese correo"
            )

        # Generar contraseña aleatoria
        contraseña_generada = generar_contraseña_aleatoria()

        # Encriptar la contraseña
        contraseña_encriptada = encriptar_contraseña(contraseña_generada)

        # Insertar el nuevo cliente en la base de datos
        new_cliente = {
            "nombre": cliente.nombre,
            "correo": cliente.correo,
            "contraseña": contraseña_encriptada,  # Guardar la contraseña encriptada
            "rol": cliente.rol or "cliente",  # Asignar rol cliente por defecto si no se especifica
            "casas": []
        }
        result = await collection_cliente.insert_one(new_cliente)

        # Recuperar el cliente creado
        created_cliente = await collection_cliente.find_one({"_id": result.inserted_id})

        # Enviar correo electrónico con la contraseña
        correo_enviado = enviar_correo_bienvenida(cliente.correo, contraseña_generada)
        
        if not correo_enviado:
            print(f"No se pudo enviar el correo de bienvenida a {cliente.correo}")

        # Convertir ObjectId a string y ocultar contraseña
        created_cliente["_id"] = str(created_cliente["_id"])
        created_cliente["contraseña"] = None

        return Cliente(**created_cliente)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el cliente: {str(e)}"
        )     
        
#Ruta para traer la información básica de todos los clientes
@router.get("/admin/clientes", response_model=List[Cliente])
async def get_clientes(current_user: Cliente = Depends(get_current_user)):
    # Verificamos que el usuario sea un admin
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta información"
        )

    try:
        # Realizamos la consulta a la base de datos
        cursor = collection_cliente.find(
            {"rol": "cliente"},
            {
                "nombre": 1,
                "correo": 1,
                "contraseña": 1,
                "rol": 1,
                "casas": 1,
                "_id": 1  # Incluimos el _id para evitar problemas
            }
        )
        clientes = await cursor.to_list(length=None)

        # Convertir ObjectIds a strings para serialización JSON
        for cliente in clientes:
            # Convertimos el ObjectId a str en el campo casas
            if "casas" in cliente:
                cliente["casas"] = [{"id": str(casa["_id"]), "nombre": casa["nombre"]} for casa in cliente["casas"]]

            # Aseguramos que el _id sea un string
            cliente["_id"] = str(cliente["_id"])

            # Eliminamos la contraseña antes de devolver la información
            cliente.pop('contraseña', None)

        return [Cliente(**cliente) for cliente in clientes]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los usuarios: {str(e)}"
        )

#Endpoint para crear la casa a un cliente
@router.post("/admin/clientes/{cliente_id}/casas", response_model=Casa, status_code=status.HTTP_201_CREATED)
async def agregar_casa_a_cliente(
    cliente_id: str, 
    casa: Casa, 
    current_user: Cliente = Depends(get_current_user)
):
    # Verificar si el usuario tiene permisos de administrador
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta acción"
        )

    try:
        # Verificar que el cliente existe
        cliente = await collection_cliente.find_one({"_id": ObjectId(cliente_id)})
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )

        # Crear la casa en la colección de Casas y agregar automáticamente el usuario_id
        nueva_casa = {
            "nombre": casa.nombre,
            "direccion": casa.direccion,
            "usuario_id": ObjectId(cliente_id),  # Mantener como ObjectId
            "sensores": casa.sensores  # Asignar sensores si los hay
        }
        resultado = await collection_casa.insert_one(nueva_casa)
        nueva_casa["_id"] = resultado.inserted_id  # Agregar el ID generado a la casa

        # Convertir el usuario_id de ObjectId a str para la respuesta
        nueva_casa["usuario_id"] = str(nueva_casa["usuario_id"])

        # Crear el objeto de la casa con solo el id y el nombre
        casa_objeto = {
            "_id": str(nueva_casa["_id"]),
            "nombre": nueva_casa["nombre"]
        }

        # Actualizar el cliente para agregar el objeto de la casa con id y nombre
        await collection_cliente.update_one(
            {"_id": ObjectId(cliente_id)},
            {"$push": {"casas": casa_objeto}}  # Guardar el objeto de la casa (id y nombre)
        )

        # Devolver la casa creada como respuesta, incluyendo el nombre
        return Casa(**nueva_casa)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar la casa: {str(e)}"
        )

        
#Endpoint para ver las casas de los clientes
@router.get("/admin/clientes/{cliente_id}/casas")
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

        # Convertir los ObjectId a string para asegurar la serialización correcta
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

# Endpoint para asignar sensores
@router.post("/admin/clientes/{usuario_id}/casas/{casa_id}/sensores")
async def agregar_sensor_a_casa(
    usuario_id: str,
    casa_id: str,
    sensor_request: SensorRequest,
    token: str = Depends(oauth2_scheme)
):
    try:
        # Validar el token y obtener usuario
        current_user = await get_current_user(token)

        # Validar permisos: Admin o el mismo usuario
        if str(current_user.id) != usuario_id and current_user.rol != "admin":
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para modificar esta casa"
            )

        # Verificar que la casa existe y pertenece al usuario
        casa = await collection_casa.find_one({"_id": ObjectId(casa_id), "usuario_id": ObjectId(usuario_id)})
        if not casa:
            raise HTTPException(status_code=404, detail="Casa no encontrada o no pertenece al usuario")

        # Determinar la colección de sensores según el tipo
        tipo_sensor = sensor_request.tipo_sensor
        sensor_collection = None
        if tipo_sensor == "gas":
            sensor_collection = collection_gas
        elif tipo_sensor == "humo":
            sensor_collection = collection_humo
        elif tipo_sensor == "movimiento":
            sensor_collection = collection_movimiento
        elif tipo_sensor == "sonido":
            sensor_collection = collection_sonido
        elif tipo_sensor == "magnetico":
            sensor_collection = collection_magnetico
        else:
            raise HTTPException(status_code=400, detail="Tipo de sensor no válido")

        # Insertar el sensor en la colección correspondiente
        sensor_data = sensor_request.sensor_data
        sensor_data["fecha_hora"] = datetime.utcnow()  # Agregar la fecha y hora actual
        sensor_data["tipo"] = tipo_sensor  # Asegurar que se almacene el tipo de sensor
        nuevo_sensor = await sensor_collection.insert_one(sensor_data)

        # Actualizar la casa con la referencia al sensor
        sensor_obj_id = nuevo_sensor.inserted_id
        await collection_casa.update_one(
            {"_id": ObjectId(casa_id)},
            {"$push": {"sensores": {"sensor_obj_id": sensor_obj_id, "sensor_tipo": tipo_sensor}}}
        )

        return {"message": "Sensor agregado exitosamente", "sensor_id": str(sensor_obj_id)}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al agregar el sensor a la casa: {str(e)}"
        )

# Endpoint para ver los sensores
@router.get("/admin/clientes/{usuario_id}/casas/{casa_id}/sensores")
async def obtener_sensores_de_casa(
    usuario_id: str,
    casa_id: str,
    token: str = Depends(oauth2_scheme)
):
    try:
        # Validar el token y obtener usuario
        current_user = await get_current_user(token)

        # Validar permisos: Admin o el mismo usuario
        if str(current_user.id) != usuario_id and current_user.rol != "admin":
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


@router.get("/admin/clientes", response_model=List[Cliente])
async def get_clientes():
    try:
        # Obtiene solo los clientes con rol "cliente"
        clientes = await collection_cliente.find({"rol": "cliente"}).to_list(length=None)

        # Iteramos sobre los clientes para estructurar las casas adecuadamente
        for cliente in clientes:
            # Si el cliente tiene casas, las extraemos
            if "casas" in cliente:
                # Convertimos manualmente los ObjectId a string para cada casa
                cliente["casas"] = [
                    {"id": str(casa["_id"]), "nombre": casa["nombre"]} for casa in cliente["casas"]
                ]

            # Eliminamos la contraseña antes de devolver la información
            cliente.pop('contraseña', None)

        # Devolvemos los clientes con la información correcta de casas
        return [Cliente(**cliente) for cliente in clientes]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los usuarios: {str(e)}"
        )

def convert_objectid(obj):
    """Convierte todos los ObjectIds dentro de un objeto o lista a strings."""
    if isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    return obj