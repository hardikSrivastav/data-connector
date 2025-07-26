from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database.database import create_tables
from app.api import health, licenses, telemetry, customers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Ceneca License Management Service",
    description="Simplified on-premise licensing with telemetry",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(licenses.router, prefix="/api/licenses", tags=["licenses"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])

@app.get("/")
async def root():
    return {
        "service": "Ceneca License Management Service",
        "version": "2.0.0",
        "status": "running"
    }