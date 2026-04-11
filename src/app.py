import os
import secrets
import time
import uuid

from quart import Quart, send_from_directory, jsonify
import socketio
from game import GameManager
from pathlib import Path

# ── App setup ────────────────────────────────────────────────────────
app = Quart(
    __name__,
    static_folder=str(Path(__file__).parent.parent / "public"),
    static_url_path=""
)
cors_origins = os.environ.get("CORS_ORIGINS", "*") # Change to domain for AWS deployment.
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
asgi_app = socketio.ASGIApp(sio, app)

# ── Game manager ─────────────────────────────────────────────────────
game_manager = GameManager()

# ── In-memory store for rooms ────────────────────────────────────────
rooms: dict[str, dict] = {}

# Track which room each socket is in: sid -> room_code
player_rooms: dict[str, str] = {}

# Track player info per sid
player_info: dict[str, dict] = {}

# Characters for room codes (no ambiguous chars)
ROOM_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# ── Helpers ──────────────────────────────────────────────────────────

def generate_room_code() -> str:
    code = "".join(secrets.choice(ROOM_CODE_CHARS) for _ in range(5))
    return code if code not in rooms else generate_room_code()


def generate_player_id() -> str:
    return str(uuid.uuid4())


def get_room_state(room: dict) -> dict:
    return {
        "code": room["code"],
        "players": [
            {"id": p["id"], "username": p["username"], "ready": p["ready"]}
            for p in room["players"]
        ],
        "hostId": room["host_id"],
        "gameStarted": room["game_started"],
    }


def normalize_username(username) -> str:
    if not isinstance(username, str):
        return ""
    return username.strip()[:16]


def normalize_room_code(code) -> str:
    if not isinstance(code, str):
        return ""
    return code.upper().strip()[:5]


def normalize_chat_message(message) -> str:
    if not isinstance(message, str):
        return ""
    return message.strip()[:200]


def room_has_username(room: dict, username: str) -> bool:
    return any(
        p["username"].lower() == username.lower() for p in room["players"]
    )


async def broadcast_room_update(room_code: str) -> None:
    room = rooms.get(room_code)
    if not room:
        return
    await sio.emit("room:update", get_room_state(room), room=room_code)


# ── Routes ───────────────────────────────────────────────────────────

@app.route("/")
async def index():
    return await send_from_directory(app.static_folder, "index.html")


@app.route("/health")
async def health():
    return jsonify({"status": "ok"})


# ── Socket.IO event handling ─────────────────────────────────────────

@sio.event
async def connect(sid, environ):
    player_id = generate_player_id()
    player_info[sid] = {"player_id": player_id}
    print(f"[connect] {sid} (player: {player_id})")


@sio.on("room:create")
async def room_create(sid, payload=None):
    payload = payload or {}
    username = payload.get("username", "")

    current_room = player_rooms.get(sid)
    if current_room:
        return {"error": "You are already in a room. Leave first."}

    if sid not in player_info:
        return {"error": "Not connected."}

    normalized_username = normalize_username(username)
    if not normalized_username:
        return {"error": "Username is required."}

    code = generate_room_code()
    player = {
        "id": sid,
        "username": normalized_username,
        "player_id": player_info[sid]["player_id"],
        "ready": False,
    }

    room = {
        "code": code,
        "host_id": sid,
        "players": [player],
        "game_started": False,
    }

    rooms[code] = room
    await sio.enter_room(sid, code)
    player_rooms[sid] = code

    print(f"[room:create] {normalized_username} created room {code}")
    await broadcast_room_update(code)
    return {"success": True, "code": code}


@sio.on("room:join")
async def room_join(sid, payload=None):
    payload = payload or {}
    username = payload.get("username", "")
    code = payload.get("code", "")

    current_room = player_rooms.get(sid)
    if current_room:
        return {"error": "You are already in a room. Leave first."}

    if sid not in player_info:
        return {"error": "Not connected."}

    normalized_username = normalize_username(username)
    if not normalized_username:
        return {"error": "Username is required."}

    room_code = normalize_room_code(code)
    if not room_code:
        return {"error": "Room code is required."}

    room = rooms.get(room_code)

    if not room:
        return {"error": f'Room "{room_code}" not found.'}
    if room["game_started"]:
        return {"error": "Game already in progress."}
    if len(room["players"]) >= 6:
        return {"error": "Room is full (max 6 players)."}
    if room_has_username(room, normalized_username):
        return {"error": "Username already taken in this room."}

    player = {
        "id": sid,
        "username": normalized_username,
        "player_id": player_info[sid]["player_id"],
        "ready": False,
    }
    room["players"].append(player)
    await sio.enter_room(sid, room_code)
    player_rooms[sid] = room_code

    print(f"[room:join] {normalized_username} joined room {room_code}")

    await sio.emit(
        "room:player-joined",
        {"username": normalized_username},
        room=room_code,
        skip_sid=sid,
    )
    await broadcast_room_update(room_code)
    return {"success": True, "code": room_code}


