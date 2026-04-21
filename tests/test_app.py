import re
import asyncio
from app import (
    ROOM_CODE_CHARS,
    generate_player_id,
    generate_room_code,
    get_room_state,
    normalize_username,
    normalize_room_code,
    normalize_chat_message,
    normalize_ai_query,
    room_has_username,
    rooms,
    ai_help,
    game_start,
    game_place_bet,
    game_hit,
    game_stand,
    game_get_state,
    game_next_round,
    singleplayer_start,
    player_rooms,
    player_info,
    rooms,
    ai_help_last_request_at,
    ai_help_in_flight,
    GamePhase,
)

from types import SimpleNamespace
from unittest.mock import AsyncMock
import app as app_module

def setup_function():
    rooms.clear()


def test_normalize_username_trims_and_limits_length():
    assert normalize_username("   Luis   ") == "Luis"
    assert normalize_username("abcdefghijklmnopqr") == "abcdefghijklmnop"
    assert normalize_username(123) == ""


def test_normalize_room_code_uppercases_trims_and_limits_length():
    assert normalize_room_code(" ab12c ") == "AB12C"
    assert normalize_room_code("abcdefg") == "ABCDE"
    assert normalize_room_code(None) == ""


def test_normalize_chat_message_trims_and_limits_length():
    assert normalize_chat_message("  hello  ") == "hello"
    assert normalize_chat_message("a" * 250) == "a" * 200
    assert normalize_chat_message([]) == ""


def test_normalize_ai_query_trims_and_limits_length():
    assert normalize_ai_query("  what is blackjack?  ") == "what is blackjack?"
    assert normalize_ai_query("a" * 400) == "a" * 300
    assert normalize_ai_query({}) == ""


def test_room_has_username_is_case_insensitive():
    room = {
        "players": [
            {"username": "Luis"},
            {"username": "Alice"},
        ]
    }
    assert room_has_username(room, "luis") is True
    assert room_has_username(room, "ALICE") is True
    assert room_has_username(room, "Bob") is False


def test_get_room_state_returns_expected_shape():
    room = {
        "code": "ABCDE",
        "host_id": "sid1",
        "game_started": True,
        "singleplayer_origin": True,
        "players": [
            {
                "id": "sid1",
                "username": "Luis",
                "ready": True,
                "player_id": "p1",
            }
        ],
    }

    state = get_room_state(room)

    assert state["code"] == "ABCDE"
    assert state["hostId"] == "sid1"
    assert state["gameStarted"] is True
    assert state["singleplayerOrigin"] is True
    assert state["players"][0]["username"] == "Luis"
    assert state["players"][0]["player_id"] == "p1"


def test_get_room_state_defaults_singleplayer_origin_to_false():
    room = {
        "code": "ABCDE",
        "host_id": "sid1",
        "game_started": False,
        "players": [],
    }

    state = get_room_state(room)

    assert state["singleplayerOrigin"] is False


def test_generate_player_id_returns_uuid_like_string():
    player_id = generate_player_id()
    assert isinstance(player_id, str)
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        player_id,
    )


def test_generate_room_code_returns_five_valid_characters():
    code = generate_room_code()
    assert len(code) == 5
    assert all(ch in ROOM_CODE_CHARS for ch in code)


def test_generate_room_code_avoids_existing_room_codes(monkeypatch):
    rooms["ABCDE"] = {"code": "ABCDE"}

    picks = iter(list("ABCDE") + list("FGHIJ"))

    def fake_choice(_chars):
        return next(picks)

    monkeypatch.setattr("app.secrets.choice", fake_choice)

    code = generate_room_code()

    assert code == "FGHIJ"
def teardown_function():
    rooms.clear()
    player_rooms.clear()
    player_info.clear()
    ai_help_last_request_at.clear()
    ai_help_in_flight.clear()


def test_ai_help_rejects_invalid_payload():
    result = asyncio.run(ai_help("sid1", "bad payload"))
    assert result["error"] == "Invalid payload."


def test_ai_help_requires_room_membership():
    result = asyncio.run(ai_help("sid1", {}))
    assert result["error"] == "Not in a room."


def test_ai_help_requires_existing_room():
    player_rooms["sid1"] = "ABCDE"
    result = asyncio.run(ai_help("sid1", {}))
    assert result["error"] == "Room not found."


