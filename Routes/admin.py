from datetime import datetime
from typing import List

from bson import ObjectId
from fastapi import APIRouter
from fastapi import HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm

from Routes.cliente import convert_objectid
from enviar_email import enviar_correo_bienvenida
from auth import get_current_user, oauth2_scheme, create_access_token, generar_contraseña_aleatoria, \
    encriptar_contraseña, verificar_contraseña, token_blacklist
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



# Endpoint de Logout
@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Cierra la sesión del usuario actual invalidando su token JWT.
    
    - No requiere body
    - Requiere token de autorización Bearer
    - Agrega el token actual a una lista negra
    """
    # Agregar token a lista negra
    token_blacklist.add(token)
    
    return {"message": "Sesión cerrada exitosamente"}



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
        correo_enviado = await enviar_correo_bienvenida(cliente.correo, contraseña_generada)

        if not correo_enviado:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"El cliente fue creado pero no se pudo enviar el correo de bienvenida a {cliente.correo}"
            )

        # Convertir ObjectId a string y ocultar contraseña
        created_cliente["_id"] = str(created_cliente["_id"])
        created_cliente["contraseña"] = None

        return Cliente(**created_cliente)

    except HTTPException as http_exc:
        raise http_exc  # Relanzar excepciones HTTP ya manejadas

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el cliente: {str(e)}"
        )       
#Ruta para traer la información básica de todos los clientes

@router.get("/admin/clientes", response_model=List[Cliente])
async def get_clientes():
    try:
        # Obtiene solo los clientes con rol "cliente"
        clientes = await collection_cliente.find({"rol": "cliente"}).to_list(length=None)

        for cliente in clientes:
            # Si el cliente tiene casas, aseguramos que tengan el formato esperado
            casas = cliente.get("casas", [])
            cliente["casas"] = [
                {
                    "id": str(casa["_id"]) if isinstance(casa.get("_id"), ObjectId) else casa.get("id", ""),
                    "nombre": casa.get("nombre", "Sin nombre")
                }
                for casa in casas if isinstance(casa, dict)
            ]

            # Eliminamos la contraseña antes de devolver la información
            cliente.pop("contraseña", None)

        # Devolvemos los clientes con la información correcta de casas
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
            "nombre": nueva_casa["nombre"],
            "direccion": nueva_casa["direccion"]
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
        #sensor_data["_id"] = tipo_sensor  # Agrega el id
        sensor_data["nombre"] = tipo_sensor  # AAgrega el nombre
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

'''
@router.get("/admin/clientes", response_model=List[Cliente])
async def get_clientes():
    try:
        # Obtiene solo los clientes con rol "cliente"
        clientes = await collection_cliente.find({"rol": "cliente"}).to_list(length=None)

        for cliente in clientes:
            # Si el cliente tiene casas, aseguramos que tengan el formato esperado
            casas = cliente.get("casas", [])
            cliente["casas"] = [
                {
                    "id": str(casa["_id"]) if isinstance(casa.get("_id"), ObjectId) else casa.get("id", ""),
                    "nombre": casa.get("nombre", "Sin nombre")
                }
                for casa in casas if isinstance(casa, dict)
            ]

            # Eliminamos la contraseña antes de devolver la información
            cliente.pop("contraseña", None)

        # Devolvemos los clientes con la información correcta de casas
        return [Cliente(**cliente) for cliente in clientes]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los usuarios: {str(e)}"
        )
'''
@router.post("/admin/clientes/completo", response_model=Cliente, status_code=status.HTTP_201_CREATED)
async def create_cliente_completo(
    data: dict,  # Recibe un diccionario con toda la información
    current_user: Cliente = Depends(get_current_user)
):
    if current_user.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para realizar esta acción"
        )

    try:
        # Crear el cliente
        cliente_data = data.get("cliente", {})
        if not cliente_data.get("correo"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo del cliente es obligatorio"
            )

        existing_cliente = await collection_cliente.find_one({"correo": cliente_data["correo"]})
        if existing_cliente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un cliente con ese correo"
            )

        contraseña_generada = generar_contraseña_aleatoria()
        contraseña_encriptada = encriptar_contraseña(contraseña_generada)
        cliente_data["contraseña"] = contraseña_encriptada
        cliente_data["casas"] = []
        cliente_result = await collection_cliente.insert_one(cliente_data)
        cliente_id = cliente_result.inserted_id

        # Enviar correo con la contraseña generada
        correo_enviado = await enviar_correo_bienvenida(cliente_data["correo"], contraseña_generada)
        if not correo_enviado:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al enviar el correo de bienvenida"
            )

        # Crear casas y sensores
        casas_data = data.get("casas", [])
        for casa in casas_data:
            sensores = casa.pop("sensores", [])
            casa["usuario_id"] = cliente_id
            casa_result = await collection_casa.insert_one(casa)
            casa_id = casa_result.inserted_id

            # Crear sensores y asociarlos a la casa
            for sensor in sensores:
                tipo_sensor = sensor.get("tipo_sensor")
                if tipo_sensor not in ["gas", "humo", "movimiento", "sonido", "magnetico"]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Tipo de sensor no válido: {tipo_sensor}"
                    )

                # Generar datos del sensor
                sensor_data = {
                    "marca": "Generica",
                    "modelo": f"Modelo-{tipo_sensor.upper()}",
                    "tipo": tipo_sensor
                }

                sensor_collection = {
                    "gas": collection_gas,
                    "humo": collection_humo,
                    "movimiento": collection_movimiento,
                    "sonido": collection_sonido,
                    "magnetico": collection_magnetico,
                }[tipo_sensor]

                sensor_result = await sensor_collection.insert_one(sensor_data)
                sensor_id = sensor_result.inserted_id
                await collection_casa.update_one(
                    {"_id": casa_id},
                    {"$push": {"sensores": {"sensor_obj_id": sensor_id, "sensor_tipo": tipo_sensor}}}
                )

            # Asociar casa al cliente
            casa_info = {"id": str(casa_id), "nombre": casa["nombre"]}
            await collection_cliente.update_one(
                {"_id": cliente_id},
                {"$push": {"casas": casa_info}}
            )

        # Devolver el cliente creado
        created_cliente = await collection_cliente.find_one({"_id": cliente_id})
        if not created_cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        created_cliente["_id"] = str(created_cliente["_id"])
        created_cliente["contraseña"] = None  # No incluir la contraseña en la respuesta

        return Cliente(**created_cliente)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el cliente completo: {str(e)}"
        )
