import traceback
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
        # Buscar clientes con rol "cliente"
        cursor = collection_cliente.find({"rol": "cliente"})
        clientes_raw = await cursor.to_list(length=None)

        clientes_procesados = []
        for cliente_data in clientes_raw:
            # Convertir ObjectId a string para serialización
            if '_id' in cliente_data:
                cliente_data['id'] = str(cliente_data['_id'])
                del cliente_data['_id']

            # Eliminar la contraseña si existe
            cliente_data.pop('contraseña', None)

            # Procesar las casas
            casas_procesadas = []
            for casa in cliente_data.get('casas', []):
                # Verificar si 'casa' es un diccionario y contiene un 'id'
                if isinstance(casa, dict) and '_id' in casa:
                    # Convertir _id de casa a ObjectId si es un string
                    if isinstance(casa['_id'], str):
                        try:
                            casa['_id'] = ObjectId(casa['_id'])
                        except Exception as e:
                            print(f"Error al convertir el _id de casa {casa['_id']} a ObjectId: {e}")
                            continue

                    casa_id = str(casa['_id'])  # Convertir ObjectId a string para la serialización
                    casa_nombre = casa.get('nombre')

                    # Buscar información adicional de la casa usando su ObjectId
                    try:
                        casa_info = await collection_casa.find_one({"_id": casa['_id']})
                        if casa_info:
                            # Convertir cualquier ObjectId dentro de casa_info a string
                            casa_info = {k: str(v) if isinstance(v, ObjectId) else v for k, v in casa_info.items()}
                            casa_info['nombre'] = casa_nombre  # Mantener el nombre de la casa

                            # Eliminar los sensores (si no los quieres mostrar)
                            if 'sensores' in casa_info:
                                del casa_info['sensores']

                            casas_procesadas.append(casa_info)
                    except Exception as e:
                        print(f"Error procesando casa con ID {casa_id}: {e}")

            # Actualizar el campo de casas con las casas procesadas
            cliente_data['casas'] = casas_procesadas

            # Convertir el cliente a modelo Cliente
            try:
                cliente = Cliente(**cliente_data)
                clientes_procesados.append(cliente)
            except Exception as e:
                print(f"Error procesando cliente: {e}")
                print(f"Datos del cliente problemático: {cliente_data}")

        return clientes_procesados

    except Exception as e:
        print(traceback.format_exc())  # Imprimir traza completa del error
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
            "sensores": casa.sensores
        }
        resultado = await collection_casa.insert_one(nueva_casa)
        nueva_casa["_id"] = resultado.inserted_id  # Agregar el ID generado a la casa

        # Actualizar el cliente para agregar el ID y el nombre de la nueva casa
        await collection_cliente.update_one(
            {"_id": ObjectId(cliente_id)},
            {
                "$push": {
                    "casas": {
                        "id": nueva_casa["_id"],
                        "nombre": nueva_casa["nombre"]
                    }
                }
            }
        )

        # Devolver la casa creada como respuesta
        return Casa(**nueva_casa)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al agregar la casa: {str(e)}"
        )
     
#Endpoint para ver las casas de cada usuario
@router.get("/admin/clientes/{cliente_id}/casas-sensores", response_model=List[Casa])
async def obtener_casas_cliente(
    cliente_id: str,
    current_user: Cliente = Depends(get_current_user)
):
    # Verificar permisos
    if current_user.rol != "admin" and str(current_user.id) != cliente_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver estas casas"
        )

    try:
        # Buscar cliente
        cliente = await collection_cliente.find_one({"_id": ObjectId(cliente_id)})
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )

        # Obtener IDs de casas desde el array de objetos
        casas_ids = [ObjectId(casa["id"]) for casa in cliente.get("casas", [])]
        if not casas_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Este cliente no tiene casas asociadas"
            )

        # Buscar las casas por los IDs extraídos
        casas = await collection_casa.find(
            {"_id": {"$in": casas_ids}}
        ).to_list(length=100)

        if not casas:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron casas para este cliente"
            )

        return casas

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las casas: {str(e)}"
        )

