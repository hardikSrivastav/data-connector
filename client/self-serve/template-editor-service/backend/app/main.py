from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from app.database.database import create_tables
from app.api import sessions, templates, health, tools, scenarios

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Template Editor Service",
    description="AI-powered template editing service with workspace isolation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8500").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    print(f"WebSocket connection accepted for session: {session_id}")
    
    try:
        # Send initial connection message
        await websocket.send_text("Connected to AI assistant")
        
        # Try to initialize AI agent
        ai_agent = None
        try:
            from app.services.ai_agent import AIAgent
            ai_agent = AIAgent(session_id)
            await websocket.send_text("AI assistant initialized successfully. How can I help you customize your authentication template?")
        except Exception as e:
            print(f"Failed to initialize AI agent: {e}")
            await websocket.send_text("AI assistant is in demo mode. You can still interact with the template editor.")
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            print(f"Received message: {data}")
            
            if ai_agent is not None:
                try:
                    # Process with AI agent
                    response = await ai_agent.process_message(data)
                    await websocket.send_text(response)
                except Exception as e:
                    print(f"AI agent error: {e}")
                    await websocket.send_text(f"AI assistant encountered an error: {str(e)}")
            else:
                # Fallback response when AI agent is not available
                response = f"Demo mode: I received your message '{data}'. In full mode, I would help you customize your authentication template."
                await websocket.send_text(response)
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except:
            pass
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)