def test_ai_help_requires_existing_player_in_room():
    player_rooms["sid1"] = "ABCDE"
    rooms["ABCDE"] = {"players": []}
    result = asyncio.run(ai_help("sid1", {}))
    assert result["error"] == "Player not found."


def test_ai_help_returns_error_when_chat_unavailable(monkeypatch):
    player_rooms["sid1"] = "ABCDE"
    rooms["ABCDE"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }

    monkeypatch.setattr("app.chat", None)

    result = asyncio.run(ai_help("sid1", {}))
    assert "AI helper is unavailable" in result["error"]


def test_game_start_requires_room_membership():
    result = asyncio.run(game_start("sid1"))
    assert result["error"] == "Not in a room."


def test_game_start_requires_host():
    player_rooms["sid2"] = "ABCDE"
    rooms["ABCDE"] = {
        "host_id": "sid1",
        "players": [{"id": "sid1", "username": "Luis", "ready": True, "player_id": "p1"}],
        "game_started": False,
    }

    result = asyncio.run(game_start("sid2"))
    assert result["error"] == "Only host can start the game."


def test_game_start_requires_all_players_ready():
    player_rooms["sid1"] = "ABCDE"
    rooms["ABCDE"] = {
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "ready": True, "player_id": "p1"},
            {"id": "sid2", "username": "Bob", "ready": False, "player_id": "p2"},
        ],
        "game_started": False,
    }

    result = asyncio.run(game_start("sid1"))
    assert result["error"] == "All players must be ready."


def test_game_place_bet_requires_room_membership():
    result = asyncio.run(game_place_bet("sid1", {"amount": 50}))
    assert result["error"] == "Not in a room."


def test_game_hit_requires_room_membership():
    result = asyncio.run(game_hit("sid1"))
    assert result["error"] == "Not in a room."


def test_game_stand_requires_room_membership():
    result = asyncio.run(game_stand("sid1"))
    assert result["error"] == "Not in a room."


def test_game_get_state_requires_room_membership():
    result = asyncio.run(game_get_state("sid1"))
    assert result["error"] == "Not in a room."


def test_game_next_round_requires_room_membership():
    result = asyncio.run(game_next_round("sid1"))
    assert result["error"] == "Not in a room."


def test_singleplayer_start_requires_connection():
    result = asyncio.run(singleplayer_start("sid1", {"username": "Luis"}))
    assert result["error"] == "Not connected."


def test_singleplayer_start_requires_username():
    player_info["sid1"] = {"player_id": "p1"}

    result = asyncio.run(singleplayer_start("sid1", {"username": "   "}))
    assert result["error"] == "Username is required."

def test_room_create_success(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_info["sid1"] = {"player_id": "p1"}

    monkeypatch.setattr("app.generate_room_code", lambda: "ABCDE")
    monkeypatch.setattr("app.sio.enter_room", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())

    result = asyncio.run(app_module.room_create("sid1", {"username": " Luis "}))

    assert result == {"success": True, "code": "ABCDE", "player_id": "p1"}
    assert "ABCDE" in app_module.rooms
    assert app_module.player_rooms["sid1"] == "ABCDE"
    assert app_module.rooms["ABCDE"]["players"][0]["username"] == "Luis"


def test_room_join_success_without_active_game(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_info["sid2"] = {"player_id": "p2"}
    app_module.rooms["ABCDE"] = {
        "code": "ABCDE",
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False}
        ],
        "game_started": False,
    }

    monkeypatch.setattr("app.sio.enter_room", AsyncMock())
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())
    monkeypatch.setattr("app.game_manager.get_game", lambda code: None)

    result = asyncio.run(app_module.room_join("sid2", {"username": "Bob", "code": "abcde"}))

    assert result["success"] is True
    assert result["code"] == "ABCDE"
    assert result["player_id"] == "p2"
    assert result["spectator"] is False
    assert app_module.player_rooms["sid2"] == "ABCDE"
    assert len(app_module.rooms["ABCDE"]["players"]) == 2


