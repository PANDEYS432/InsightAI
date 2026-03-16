"""
accident_api/main.py
Run with:  uvicorn accident_api.main:app --reload --port 8001
API docs:  http://localhost:8001/docs
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from accident_api.data_loader import loader
from accident_api.routers import (
    road_features, junctions, traffic_control,
    traffic_violations, weather, vehicles, road_defects,
)

app = FastAPI(
    title="India Road Accident Data API",
    description=(
        "Structured REST API over Million Plus Cities accident datasets "
        "(2019-2021). Consumed by the Accident Data Agent."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    loader.load_all()
    print("[API] All datasets loaded and ready.")


# ── Meta routes ───────────────────────────────────────────────────────────────

@app.get("/", tags=["Meta"])
def root():
    return {
        "status": "ok",
        "loaded_datasets": len(loader.available_datasets()),
        "docs": "/docs",
    }


@app.get("/datasets", tags=["Meta"])
def list_datasets():
    """List every loaded dataset with row count and column names."""
    return loader.available_datasets()


@app.get("/cities", tags=["Meta"])
def list_cities(
    dataset: Optional[str] = Query(
        None, description="Filter cities to a specific dataset key")
):
    """List all city names across datasets (or within one dataset)."""
    return {"cities": loader.get_cities(dataset)}


@app.get("/years", tags=["Meta"])
def list_years():
    """List all years available across loaded datasets."""
    return {"years": loader.get_years()}


# ── Domain routers ────────────────────────────────────────────────────────────

app.include_router(road_features.router,
                   prefix="/road-features", tags=["Road Features"])
app.include_router(junctions.router,
                   prefix="/junctions", tags=["Junctions"])
app.include_router(traffic_control.router,
                   prefix="/traffic-control", tags=["Traffic Control"])
app.include_router(traffic_violations.router,
                   prefix="/traffic-violations", tags=["Traffic Violations"])
app.include_router(weather.router,
                   prefix="/weather", tags=["Weather"])
app.include_router(vehicles.router,
                   prefix="/vehicles", tags=["Vehicles"])
app.include_router(road_defects.router,
                   prefix="/road-defects", tags=["Road Defects"])
