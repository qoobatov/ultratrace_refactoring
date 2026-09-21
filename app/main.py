import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# --- API роуты регистрируются как раньше ---
app.include_router(frames.router)
app.include_router(textgrid.router)
app.include_router(audio.router)
app.include_router(contours.router)
app.include_router(spectrogram.router)
app.include_router(study.router)


# --- Раздача собранного фронтенда (добавлено) ---
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend_dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

else:

    @app.get("/")
    async def root():
        return {
            "message": "UltraTrace API is running (frontend_dist not found — "
            "run `npm run build` in the frontend repo and copy dist/ here as frontend_dist/)"
        }