@router.get("/admin/clientes/{cliente_id}/casas", response_model=List[Casa])
async def obtener_casas_cliente_sin_sensores(
    cliente_id: str,
    current_user: Cliente = Depends(get_current_user)
):
    # Verificar permisos
    if current_user.rol != "admin" and str(current_user.id) != cliente_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver estas casas"
        )

    try:
        # Buscar cliente
        cliente = await collection_cliente.find_one({"_id": ObjectId(cliente_id)})
        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado"
            )

        # Obtener IDs de casas desde el array de objetos
        casas_ids = [ObjectId(casa["id"]) for casa in cliente.get("casas", [])]
        if not casas_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Este cliente no tiene casas asociadas"
            )

        # Buscar las casas
        casas = await collection_casa.find(
            {"_id": {"$in": casas_ids}}
        ).to_list(length=100)

        if not casas:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron casas para este cliente"
            )

        # Ocultar el campo 'sensores' en la respuesta
        casas_sin_sensores = [
            {key: value for key, value in casa.items() if key != "sensores"}
            for casa in casas
        ]

        return casas_sin_sensores

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las casas: {str(e)}"
        )


@router.get("/admin/clientes/{cliente_id}/casas/{casa_id}/sensores") 
async def obtener_sensores_de_casa(
    cliente_id: str,
    casa_id: str,
    token: str = Depends(oauth2_scheme)
):
    try:
        # Validar el token y obtener usuario actual
        current_user = await get_current_user(token)
        
        # Validar permisos: Admin o el mismo usuario
        if str(current_user.id) != cliente_id and current_user.rol != "admin":
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para ver los sensores de esta casa"
            )
        
        # Verificar que el usuario tiene la casa asociada
        usuario = await collection_cliente.find_one({"_id": ObjectId(cliente_id)})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        # Validar que la casa está asociada al usuario
        if not any(str(casa.get('id', '')) == casa_id for casa in usuario.get("casas", [])):
            raise HTTPException(status_code=404, detail="La casa no pertenece al usuario")
        
        # Obtener la casa desde su colección
        casa = await collection_casa.find_one({"_id": ObjectId(casa_id)})
        if not casa:
            raise HTTPException(status_code=404, detail="Casa no encontrada")
        
        # Obtener los IDs de sensores de la casa
        sensores_ids = [str(sensor['sensor_obj_id']) if isinstance(sensor, dict) else str(sensor) for sensor in casa.get("sensores", [])]
        
        if not sensores_ids:
            return {"message": "No hay sensores asociados a esta casa", "data": []}
        
        # Lista para almacenar todos los sensores
        sensores_totales = []
        
        # Lista de colecciones de sensores (ajusta según tus colecciones específicas)
        colecciones_sensores = [
            collection_gas,
            collection_humo,
            collection_movimiento,
            collection_sonido,
            collection_magnetico
            # Agrega aquí todas las colecciones de sensores que tengas
        ]
        
        # Buscar cada sensor por su ID en todas las colecciones
        for sensor_id in sensores_ids:
            sensor_encontrado = False
            for collection in colecciones_sensores:
                sensor = await collection.find_one({"_id": ObjectId(sensor_id)})
                if sensor:
                    sensores_totales.append({
                        "_id": str(sensor["_id"]),
                        "tipo": sensor.get("tipo", "desconocido"),
                        # Otros campos específicos según el tipo de sensor
                    })
                    sensor_encontrado = True
                    break  # Salir del bucle de colecciones una vez encontrado
            
            # Opcional: manejar sensores no encontrados
            if not sensor_encontrado:
                print(f"Sensor con ID {sensor_id} no encontrado en ninguna colección")
        
        return {"message": "Sensores obtenidos con éxito", "data": sensores_totales}
    
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

