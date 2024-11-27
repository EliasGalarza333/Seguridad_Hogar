from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import APIRouter
from fastapi import HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm

from auth import get_current_user, oauth2_scheme, create_access_token, generar_contraseña_aleatoria, \
    encriptar_contraseña, verificar_contraseña
from Modelos.models import collection_gas, collection_humo, collection_magnetico, collection_movimiento, collection_sonido
from Modelos.user_models import Cliente, Casa, SensorRequest, TokenResponse
from Modelos.user_models import collection_cliente, collection_casa

router = APIRouter()


# Login (ruta /login)
@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    print(f"Datos recibidos: username={form_data.username}, password={form_data.password}")

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
            "rol": cliente.rol,
            "casas": []
        }
        result = await collection_cliente.insert_one(new_cliente)

        # Recuperar el cliente creado
        created_cliente = await collection_cliente.find_one({"_id": result.inserted_id})

        # Mostrar al cliente su contraseña generada
        created_cliente["contraseña"] = contraseña_generada

        return Cliente(**created_cliente)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el cliente: {str(e)}"
        )
        
        
@router.get("/admin/clientes", response_model=List[Cliente])
async def get_clientes(current_user: Cliente = Depends(get_current_user)):
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver esta información"
        )

    try:
        cursor = collection_cliente.find(
            {"rol": "cliente"},
            {
                "nombre": 1,
                "correo": 1,
                "rol": 1,
                "casas": 1,
                "_id": 1  # Incluimos el _id para evitar problemas
            }
        )
        clientes = await cursor.to_list(length=None)

        for cliente in clientes:
            cliente.pop('contraseña', None)  # Eliminar el campo 'contraseña' si está presente

            # Cargar las casas completas, incluyendo sensores
            casas_completas = []
            for casa_id in cliente.get("casas", []):  # Obtener las casas de la lista de ObjectIds
                casa = await collection_casa.find_one({"_id": ObjectId(casa_id)})

                if casa:
                    # Usar jsonable_encoder para asegurar que los datos se serialicen correctamente
                    casa_serializable = jsonable_encoder(casa)

                    # Obtener los detalles de los sensores asociados a la casa
                    sensores_detallados = []
                    for sensor_id in casa.get("sensores", []):
                        # Dependiendo del tipo de sensor, buscamos en la colección correspondiente
                        sensor_info = None
                        if casa.get("sensor_tipo") == "gas":
                            sensor_info = await collection_gas.find_one({"_id": ObjectId(sensor_id)})
                        elif casa.get("sensor_tipo") == "humo":
                            sensor_info = await collection_humo.find_one({"_id": ObjectId(sensor_id)})
                        elif casa.get("sensor_tipo") == "movimiento":
                            sensor_info = await collection_movimiento.find_one({"_id": ObjectId(sensor_id)})
                        elif casa.get("sensor_tipo") == "sonido":
                            sensor_info = await collection_sonido.find_one({"_id": ObjectId(sensor_id)})
                        elif casa.get("sensor_tipo") == "magnetico":
                            sensor_info = await collection_magnetico.find_one({"_id": ObjectId(sensor_id)})

                        if sensor_info:
                            sensores_detallados.append(sensor_info)

                    # Agregamos los sensores detallados a la casa
                    casa_serializable["sensores"] = sensores_detallados
                    casas_completas.append(casa_serializable)

            # Agregamos las casas completas al cliente
            cliente["casas"] = casas_completas

        return [Cliente(**cliente) for cliente in clientes]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los usuarios: {str(e)}"
        )

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

        # Crear la casa en la colección de Casas
        nueva_casa = {
            "nombre": casa.nombre,
            "direccion": casa.direccion,
            "usuario_id": ObjectId(cliente_id),
            "sensores": casa.sensores
        }
        resultado = await collection_casa.insert_one(nueva_casa)
        nueva_casa["_id"] = resultado.inserted_id  # Agregar el ID generado a la casa

        # Actualizar el cliente para agregar el ID de la nueva casa
        await collection_cliente.update_one(
            {"_id": ObjectId(cliente_id)},
            {"$push": {"casas": nueva_casa["_id"]}},
            {"nombre":str},
            {"$push": {"casas": nueva_casa["nombre"]}}
        )

        # Devolver la casa creada como respuesta
        return Casa(**nueva_casa)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar la casa: {str(e)}"
        )
        

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

        # Convertir ObjectId a string para serialización
        casas_serializable = []
        for casa in casas:
            casa_serializable = {
                "_id": str(casa["_id"]),
                "nombre": casa["nombre"],
                "direccion": casa["direccion"],
                "usuario_id": str(casa["usuario_id"]),
                "sensores": casa.get("sensores", [])
            }
            casas_serializable.append(casa_serializable)

        return {"data": casas_serializable}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener las casas: {str(e)}"
        )

# Endpoint para ver los sensores asignados a cada casa de un cliente
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


# Endpoint para buscar clientes por nombre o correo
@router.get("/admin/clientes/buscar/", response_model=List[Cliente])
async def buscar_clientes( termino: str, current_user: dict = Depends(get_current_user)):
    
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta búsqueda"
        )
    
    try:
        # Buscar clientes que coincidan con el término en nombre o correo
        cursor = collection_cliente.find(
            {
                "rol": "cliente",
                "$or": [
                    {"nombre": {"$regex": termino, "$options": "i"}},
                    {"correo": {"$regex": termino, "$options": "i"}}
                ]
            },
            {"contraseña": 0}
        )
        
        clientes = await cursor.to_list(length=None)
        return clientes
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la búsqueda: {str(e)}"
        )
        
# Endpoint para obtener todos los clientes
@router.get("/clientes", response_model=List[Cliente])
async def get_clientes():
    try:
        # Obtiene solo los clientes con rol "cliente"
        clientes = await collection_cliente.find({"rol": "cliente"}).to_list(length=None)

        # Añadir la información completa de las casas para cada cliente
        for cliente in clientes:
            # Obtiene solo los ObjectId de las casas asociadas al cliente
            casas_completas = await collection_casa.find({"usuario_id": cliente["_id"]}).to_list(length=None)
            casas_ids = [casa["_id"] for casa in casas_completas]  # Solo los ObjectId
            cliente["casas"] = casas_ids  # Asigna los ObjectIds a cada cliente
            cliente.pop('contraseña', None)

        return [Cliente(**cliente) for cliente in clientes]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los usuarios: {str(e)}"
        )

