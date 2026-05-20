import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import frames, textgrid, audio, contours, spectrogram, study

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="UltraTrace Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(frames.router)
app.include_router(textgrid.router)
app.include_router(audio.router)
app.include_router(contours.router)
app.include_router(spectrogram.router)
app.include_router(study.router)


@app.get("/")
async def root():
    return {"message": "UltraTrace API is running"}
