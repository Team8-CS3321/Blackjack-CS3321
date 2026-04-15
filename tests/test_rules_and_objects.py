from rules_and_objects import Card, Deck, Player, Game, hand_value


def test_card_string_representation():
    card = Card("Hearts", "Ace")
    assert str(card) == "Ace of Hearts"


def test_hand_value_without_aces():
    hand = [Card("Hearts", "10"), Card("Spades", "7")]
    value, soft = hand_value(hand)
    assert value == 17
    assert soft is False


def test_hand_value_with_soft_ace():
    hand = [Card("Hearts", "Ace"), Card("Spades", "6")]
    value, soft = hand_value(hand)
    assert value == 17
    assert soft is True


def test_hand_value_with_ace_adjustment():
    hand = [Card("Hearts", "Ace"), Card("Spades", "King"), Card("Clubs", "5")]
    value, soft = hand_value(hand)
    assert value == 16
    assert soft is False


def test_deck_builds_52_cards():
    deck = Deck()
    assert len(deck.cards) == 52


def test_draw_card_reduces_deck_size():
    deck = Deck()
    original_size = len(deck.cards)
    card = deck.draw_card()
    assert isinstance(card, Card)
    assert len(deck.cards) == original_size - 1


def test_player_place_valid_bet():
    player = Player("Luis")
    success = player.place_bet(100)
    assert success is True
    assert player.bet == 100
    assert player.balance == 900


def test_player_rejects_invalid_bet():
    player = Player("Luis")
    assert player.place_bet(0) is False
    assert player.place_bet(-5) is False
    assert player.place_bet(2000) is False
    assert player.balance == 1000


def test_player_reset_hand_clears_state():
    player = Player("Luis")
    player.hand = [Card("Hearts", "10")]
    player.is_bust = True
    player.is_stand = True

    player.reset_hand()

    assert player.hand == []
    assert player.is_bust is False
    assert player.is_stand is False


def test_player_stand_sets_flag():
    player = Player("Luis")
    player.stand()
    assert player.is_stand is True


def test_game_add_and_remove_player():
    game = Game()
    player = Player("Luis")
    game.add_player(player)
    assert player in game.players

    game.remove_player(player)
    assert player not in game.players


def test_game_determine_winner_player_bust():
    game = Game()
    player = Player("Luis")
    player.bet = 100
    player.is_bust = True

    outcome, payout = game.determine_winner(player)
    assert outcome == "lose"
    assert payout == 0

