import logging
from fastapi import FastAPI
from app.api.endpoints import frames, textgrid, audio, contours, spectrogram

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="UltraTrace Backend")

app.include_router(frames.router)
app.include_router(textgrid.router)
app.include_router(audio.router)
app.include_router(contours.router)
app.include_router(spectrogram.router)


@app.get("/")
async def root():
    return {"message": "UltraTrace API is running"}