def test_singleplayer_start_success(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_info["sid1"] = {"player_id": "p1"}

    fake_game = SimpleNamespace(get_game_state=lambda: {"phase": "waiting_for_bets"})

    monkeypatch.setattr("app.generate_room_code", lambda: "SOLO1")
    monkeypatch.setattr("app.sio.enter_room", AsyncMock())
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())
    monkeypatch.setattr("app.game_manager.create_game", lambda code, players: fake_game)

    result = asyncio.run(app_module.singleplayer_start("sid1", {"username": "Luis"}))

    assert result == {"success": True, "code": "SOLO1", "player_id": "p1"}
    assert app_module.player_rooms["sid1"] == "SOLO1"
    assert app_module.rooms["SOLO1"]["singleplayer_origin"] is True
    assert app_module.rooms["SOLO1"]["game_started"] is True


def test_game_start_success(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ABCDE"
    app_module.rooms["ABCDE"] = {
        "code": "ABCDE",
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "player_id": "p1", "ready": True}
        ],
        "game_started": False,
    }

    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.game_manager.create_game", lambda room, players: object())

    result = asyncio.run(app_module.game_start("sid1"))

    assert result == {"success": True}
    assert app_module.rooms["ABCDE"]["game_started"] is True


def test_game_place_bet_success_and_round_not_started(monkeypatch):
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_rooms["sid1"] = "ABCDE"
    app_module.player_info["sid1"] = {"player_id": "p1"}

    fake_game = SimpleNamespace(
        place_bet=lambda player_id, amount: {"success": True, "message": "Bet placed"},
        get_game_state=lambda: {"phase": "waiting_for_bets"},
        player_bets={"p1": 50},
        players_dict={"p1": {"username": "Luis", "id": "sid1"}, "p2": {"username": "Bob", "id": "sid2"}},
    )

    monkeypatch.setattr("app.game_manager.get_game", lambda room: fake_game)
    monkeypatch.setattr("app.sio.emit", AsyncMock())

    result = asyncio.run(app_module.game_place_bet("sid1", {"amount": 50}))

    assert result["success"] is True
    app_module.sio.emit.assert_awaited()


def test_game_get_state_success(monkeypatch):
    app_module.player_rooms.clear()
    app_module.player_rooms["sid1"] = "ABCDE"

    fake_state = {"phase": "playing"}
    fake_game = SimpleNamespace(get_game_state=lambda: fake_state)

    monkeypatch.setattr("app.game_manager.get_game", lambda room: fake_game)

    result = asyncio.run(app_module.game_get_state("sid1"))

    assert result == fake_state


def test_game_next_round_success(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ABCDE"
    app_module.rooms["ABCDE"] = {
        "code": "ABCDE",
        "host_id": "sid1",
        "players": [{"id": "sid1", "username": "Luis", "player_id": "p1", "ready": True}],
        "game_started": True,
        "pending_removals": [{"player_id": "p2", "username": "Bob"}],
        "pending_players": [{"player_id": "p3", "username": "Ana", "sid": "sid3"}],
    }

    fake_game = SimpleNamespace(
        phase=app_module.GamePhase.ROUND_COMPLETE,
        remove_player=AsyncMock(),
        reset_for_next_round=AsyncMock(),
        get_game_state=lambda: {"phase": "waiting_for_bets"},
    )

    def fake_remove_player(player_id):
        return None

    def fake_reset_for_next_round(pending):
        return None

    fake_game.remove_player = fake_remove_player
    fake_game.reset_for_next_round = fake_reset_for_next_round

    monkeypatch.setattr("app.game_manager.get_game", lambda room: fake_game)
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())

    result = asyncio.run(app_module.game_next_round("sid1"))

    assert result == {"success": True}
    app_module.sio.emit.assert_awaited()


