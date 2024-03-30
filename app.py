from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict
import json

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def total_connections(self):
        return len(self.active_connections)


class Game(BaseModel):
    word: str
    theme: str
    letters: List[str] = []
    errors: int = 0


games: Dict[str, Game] = {}

manager = ConnectionManager()


@app.get("/")
async def get():
    return {"message": "Hello World"}


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    if game_id in games and manager.total_connections() == 2:
        await websocket.send_text("Game is full")
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            command, value = data.split(" ", 1)
            if command == "start_game":
                word, theme = value.split(" ", 1)
                if game_id in games:
                    await websocket.send_text("Game with this ID already exists")
                else:
                    games[game_id] = Game(
                        word=word, theme=theme, letters=[], errors=0)
                    game_json = json.dumps(games[game_id].__dict__)
                    await manager.send_personal_message(game_json, websocket)
            elif command == "get_game":
                if game_id not in games:
                    await websocket.send_text("Game not found")
                else:
                    game_json = json.dumps(games[game_id].__dict__)
                    await manager.send_personal_message(game_json, websocket)
            elif command == "send_letter":
                if game_id not in games:
                    await websocket.send_text("Game not found")
                else:
                    letter = value
                    games[game_id].letters.append(letter)
                    game_json = json.dumps(games[game_id].__dict__)
                    await manager.broadcast(game_json)
            elif command == "send_errors":
                if game_id not in games:
                    await websocket.send_text("Game not found")
                else:
                    errors = int(value)
                    games[game_id].errors = errors
                    game_json = json.dumps(games[game_id].__dict__)
                    await manager.broadcast(game_json)
            elif command == "new_word_and_theme":
                word, theme = value.split(" ", 1)
                if game_id not in games:
                    await websocket.send_text("Game not found")
                else:
                    games[game_id].word = word
                    games[game_id].theme = theme
                    games[game_id].letters = []
                    games[game_id].errors = 0
                    game_json = json.dumps(games[game_id].__dict__)
                    await manager.broadcast(game_json)

            else:
                await websocket.send_text("Invalid command")
    except WebSocketDisconnect:
        manager.active_connections.remove(websocket)
        if game_id in games:
            del games[game_id]
        await manager.broadcast(f"Second player left the game")
