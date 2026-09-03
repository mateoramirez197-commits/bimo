import datetime
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ai_engine import procesar_comando_o_dictado
from generador_pdf import crear_historia_clinica
from database import buscar_pacientes, listar_citas_db

app = FastAPI(title="BIMO API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def status():
    return {"status": "ok"}

@app.get("/api/pacientes")
def get_pacientes():
    return buscar_pacientes("")

@app.get("/api/agenda")
def get_agenda():
    return listar_citas_db()

@app.post("/api/dictado/procesar")
async def procesar_dictado(req: Request):
    data = await req.json()
    texto = data.get("texto", "")
    if not texto:
        raise HTTPException(status_code=400, detail="Vacio")
    
    try:
        resultado = procesar_comando_o_dictado(texto)
        return {"status": "success", "resultado": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pdf/generar")
async def generar_pdf(req: Request):
    data = await req.json()
    datos_clinicos = data.get("datos")
    paciente_id = data.get("paciente_id", 1)
    
    if not datos_clinicos:
        raise HTTPException(status_code=400, detail="Vacio")
        
    try:
        ruta_pdf = crear_historia_clinica(datos_clinicos, paciente_id)
        return {"status": "success", "ruta_pdf": str(ruta_pdf)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
