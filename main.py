from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

from task import Task

load_dotenv()

app = FastAPI()

# Store active connections
connections = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.add(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            if data["type"] == "start_task":
                # Create and run task
                task = Task(
                    user_message=data["message"],
                    websocket=websocket,
                    config={
                        "cwd": os.getenv("WORKING_DIRECTORY", os.getcwd())
                    }
                )
                
                # Run task in background
                asyncio.create_task(task.start())
            
            elif data["type"] == "approve_tool":
                # Handle tool approval
                # (For MVP, auto-approve all tools)
                pass
    
    except WebSocketDisconnect:
        connections.remove(websocket)

@app.get("/")
async def get():
    # Get path relative to backend directory
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    return HTMLResponse(frontend_path.read_text())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