def test_leave_room_deletes_empty_room(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.ai_help_last_request_at.clear()
    app_module.ai_help_in_flight.clear()

    app_module.player_rooms["sid1"] = "ABCDE"
    app_module.rooms["ABCDE"] = {
        "code": "ABCDE",
        "host_id": "sid1",
        "players": [{"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False}],
        "game_started": False,
    }

    monkeypatch.setattr("app.game_manager.get_game", lambda room: None)
    monkeypatch.setattr("app.game_manager.end_game", lambda room: None)
    monkeypatch.setattr("app.sio.leave_room", AsyncMock())

    asyncio.run(app_module.leave_room("sid1"))

    assert "ABCDE" not in app_module.rooms
    assert "sid1" not in app_module.player_rooms


def test_leave_room_transfers_host(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ABCDE"
    app_module.rooms["ABCDE"] = {
        "code": "ABCDE",
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False},
            {"id": "sid2", "username": "Bob", "player_id": "p2", "ready": False},
        ],
        "game_started": False,
    }

    monkeypatch.setattr("app.game_manager.get_game", lambda room: None)
    monkeypatch.setattr("app.sio.leave_room", AsyncMock())
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())

    asyncio.run(app_module.leave_room("sid1"))

    assert app_module.rooms["ABCDE"]["host_id"] == "sid2"
    assert len(app_module.rooms["ABCDE"]["players"]) == 1

def test_ai_help_rejects_when_request_already_in_flight(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.ai_help_in_flight.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }
    app_module.ai_help_in_flight.add("sid1")

    fake_chat = SimpleNamespace(ask=lambda prompt: "Hit.")
    monkeypatch.setattr("app.chat", fake_chat)

    result = asyncio.run(app_module.ai_help("sid1", {"query": "help"}))

    assert result["error"] == "AI helper is already processing your request."


def test_ai_help_rejects_when_on_cooldown(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.ai_help_last_request_at.clear()
    app_module.ai_help_in_flight.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }
    app_module.ai_help_last_request_at["sid1"] = 100.0

    fake_chat = SimpleNamespace(ask=lambda prompt: "Stand.")
    monkeypatch.setattr("app.chat", fake_chat)
    monkeypatch.setattr("app.time.monotonic", lambda: 101.0)

    result = asyncio.run(app_module.ai_help("sid1", {"query": "help"}))

    assert result["error"] == "Please wait a few seconds before asking AI again."


def test_ai_help_success(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.ai_help_last_request_at.clear()
    app_module.ai_help_in_flight.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }

    fake_chat = SimpleNamespace(ask=lambda prompt: " Hit on 11 versus dealer 10. ")
    monkeypatch.setattr("app.chat", fake_chat)
    monkeypatch.setattr("app.time.monotonic", lambda: 200.0)

    result = asyncio.run(app_module.ai_help("sid1", {"query": "what should I do?"}))

    assert result == {"success": True, "message": "Hit on 11 versus dealer 10."}
    assert "sid1" not in app_module.ai_help_in_flight


def test_ai_help_returns_error_on_empty_response(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.ai_help_last_request_at.clear()
    app_module.ai_help_in_flight.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }

    fake_chat = SimpleNamespace(ask=lambda prompt: "   ")
    monkeypatch.setattr("app.chat", fake_chat)
    monkeypatch.setattr("app.time.monotonic", lambda: 300.0)

    result = asyncio.run(app_module.ai_help("sid1", {"query": "help"}))

    assert result["error"] == "AI helper returned an empty response."


def test_player_ready_toggles_ready_and_broadcasts(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis", "ready": False}]
    }

    mock_broadcast = AsyncMock()
    monkeypatch.setattr("app.broadcast_room_update", mock_broadcast)

    asyncio.run(app_module.player_ready("sid1"))

    assert app_module.rooms["ROOM1"]["players"][0]["ready"] is True
    mock_broadcast.assert_awaited_once_with("ROOM1")


def test_chat_message_emits_sanitized_message(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "players": [{"id": "sid1", "username": "Luis"}]
    }

    mock_emit = AsyncMock()
    monkeypatch.setattr("app.sio.emit", mock_emit)
    monkeypatch.setattr("app.time.time", lambda: 1234.567)

    asyncio.run(app_module.chat_message("sid1", {"message": "  hello table  "}))

    mock_emit.assert_awaited_once()
    args, kwargs = mock_emit.await_args
    assert args[0] == "chat:message"
    assert args[1]["username"] == "Luis"
    assert args[1]["message"] == "hello table"
    assert args[1]["timestamp"] == 1234567
    assert kwargs["room"] == "ROOM1"


def test_room_join_adds_player_directly_when_waiting_for_bets(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_info["sid2"] = {"player_id": "p2"}
    app_module.rooms["ROOM1"] = {
        "code": "ROOM1",
        "host_id": "sid1",
        "players": [{"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False}],
        "game_started": True,
    }

    fake_game = SimpleNamespace(
        phase=app_module.GamePhase.WAITING_FOR_BETS,
        add_player=lambda player_id, username, sid: None,
        get_game_state=lambda: {"phase": "waiting_for_bets"},
    )

    mock_enter = AsyncMock()
    mock_emit = AsyncMock()
    mock_broadcast = AsyncMock()

    monkeypatch.setattr("app.sio.enter_room", mock_enter)
    monkeypatch.setattr("app.sio.emit", mock_emit)
    monkeypatch.setattr("app.broadcast_room_update", mock_broadcast)
    monkeypatch.setattr("app.game_manager.get_game", lambda code: fake_game)

    result = asyncio.run(app_module.room_join("sid2", {"username": "Bob", "code": "ROOM1"}))

    assert result["success"] is True
    assert result["spectator"] is False
    assert app_module.player_rooms["sid2"] == "ROOM1"


def test_room_join_adds_spectator_when_game_active(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()
    app_module.player_info.clear()

    app_module.player_info["sid2"] = {"player_id": "p2"}
    app_module.rooms["ROOM1"] = {
        "code": "ROOM1",
        "host_id": "sid1",
        "players": [{"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False}],
        "game_started": True,
    }

    fake_game = SimpleNamespace(
        phase=app_module.GamePhase.PLAYING,
        get_game_state=lambda: {"phase": "playing"},
    )

    mock_enter = AsyncMock()
    mock_emit = AsyncMock()
    mock_broadcast = AsyncMock()

    monkeypatch.setattr("app.sio.enter_room", mock_enter)
    monkeypatch.setattr("app.sio.emit", mock_emit)
    monkeypatch.setattr("app.broadcast_room_update", mock_broadcast)
    monkeypatch.setattr("app.game_manager.get_game", lambda code: fake_game)

    result = asyncio.run(app_module.room_join("sid2", {"username": "Bob", "code": "ROOM1"}))

    assert result["success"] is True
    assert result["spectator"] is True
    assert app_module.rooms["ROOM1"]["pending_players"][0]["player_id"] == "p2"


def test_leave_room_removes_player_from_game_in_waiting_phase(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "code": "ROOM1",
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False},
            {"id": "sid2", "username": "Bob", "player_id": "p2", "ready": False},
        ],
        "game_started": True,
    }

    removed = []

    fake_game = SimpleNamespace(
        phase=app_module.GamePhase.WAITING_FOR_BETS,
        remove_player=lambda player_id: removed.append(player_id),
        players_dict={"p2": {"username": "Bob", "id": "sid2"}},
        player_bets={},
        get_game_state=lambda: {"phase": "waiting_for_bets"},
    )

    monkeypatch.setattr("app.game_manager.get_game", lambda code: fake_game)
    monkeypatch.setattr("app.sio.leave_room", AsyncMock())
    monkeypatch.setattr("app.sio.emit", AsyncMock())
    monkeypatch.setattr("app.broadcast_room_update", AsyncMock())

    asyncio.run(app_module.leave_room("sid1"))

    assert removed == ["p1"]
    assert app_module.rooms["ROOM1"]["host_id"] == "sid2"


def test_leave_room_marks_pending_removal_during_playing_phase(monkeypatch):
    app_module.rooms.clear()
    app_module.player_rooms.clear()

    leaving_obj = SimpleNamespace(is_stand=False, stand=lambda: None)

    fake_game = SimpleNamespace(
        phase=app_module.GamePhase.PLAYING,
        player_objects={"p1": leaving_obj},
        current_player_index=0,
        advance_to_next_player=lambda: {"phase": "playing"},
        get_game_state=lambda: {"phase": "playing"},
    )

    app_module.player_rooms["sid1"] = "ROOM1"
    app_module.rooms["ROOM1"] = {
        "code": "ROOM1",
        "host_id": "sid1",
        "players": [
            {"id": "sid1", "username": "Luis", "player_id": "p1", "ready": False},
            {"id": "sid2", "username": "Bob", "player_id": "p2", "ready": False},
        ],
        "game_started": True,
    }

    mock_leave = AsyncMock()
    mock_emit = AsyncMock()
    mock_broadcast = AsyncMock()

    monkeypatch.setattr("app.game_manager.get_game", lambda code: fake_game)
    monkeypatch.setattr("app.sio.leave_room", mock_leave)
    monkeypatch.setattr("app.sio.emit", mock_emit)
    monkeypatch.setattr("app.broadcast_room_update", mock_broadcast)

    asyncio.run(app_module.leave_room("sid1"))

    assert app_module.rooms["ROOM1"]["pending_removals"][0]["player_id"] == "p1"
