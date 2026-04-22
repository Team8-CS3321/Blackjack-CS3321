import os
import secrets
import time
import uuid
import asyncio
from .ChatGPTClient import ChatGPTClient

from quart import Quart, send_from_directory, jsonify
import socketio
from .game import GameManager, GamePhase
from pathlib import Path

# ── App setup ────────────────────────────────────────────────────────
app = Quart(
    __name__,
    static_folder=str(Path(__file__).parent / "frontend"),
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

# Track AI helper usage per socket id to prevent request spam.
ai_help_last_request_at: dict[str, float] = {}
ai_help_in_flight: set[str] = set()
AI_HELP_COOLDOWN_SECONDS = 3.0

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
            {
                "id": p["id"],
                "username": p["username"],
                "ready": p["ready"],
                "player_id": p["player_id"],
            }
            for p in room["players"]
        ],
        "hostId": room["host_id"],
        "gameStarted": room["game_started"],
        "singleplayerOrigin": room.get("singleplayer_origin", False),
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


def normalize_ai_query(query) -> str:
    if not isinstance(query, str):
        return ""
    return query.strip()[:300]


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
    return {"success": True, "code": code, "player_id": player["player_id"]}


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

    # If a game exists and is waiting for bets, add the player directly so they
    # can place a bet immediately. In all other active phases, queue them as a
    # spectator to join on next round reset.
    game = game_manager.get_game(room_code)
    is_spectator = False
    if game and game.phase == GamePhase.WAITING_FOR_BETS:
        game.add_player(player["player_id"], normalized_username, sid)
        await sio.emit("game:state", game.get_game_state(), room=room_code)
    elif game:
        is_spectator = True
        room.setdefault("pending_players", []).append(
            {
                "player_id": player["player_id"],
                "username": normalized_username,
                "sid": sid,
            }
        )

    print(f"[room:join] {normalized_username} joined room {room_code}{' (spectator)' if is_spectator else ''}")

    await sio.emit(
        "room:player-joined",
        {"username": normalized_username, "spectator": is_spectator},
        room=room_code,
        skip_sid=sid,
    )
    await broadcast_room_update(room_code)

    # Spectator gets a snapshot of the in-flight game so the table renders for them.
    if is_spectator and game:
        await sio.emit("game:state", game.get_game_state(), to=sid)

    return {"success": True, "code": room_code, "player_id": player["player_id"], "spectator": is_spectator}


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


@sio.on("ai:help")
async def ai_help(sid, payload=None):
    payload = payload or {}
    if not isinstance(payload, dict):
        return {"error": "Invalid payload."}

    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}

    room = rooms.get(current_room)
    if not room:
        return {"error": "Room not found."}

    player = next((p for p in room["players"] if p["id"] == sid), None)
    if not player:
        return {"error": "Player not found."}

    if chat is None:
        return {"error": "AI helper is unavailable. Set CHATGPT env var and restart server."}

    if sid in ai_help_in_flight:
        return {"error": "AI helper is already processing your request."}

    now = time.monotonic()
    last_request_at = ai_help_last_request_at.get(sid)
    if last_request_at is not None and (now - last_request_at) < AI_HELP_COOLDOWN_SECONDS:
        return {"error": "Please wait a few seconds before asking AI again."}

    ai_help_last_request_at[sid] = now
    ai_help_in_flight.add(sid)

    raw_query = payload.get("query", "")
    normalized_query = normalize_ai_query(raw_query)
    if not normalized_query:
        normalized_query = (
            "Give me a quick blackjack help summary: core rules, best basic strategy "
            "for beginners, and one common mistake to avoid."
        )

    prompt = (
        f"Player '{player['username']}' asks: {normalized_query}. "
        "Answer in plain language for in-game help."
    )

    try:
        ai_message = await asyncio.wait_for(
            asyncio.to_thread(chat.ask, prompt),
            timeout=14,
        )
    except asyncio.TimeoutError:
        return {"error": "AI helper timed out. Please try a shorter question."}
    except Exception as e:
        print(f"[ai:help] error: {e}")
        return {"error": "AI helper failed. Try again in a moment."}
    finally:
        ai_help_in_flight.discard(sid)

    if not isinstance(ai_message, str) or not ai_message.strip():
        return {"error": "AI helper returned an empty response."}

    return {"success": True, "message": ai_message.strip()}


@sio.on("room:leave")
async def room_leave(sid, *args):
    await leave_room(sid)


@sio.event
async def disconnect(sid):
    print(f"[disconnect] {sid}")
    await leave_room(sid)
    player_info.pop(sid, None)
    ai_help_last_request_at.pop(sid, None)
    ai_help_in_flight.discard(sid)


