# main.py
import traceback

from fastapi import FastAPI, WebSocket, HTTPException
from models import SensorMovimiento, collection_gas, collection_magnetico, collection_movimiento, collection_sonido, collection_humo, SensorGas, SensorMagnetico, SensorSonido, SensorHumo
from bson import ObjectId
from datetime import datetime
from bson.timestamp import Timestamp
import asyncio


app = FastAPI()


# Función auxiliar para serializar ObjectId a string
def serialize_id(document):
    document["_id"] = str(document["_id"])
    return document


# Función genérica para insertar un sensor en una colección
async def insert_sensor(sensor_data, collection):
    result = await collection.insert_one(sensor_data)
    return {**sensor_data, "id": str(result.inserted_id)}


# Rutas para crear sensores
@app.post("/sensor/movimiento/")
async def create_sensor_movimiento(sensor: SensorMovimiento):
    return await insert_sensor(sensor.dict(), collection_movimiento)

@app.post("/sensor/humo/")
async def create_sensor_humo(sensor: SensorHumo):
    return await insert_sensor(sensor.dict(), collection_humo)

@app.post("/sensor/gas/")
async def create_sensor_humo(sensor: SensorGas):
    return await insert_sensor(sensor.dict(), collection_gas)

@app.post("/sensor/sonido/")
async def create_sensor_humo(sensor: SensorSonido):
    return await insert_sensor(sensor.dict(), collection_sonido)

@app.post("/sensor/magnetico/")
async def create_sensor_deteccion(sensor: SensorMagnetico):
    return await insert_sensor(sensor.dict(), collection_magnetico)


# Función genérica para obtener todos los sensores de una colección
async def get_all_sensors(collection):
    sensors = []
    async for sensor in collection.find():
        sensors.append(serialize_id(sensor))
    return sensors


# Rutas para obtener todos los sensores en cada colección
@app.get("/sensores/movimiento/")
async def get_sensores_movimiento():
    return await get_all_sensors(collection_movimiento)


@app.get("/sensores/humo/")
async def get_sensores_humo():
    return await get_all_sensors(collection_humo)


@app.get("/sensores/magnetico/")
async def get_sensores_deteccion():
    return await get_all_sensors(collection_magnetico)

@app.get("/sensores/sonido/")
async def get_sensores_sonido():
    return await get_all_sensors(collection_sonido)

@app.get("/sensores/gas/")
async def get_sensores_gas():
    return await get_all_sensors(collection_gas)

# Ruta genérica para actualizar un sensor en una colección
async def update_sensor(sensor_id: str, sensor_data, collection):
    result = await collection.update_one({"_id": ObjectId(sensor_id)}, {"$set": sensor_data})
    if result.modified_count:
        return {**sensor_data, "id": sensor_id}
    else:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")


# Ejemplo de ruta para actualizar un sensor de movimiento
@app.put("/sensor/movimiento/{sensor_id}")
async def update_sensor_movimiento(sensor_id: str, sensor: SensorMovimiento):
    return await update_sensor(sensor_id, sensor.dict(), collection_movimiento)


# Ejemplo de ruta para eliminar un sensor de movimiento
@app.delete("/sensor/movimiento/{sensor_id}")
async def delete_sensor_movimiento(sensor_id: str):
    result = await collection_movimiento.delete_one({"_id": ObjectId(sensor_id)})
    if result.deleted_count:
        return {"status": "Sensor eliminado"}
    else:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")


# WebSocket para recibir cambios en todas las colecciones en tiempo real
@app.websocket("/ws/sensores")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        collections = [collection_movimiento, collection_sonido, collection_magnetico, collection_gas, collection_sonido]
        # Ejecuta todos los streams de forma concurrente
        await asyncio.gather(*(stream_changes(websocket, col) for col in collections))
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        await websocket.close()

async def stream_changes(websocket: WebSocket, collection):
    async for change in collection.watch():
        serialized_change = serialize_mongo_document(change)
        await websocket.send_json(serialized_change)

async def merge_streams(*streams):
    for stream in streams:
        try:
            async for change in stream:
                # Serializa el documento antes de enviarlo
                change = serialize_mongo_document(change)
                print(f"Evento de cambio recibido: {change}")  # Agrega este print para depuración
                yield change
        except Exception as e:
            print("Error en el merge_streams:")
            print(traceback.format_exc())  # Imprime la traza del error
            continue

def serialize_mongo_document(doc):
    """Convierte los campos de MongoDB en tipos JSON serializables."""
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, datetime):
        return doc.isoformat()  # Convierte el timestamp a una cadena ISO
    if isinstance(doc, Timestamp):
        return str(doc)  # Convierte Timestamp a cadena
    if isinstance(doc, dict):
        return {key: serialize_mongo_document(value) for key, value in doc.items()}
    return doc