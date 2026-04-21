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