async def leave_room(sid: str) -> None:
    ai_help_last_request_at.pop(sid, None)
    ai_help_in_flight.discard(sid)

    current_room = player_rooms.get(sid)
    if not current_room:
        return
    room = rooms.get(current_room)
    if not room:
        return
    game = game_manager.get_game(current_room)

    leaving_player = next(
        (p for p in room["players"] if p["id"] == sid), None
    )

    removed_from_game = False
    advanced_after_disconnect = False
    if game and leaving_player:
        leaving_player_id = leaving_player["player_id"]
        removable_phases = (GamePhase.WAITING_FOR_BETS, GamePhase.ROUND_COMPLETE)
        if game.phase in removable_phases:
            game.remove_player(leaving_player_id)
            removed_from_game = True
        else:
            pending_removals = room.setdefault("pending_removals", [])
            if not any(p.get("player_id") == leaving_player_id for p in pending_removals):
                pending_removals.append(
                    {
                        "player_id": leaving_player_id,
                        "username": leaving_player["username"],
                    }
                )

            # During active dealing/playing phases, mark disconnected players as
            # standing so turn order can continue without manual intervention.
            if game.phase in (GamePhase.DEALING, GamePhase.PLAYING):
                leaving_player_obj = game.player_objects.get(leaving_player_id)
                if leaving_player_obj and not leaving_player_obj.is_stand:
                    leaving_player_obj.stand()
                    if game.phase == GamePhase.PLAYING:
                        player_ids = list(game.player_objects.keys())
                        if (
                            game.current_player_index < len(player_ids)
                            and player_ids[game.current_player_index] == leaving_player_id
                        ):
                            result = game.advance_to_next_player()
                            await sio.emit("game:state", result, room=current_room)
                            advanced_after_disconnect = True

    room["players"] = [p for p in room["players"] if p["id"] != sid]
    if "pending_players" in room:
        room["pending_players"] = [
            pp for pp in room["pending_players"] if pp.get("sid") != sid
        ]
    await sio.leave_room(sid, current_room)

    left_room = current_room
    player_rooms.pop(sid, None)

    if len(room["players"]) == 0:
        game_manager.end_game(left_room)
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
        if removed_from_game and game:
            if (
                game.phase == GamePhase.WAITING_FOR_BETS
                and len(game.players_dict) > 0
                and len(game.player_bets) == len(game.players_dict)
            ):
                start_result = game.start_round()
                await sio.emit("game:round-started", start_result, room=left_room)
            else:
                await sio.emit("game:state", game.get_game_state(), room=left_room)
        elif game and not advanced_after_disconnect and game.phase in (GamePhase.DEALING, GamePhase.PLAYING):
            await sio.emit("game:state", game.get_game_state(), room=left_room)
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
    if not all(p["ready"] for p in room["players"]):
        return {"error": "All players must be ready."}
    
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


@sio.on("game:next-round")
async def game_next_round(sid, *args):
    """Reset the game for the next round. Host-only in multiplayer; sole player in singleplayer."""
    current_room = player_rooms.get(sid)
    if not current_room:
        return {"error": "Not in a room."}

    room = rooms.get(current_room)
    if not room:
        return {"error": "Room not found."}

    game = game_manager.get_game(current_room)
    if not game:
        return {"error": "No active game."}

    if game.phase != GamePhase.ROUND_COMPLETE:
        return {"error": "Round not complete yet."}

    if len(room["players"]) == 1:
        if sid != room["players"][0]["id"]:
            return {"error": "Not authorized."}
    else:
        if sid != room["host_id"]:
            return {"error": "Only host can start next round."}

    pending_removals = room.pop("pending_removals", [])
    for pending_removal in pending_removals:
        player_id = pending_removal.get("player_id")
        if player_id:
            game.remove_player(player_id)

    pending = room.pop("pending_players", [])
    game.reset_for_next_round(pending)
    await sio.emit("game:state", game.get_game_state(), room=current_room)
    await broadcast_room_update(current_room)
    return {"success": True}


@sio.on("singleplayer:start")
async def singleplayer_start(sid, payload=None):
    """Create a private 1-player room and start the game atomically."""
    payload = payload or {}

    if sid in player_rooms:
        return {"error": "You are already in a room. Leave first."}

    if sid not in player_info:
        return {"error": "Not connected."}

    normalized_username = normalize_username(payload.get("username", ""))
    if not normalized_username:
        return {"error": "Username is required."}

    code = generate_room_code()
    player_id = player_info[sid]["player_id"]
    player = {
        "id": sid,
        "username": normalized_username,
        "player_id": player_id,
        "ready": True,
    }

    # Singleplayer rooms are structurally identical to multiplayer rooms.
    # The only difference is singleplayer_origin=True, which is a UI hint so
    # the frontend hides the room code until the host explicitly shares it.
    # A friend can still join via room:join with the code.
    room = {
        "code": code,
        "host_id": sid,
        "players": [player],
        "game_started": True,
        "singleplayer_origin": True,
    }
    rooms[code] = room
    await sio.enter_room(sid, code)
    player_rooms[sid] = code

    players_dict = {player_id: {"username": normalized_username, "id": sid}}
    game = game_manager.create_game(code, players_dict)

    print(f"[singleplayer:start] {normalized_username} started solo room {code}")

    await broadcast_room_update(code)
    await sio.emit(
        "singleplayer:ready",
        {
            "code": code,
            "player_id": player_id,
            "room": get_room_state(room),
            "state": game.get_game_state(),
        },
        to=sid,
    )
    return {"success": True, "code": code, "player_id": player_id}


# ── Start server ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 3000)) # Port 3000 is default.
    print(f"\n  Blackjack server running on http://{host}:{port}\n")
    uvicorn.run(asgi_app, host=host, port=port)

    # ── ChatGPT Client ────────────────────────────────────────────────────
    try:
        chat = ChatGPTClient()
    except Exception as e:
        print(f"[warn] ChatGPTClient init failed: {e}")
        chat = None
