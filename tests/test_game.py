from game import GameManager, GamePhase


def sample_players():
    return {
        "p1": {"username": "Alice", "id": "sid1"},
        "p2": {"username": "Bob", "id": "sid2"},
    }


def test_game_manager_create_and_get_game():
    manager = GameManager()
    room_game = manager.create_game("ROOM1", sample_players())

    assert room_game.room_code == "ROOM1"
    assert manager.get_game("ROOM1") is room_game


def test_game_manager_end_game_removes_game():
    manager = GameManager()
    manager.create_game("ROOM1", sample_players())

    manager.end_game("ROOM1")

    assert manager.get_game("ROOM1") is None


def test_room_game_initializes_players():
    room_game = GameManager().create_game("ROOM1", sample_players())

    assert len(room_game.player_objects) == 2
    assert len(room_game.game.players) == 2
    assert room_game.phase == GamePhase.WAITING_FOR_BETS


def test_place_bet_success():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.place_bet("p1", 100)

    assert result["success"] is True
    assert room_game.player_bets["p1"] == 100
    assert room_game.player_objects["p1"].balance == 900


def test_place_bet_rejects_invalid_player():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.place_bet("bad_id", 100)

    assert result["error"] == "Player not in game."


def test_place_bet_rejects_invalid_amount():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.place_bet("p1", 5000)

    assert result["error"] == "Invalid bet amount."


def test_start_round_requires_all_bets():
    room_game = GameManager().create_game("ROOM1", sample_players())
    room_game.place_bet("p1", 100)

    result = room_game.start_round()

    assert result["error"] == "Not all players have placed bets."


def test_start_round_transitions_to_playing():
    room_game = GameManager().create_game("ROOM1", sample_players())
    room_game.place_bet("p1", 100)
    room_game.place_bet("p2", 150)

    result = room_game.start_round()

    assert room_game.phase == GamePhase.PLAYING
    assert result["phase"] == "playing"
    assert len(room_game.game.dealer_hand) == 2
    assert len(room_game.player_objects["p1"].hand) == 2
    assert len(room_game.player_objects["p2"].hand) == 2


def test_get_game_state_returns_expected_structure():
    room_game = GameManager().create_game("ROOM1", sample_players())

    state = room_game.get_game_state()

    assert "phase" in state
    assert "players" in state
    assert "dealer_hand" in state
    assert "current_player_index" in state
    assert len(state["players"]) == 2


def test_add_player_registers_player_in_active_game():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.add_player("p3", "Carol", "sid3")

    assert result["success"] is True
    assert "p3" in room_game.player_objects
    assert room_game.players_dict["p3"]["username"] == "Carol"
    assert room_game.players_dict["p3"]["id"] == "sid3"
    assert len(room_game.game.players) == 3


def test_add_player_ignores_duplicate_player_id():
    room_game = GameManager().create_game("ROOM1", sample_players())

    room_game.add_player("p3", "Carol", "sid3")
    second = room_game.add_player("p3", "Carol", "sid3")

    assert second["success"] is True
    assert len(room_game.game.players) == 3


def test_remove_player_removes_game_membership_and_bet_tracking():
    room_game = GameManager().create_game("ROOM1", sample_players())
    room_game.add_player("p3", "Carol", "sid3")
    room_game.place_bet("p3", 50)

    result = room_game.remove_player("p3")

    assert result["success"] is True
    assert "p3" not in room_game.player_objects
    assert "p3" not in room_game.players_dict
    assert "p3" not in room_game.player_bets
    assert len(room_game.game.players) == 2


def test_remove_player_is_noop_for_unknown_player():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.remove_player("missing")

    assert result["success"] is True
    assert len(room_game.game.players) == 2


def test_stand_in_wrong_phase_returns_error():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.stand("p1")

    assert result["error"] == "Not in playing phase."


def test_hit_in_wrong_phase_returns_error():
    room_game = GameManager().create_game("ROOM1", sample_players())

    result = room_game.hit("p1")

    assert result["error"] == "Not in playing phase."


def test_get_final_state_includes_dealer_value():
    room_game = GameManager().create_game("ROOM1", sample_players())
    room_game.place_bet("p1", 100)
    room_game.place_bet("p2", 100)
    room_game.start_round()

    final_state = room_game.get_final_state()

    assert "dealer_hand" in final_state
    assert "dealer_value" in final_state

