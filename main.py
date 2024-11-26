# main.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from Routes import admin, Sensores, cliente

app = FastAPI()
app.include_router(Sensores.router)
app.include_router(admin.router)
app.include_router(cliente.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Servidor funcionando"}




