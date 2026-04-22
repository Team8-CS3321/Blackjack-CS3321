from .rules_and_objects import *
from enum import Enum
from typing import Optional


class GamePhase(Enum):
    """Phases of a Blackjack game."""
    WAITING_FOR_BETS = "waiting_for_bets"
    DEALING = "dealing"
    PLAYING = "playing"
    DEALER_TURN = "dealer_turn"
    ROUND_COMPLETE = "round_complete"


class GameManager:
    """Manages Blackjack games for multiplayer rooms."""
    
    def __init__(self):
        self.active_games: dict[str, 'RoomGame'] = {}
    
    def create_game(self, room_code: str, players_dict: dict) -> 'RoomGame':
        """Create a new game for a room."""
        game = RoomGame(room_code, players_dict)
        self.active_games[room_code] = game
        return game
    
    def get_game(self, room_code: str) -> Optional['RoomGame']:
        """Get active game for a room."""
        return self.active_games.get(room_code)
    
    def end_game(self, room_code: str) -> None:
        """End and remove game for a room."""
        if room_code in self.active_games:
            del self.active_games[room_code]


class RoomGame:
    """Represents a Blackjack game in a specific room."""
    
    def __init__(self, room_code: str, players_dict: dict):
        """
        Initialize game for a room.
        players_dict: {player_id: {'username': str, 'id': sid}}
        """
        self.room_code = room_code
        self.players_dict = players_dict  # Store socket IDs for emit targets
        self.game = Game()
        self.phase = GamePhase.WAITING_FOR_BETS
        self.player_bets: dict[str, int] = {}  # player_id -> bet amount
        self.player_objects: dict[str, Player] = {}  # player_id -> Player object
        self.current_player_index = 0
        
        # Initialize players
        for player_id, player_info in players_dict.items():
            player = Player(player_info['username'])
            self.player_objects[player_id] = player
            self.game.add_player(player)
    
    def start_round(self) -> dict:
        """Start a new round, return game state."""
        # Check all players have placed bets
        if len(self.player_bets) != len(self.players_dict):
            return {"error": "Not all players have placed bets."}

        # Reset hands
        self.game.reset_round()

        # Deal initial cards
        self.game.deal_initial()
        self.phase = GamePhase.DEALING

        # Detect natural blackjacks. Any player with Ace + 10-value auto-stands
        # so turn order skips them; payouts are resolved in finalize_round via
        # determine_winner, which credits a 30% bonus on top of the standard win.
        dealer_blackjack = self.game.is_dealer_blackjack()
        for player in self.game.players:
            if player.check_blackjack():
                player.is_blackjack = True
                player.is_stand = True

        # If dealer has blackjack the round ends immediately — no player
        # decisions matter. determine_winner handles push vs. lose for each
        # player based on whether they also have a natural.
        if dealer_blackjack:
            return self._finalize_round_early()

        # If every player has a natural blackjack there is no one to play.
        active_players = [
            p for p in self.game.players if not p.is_stand and not p.is_bust
        ]
        if not active_players:
            return self._finalize_round_early()

        self.phase = GamePhase.PLAYING
        self.current_player_index = self._next_active_index(0)

        return self.get_game_state()

    def _finalize_round_early(self) -> dict:
        """End the current round immediately (dealer blackjack or all standing)."""
        self.phase = GamePhase.DEALER_TURN
        results = self.game.finalize_round()
        self.phase = GamePhase.ROUND_COMPLETE
        state = self.get_game_state()
        state["phase"] = self.phase.value
        state["message"] = (
            "Dealer has Blackjack!" if self.game.is_dealer_blackjack() else "Round complete"
        )
        state["results"] = results
        state["dealer_hand"] = [str(card) for card in self.game.dealer_hand]
        state["dealer_value"] = self.game.get_dealer_hand_value()
        return state

    def _next_active_index(self, start: int) -> int:
        """Return the first index >= start whose player still needs to act."""
        player_ids = list(self.player_objects.keys())
        i = start
        while i < len(player_ids):
            p = self.player_objects[player_ids[i]]
            if not p.is_stand and not p.is_bust:
                return i
            i += 1
        return i
    
    def place_bet(self, player_id: str, amount: int) -> dict:
        """Place bet for a player."""
        if self.phase != GamePhase.WAITING_FOR_BETS:
            return {"error": "Not in betting phase."}
        
        if player_id not in self.player_objects:
            return {"error": "Player not in game."}
        
        player = self.player_objects[player_id]
        if not player.place_bet(amount):
            return {"error": "Invalid bet amount."}
        
        self.player_bets[player_id] = amount
        return {"success": True, "message": f"Bet placed: {amount}"}

    def add_player(self, player_id: str, username: str, sid: Optional[str] = None) -> dict:
        """Add a player to the game state if they are not already present."""
        if player_id in self.player_objects:
            return {"success": True, "message": "Player already in game."}

        player = Player(username)
        self.player_objects[player_id] = player
        self.players_dict[player_id] = {"username": username, "id": sid or ""}
        self.game.add_player(player)
        return {"success": True, "message": "Player added to game."}

    def remove_player(self, player_id: str) -> dict:
        """Remove a player from game state if they are currently registered."""
        player = self.player_objects.pop(player_id, None)
        if not player:
            return {"success": True, "message": "Player not in game."}

        self.players_dict.pop(player_id, None)
        self.player_bets.pop(player_id, None)
        if player in self.game.players:
            self.game.remove_player(player)

        if self.current_player_index >= len(self.game.players):
            self.current_player_index = 0

        return {"success": True, "message": "Player removed from game."}
    
    def hit(self, player_id: str) -> dict:
        """Player hits."""
        if self.phase != GamePhase.PLAYING:
            return {"error": "Not in playing phase."}
        
        player = self.player_objects.get(player_id)
        if not player:
            return {"error": "Player not found."}
        
        player.hit(self.game.deck)
        
        if player.is_bust:
            return self.advance_to_next_player()
        
        return self.get_game_state()
    
    def stand(self, player_id: str) -> dict:
        """Player stands."""
        if self.phase != GamePhase.PLAYING:
            return {"error": "Not in playing phase."}
        
        player = self.player_objects.get(player_id)
        if not player:
            return {"error": "Player not found."}
        
        player.stand()
        return self.advance_to_next_player()
    
    def advance_to_next_player(self) -> dict:
        """Move to next active player or dealer."""
        self.current_player_index = self._next_active_index(self.current_player_index + 1)

        # Skip busted/standing players
        active_players = [p for p in self.game.players if not p.is_bust and not p.is_stand]

        if active_players:
            return self.get_game_state()
        
        # All players done, dealer's turn
        self.phase = GamePhase.DEALER_TURN
        results = self.game.finalize_round()
        self.phase = GamePhase.ROUND_COMPLETE
        
        return {
            "phase": self.phase.value,
            "message": "Round complete",
            "results": results,
            "dealer_hand": [str(card) for card in self.game.dealer_hand],
            "dealer_value": self.game.get_dealer_hand_value(),
        }
    
    def reset_for_next_round(self, new_players: list[dict] | None = None) -> None:
        """Reset for a new round, preserving player_objects insertion order.

        new_players: list of {player_id, username} for spectators to promote
        into active players. Appended at the end so existing turn order is
        preserved. current_player_index resets to 0 so it always points at
        an existing player, never into the newly-added tail.
        """
        # Promote any pending spectators into real players BEFORE reset_round
        # so their hands get cleared like everyone else's. We use the existing
        # Game.add_player helper rather than touching self.game.players directly.
        if new_players:
            for np in new_players:
                pid = np["player_id"]
                self.add_player(pid, np["username"], np.get("sid"))

        self.game.reset_round()
        for player_obj in self.player_objects.values():
            player_obj.bet = 0
        self.player_bets.clear()
        self.current_player_index = 0
        self.phase = GamePhase.WAITING_FOR_BETS

    def get_game_state(self) -> dict:
        """Get current game state for broadcasting."""
        player_states = []
        for pid, player_obj in self.player_objects.items():
            player_states.append({
                "player_id": pid,
                "username": player_obj.name,
                "hand": [str(card) for card in player_obj.hand],
                "hand_value": player_obj.get_hand_value() if not player_obj.is_bust else None,
                "bet": player_obj.bet,
                "balance": player_obj.balance,
                "is_bust": player_obj.is_bust,
                "is_stand": player_obj.is_stand,
                "is_blackjack": player_obj.is_blackjack,
            })
        
        return {
            "phase": self.phase.value,
            "players": player_states,
            "dealer_hand": [str(card) for card in self.game.dealer_hand[:1]],  # Only show first card during play
            "current_player_index": self.current_player_index,
        }
    
    def get_final_state(self) -> dict:
        """Get final state including dealer hand."""
        state = self.get_game_state()
        state["dealer_hand"] = [str(card) for card in self.game.dealer_hand]
        state["dealer_value"] = self.game.get_dealer_hand_value()
        return state


def main():
    """Test the game locally."""
    # Example: Create a game with 2 players
    manager = GameManager()
    players_dict = {
        "player1": {"username": "Alice", "id": "sid1"},
        "player2": {"username": "Bob", "id": "sid2"},
    }
    
    game = manager.create_game("TEST01", players_dict)
    print(f"Game created for room TEST01")
    print(f"Players: {[p.name for p in game.game.players]}")
    
    # Place bets
    game.place_bet("player1", 50)
    game.place_bet("player2", 100)
    print(f"\nBets placed: {game.player_bets}")
    
    # Start round
    state = game.start_round()
    print(f"\nGame state: {state}")


if __name__ == "__main__":
    main()
