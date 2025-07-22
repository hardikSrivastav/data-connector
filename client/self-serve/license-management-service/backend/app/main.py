from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

from app.api import health, licenses, validation, customers
from app.database.database import engine, Base

load_dotenv()

app = FastAPI(
    title="License Management Service",
    description="Enterprise License Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(licenses.router, prefix="/api/licenses", tags=["licenses"])
app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)