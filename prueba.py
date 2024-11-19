from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

class MongoDBConnection:
    def __init__(self, uri, database_name):
        self.uri = uri
        self.database_name = database_name
        try:
            self.client = MongoClient(self.uri, server_api=ServerApi('1'))
            self.db = self.client[self.database_name]
            print("Conexión exitosa a MongoDB Atlas")
        except Exception as e:
            print(f"No se pudo conectar a MongoDB Atlas: {e}")
            self.db = None

    def insert_documents(self, collection_name, documents):
        """Inserta múltiples documentos en la colección especificada."""
        if self.db is not None and documents:
            collection = self.db[collection_name]
            result = collection.insert_many(documents)
            print(f"Documentos insertados en '{collection_name}' con ids: {result.inserted_ids}")
        else:
            print("No se puede insertar, no hay conexión a la base de datos.")

    def find_documents(self, collection_name, query={}):
        """Consulta documentos en una colección especificada."""
        if self.db is not None:  # Cambiado para comparar con None
            collection = self.db[collection_name]
            return list(collection.find(query))
        else:
            print("No se puede consultar, no hay conexión a la base de datos.")
            return []

    def update_document(self, collection_name, query, new_values):
        """Actualiza un documento basado en una consulta."""
        if self.db is not None:  # Cambiado para comparar con None
            collection = self.db[collection_name]
            result = collection.update_one(query, {'$set': new_values})
            if result.modified_count > 0:
                print("Documento actualizado correctamente.")
            else:
                print("No se encontró el documento o no hubo cambios.")
        else:
            print("No se puede actualizar, no hay conexión a la base de datos.")


    def delete_document(self, collection_name, query):
        """Elimina un documento basado en una consulta."""
        if self.db is not None:
            collection = self.db[collection_name]
            result = collection.delete_one(query)
            if result.deleted_count > 0:
                print("Documento eliminado correctamente.")
            else:
                print("No se encontró el documento.")
        else:
            print("No se puede eliminar, no hay conexión a la base de datos.")

    


# Ejemplo de uso de MongoDBConnection
if __name__ == "__main__":
    uri = "mongodb+srv://seguridadhogar:Integradora-Proyecto-1@cluster0.nmcaz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    database_name = "UTT"
    
    mongo_conn = MongoDBConnection(uri, database_name)
    
    # Insertar ejemplo de alumno
    alumno = {"nombre": "Juan", "edad": 30, "carrera": "Ingeniería"}
    # Si alumno es un solo documento
    mongo_conn.insert_documents("Alumnos", [alumno])  # Pásalo como una lista

    
    # Consultar alumnos
    #alumnos = mongo_conn.find_documents("Alumnos")
    #for alumno in alumnos:
     #   print(alumno)
    
    # Actualizar un alumno
    #mongo_conn.update_document("Alumnos", {"nombre": "Juan"}, {"edad": 31})

    # Eliminar un alumno
    #mongo_conn.delete_document("Alumnos", {"nombre": "Juan"})