@sio.on("player:ready")
async def player_ready(sid, *args):
    current_room = player_rooms.get(sid)
    if not current_room:
        return
    room = rooms.get(current_room)
    if not room:
        return

    player = next((p for p in room["players"] if p["id"] == sid), None)
    if player:
        player["ready"] = not player["ready"]
        await broadcast_room_update(current_room)


@sio.on("chat:message")
async def chat_message(sid, payload=None):
    payload = payload or {}
    current_room = player_rooms.get(sid)
    if not current_room:
        return
    room = rooms.get(current_room)
    if not room:
        return

    message = payload.get("message", "")
    if not isinstance(message, str):
        return

    normalized_message = normalize_chat_message(message)
    if not normalized_message:
        return

    player = next((p for p in room["players"] if p["id"] == sid), None)
    if not player:
        return

    await sio.emit(
        "chat:message",
        {
            "username": player["username"],
            "message": normalized_message,
            "timestamp": int(time.time() * 1000),
        },
        room=current_room,
    )


@sio.on("room:leave")
async def room_leave(sid, *args):
    await leave_room(sid)


@sio.event
async def disconnect(sid):
    print(f"[disconnect] {sid}")
    await leave_room(sid)
    player_info.pop(sid, None)


async def leave_room(sid: str) -> None:
    current_room = player_rooms.get(sid)
    if not current_room:
        return
    room = rooms.get(current_room)
    if not room:
        return

    leaving_player = next(
        (p for p in room["players"] if p["id"] == sid), None
    )
    room["players"] = [p for p in room["players"] if p["id"] != sid]
    await sio.leave_room(sid, current_room)

    left_room = current_room
    player_rooms.pop(sid, None)

    if len(room["players"]) == 0:
        del rooms[left_room]
        print(f"[room:delete] room {left_room} is now empty")
    else:
        leaving_username = leaving_player["username"] if leaving_player else "A player"
        await sio.emit(
            "room:player-left",
            {"username": leaving_username},
            room=left_room,
        )

        if room["host_id"] == sid:
            room["host_id"] = room["players"][0]["id"]
            await sio.emit(
                "room:new-host",
                {"username": room["players"][0]["username"]},
                room=left_room,
            )
        await broadcast_room_update(left_room)


# ── Game event handlers ──────────────────────────────────────────────

@sio.on("game:start")
async def game_start(sid, *args):
    """Start a new Blackjack game (host only)."""
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}
    
    room = rooms.get(current_room)
    if not room:
        return {"error": "Room not found."}
    
    # Only host can start
    if room["host_id"] != sid:
        return {"error": "Only host can start the game."}
    
    if len(room["players"]) < 1:
        return {"error": "Need at least 1 player."}
    
    # Create game
    players_dict = {p["player_id"]: {"username": p["username"], "id": p["id"]} for p in room["players"]}
    game = game_manager.create_game(current_room, players_dict)
    room["game_started"] = True
    
    await broadcast_room_update(current_room)
    await sio.emit("game:started", {"message": "Game started. Waiting for bets."}, room=current_room)
    return {"success": True}


@sio.on("game:place-bet")
async def game_place_bet(sid, payload=None):
    """Place a bet for the current round."""
    payload = payload or {}
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}
    
    game = game_manager.get_game(current_room)
    if not game:
        return {"error": "No active game."}
    
    amount = payload.get("amount", 0)
    if not isinstance(amount, int) or amount <= 0:
        return {"error": "Invalid bet amount."}
    
    player_id = player_info[sid]["player_id"]
    result = game.place_bet(player_id, amount)
    
    if "error" in result:
        return result
    
    # Broadcast updated game state
    await sio.emit("game:state", game.get_game_state(), room=current_room)
    
    # Check if all players have bet
    if len(game.player_bets) == len(game.players_dict):
        start_result = game.start_round()
        await sio.emit("game:round-started", start_result, room=current_room)
    
    return result


@sio.on("game:hit")
async def game_hit(sid, *args):
    """Player hits (draws a card)."""
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}
    
    game = game_manager.get_game(current_room)
    if not game:
        return {"error": "No active game."}
    
    player_id = player_info[sid]["player_id"]
    result = game.hit(player_id)
    
    if "error" in result:
        return result
    
    await sio.emit("game:state", result, room=current_room)
    return result


@sio.on("game:stand")
async def game_stand(sid, *args):
    """Player stands (stops drawing)."""
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}
    
    game = game_manager.get_game(current_room)
    if not game:
        return {"error": "No active game."}
    
    player_id = player_info[sid]["player_id"]
    result = game.stand(player_id)
    
    if "error" in result:
        return result
    
    await sio.emit("game:state", result, room=current_room)
    return result


@sio.on("game:get-state")
async def game_get_state(sid, *args):
    """Get current game state."""
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}
    
    game = game_manager.get_game(current_room)
    if not game:
        return {"error": "No active game."}
    
    return game.get_game_state()


# ── Start server ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 3000))
    print(f"\n  Blackjack server running on http://localhost:{port}\n")
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)
