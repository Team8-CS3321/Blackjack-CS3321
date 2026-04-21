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

class FixedDeck:
    def __init__(self, cards):
        self.cards = list(cards)

    def draw_card(self):
        return self.cards.pop(0)


def test_peak_card_returns_expected_card():
    deck = Deck()
    first = deck.peak_card(0)
    assert isinstance(first, Card)
    assert str(first) == str(deck.cards[0])


def test_player_draw_from_deck_adds_card_to_hand():
    player = Player("Luis")
    deck = FixedDeck([Card("Hearts", "9")])

    player.draw_from_deck(deck)

    assert len(player.hand) == 1
    assert str(player.hand[0]) == "9 of Hearts"


def test_player_get_hand_returns_hand_reference():
    player = Player("Luis")
    player.hand = [Card("Spades", "Ace")]

    hand = player.get_hand()

    assert len(hand) == 1
    assert str(hand[0]) == "Ace of Spades"


def test_player_get_hand_value_uses_hand_value_function():
    player = Player("Luis")
    player.hand = [Card("Hearts", "Ace"), Card("Clubs", "7")]

    assert player.get_hand_value() == 18


def test_player_hit_without_busting():
    player = Player("Luis")
    player.hand = [Card("Hearts", "10")]
    deck = FixedDeck([Card("Spades", "7")])

    player.hit(deck)

    assert player.get_hand_value() == 17
    assert player.is_bust is False


def test_player_hit_sets_bust_when_over_21():
    player = Player("Luis")
    player.hand = [Card("Hearts", "10"), Card("Diamonds", "9")]
    deck = FixedDeck([Card("Spades", "5")])

    player.hit(deck)

    assert player.get_hand_value() == 24
    assert player.is_bust is True


def test_game_reset_round_clears_dealer_and_player_states():
    game = Game()
    player = Player("Luis")
    player.hand = [Card("Hearts", "10")]
    player.is_bust = True
    player.is_stand = True
    game.add_player(player)
    game.dealer_hand = [Card("Spades", "Ace")]

    game.reset_round()

    assert game.dealer_hand == []
    assert player.hand == []
    assert player.is_bust is False
    assert player.is_stand is False


def test_game_reset_round_rebuilds_and_shuffles_when_deck_low(monkeypatch):
    game = Game()
    game.deck.cards = [Card("Hearts", "2")] * 10

    called = {"build": 0, "shuffle": 0}

    def fake_build():
        called["build"] += 1
        game.deck.cards = [Card("Spades", "Ace")] * 52

    def fake_shuffle():
        called["shuffle"] += 1

    monkeypatch.setattr(game.deck, "build_deck", fake_build)
    monkeypatch.setattr(game.deck, "shuffle", fake_shuffle)

    game.reset_round()

    assert called["build"] == 1
    assert called["shuffle"] == 1
    assert len(game.deck.cards) == 52


def test_deal_initial_gives_two_cards_to_each_player_and_dealer():
    game = Game()
    p1 = Player("Luis")
    p2 = Player("Bob")
    game.add_player(p1)
    game.add_player(p2)

    game.deck = FixedDeck([
        Card("Hearts", "2"),
        Card("Hearts", "3"),
        Card("Hearts", "4"),
        Card("Hearts", "5"),
        Card("Spades", "9"),
        Card("Spades", "10"),
    ])

    game.deal_initial()

    assert len(p1.hand) == 2
    assert len(p2.hand) == 2
    assert len(game.dealer_hand) == 2


def test_dealer_play_hits_until_at_least_17():
    game = Game()
    game.dealer_hand = [Card("Hearts", "5"), Card("Clubs", "6")]
    game.deck = FixedDeck([
        Card("Spades", "4"),
        Card("Diamonds", "3"),
    ])

    game.dealer_play()

    assert game.get_dealer_hand_value() >= 17


def test_dealer_play_stops_immediately_on_17_or_more():
    game = Game()
    game.dealer_hand = [Card("Hearts", "10"), Card("Clubs", "7")]
    game.deck = FixedDeck([Card("Spades", "4")])

    game.dealer_play()

    assert len(game.dealer_hand) == 2
    assert game.get_dealer_hand_value() == 17


def test_determine_winner_when_dealer_busts():
    game = Game()
    player = Player("Luis")
    player.bet = 50
    player.hand = [Card("Hearts", "10"), Card("Clubs", "9")]
    game.dealer_hand = [Card("Spades", "10"), Card("Diamonds", "9"), Card("Hearts", "5")]

    outcome, payout = game.determine_winner(player)

    assert outcome == "win"
    assert payout == 100


def test_determine_winner_when_player_beats_dealer():
    game = Game()
    player = Player("Luis")
    player.bet = 25
    player.hand = [Card("Hearts", "10"), Card("Clubs", "9")]
    game.dealer_hand = [Card("Spades", "10"), Card("Diamonds", "7")]

    outcome, payout = game.determine_winner(player)

    assert outcome == "win"
    assert payout == 50


def test_determine_winner_push_returns_bet():
    game = Game()
    player = Player("Luis")
    player.bet = 30
    player.hand = [Card("Hearts", "10"), Card("Clubs", "8")]
    game.dealer_hand = [Card("Spades", "9"), Card("Diamonds", "9")]

    outcome, payout = game.determine_winner(player)

    assert outcome == "push"
    assert payout == 30


def test_determine_winner_player_loses():
    game = Game()
    player = Player("Luis")
    player.bet = 40
    player.hand = [Card("Hearts", "10"), Card("Clubs", "6")]
    game.dealer_hand = [Card("Spades", "10"), Card("Diamonds", "8")]

    outcome, payout = game.determine_winner(player)

    assert outcome == "lose"
    assert payout == 0


def test_finalize_round_updates_balances_and_results(monkeypatch):
    game = Game()
    p1 = Player("Luis")
    p2 = Player("Bob")
    p1.bet = 50
    p2.bet = 25
    p1.balance = 900
    p2.balance = 800
    p1.hand = [Card("Hearts", "10"), Card("Clubs", "9")]
    p2.hand = [Card("Hearts", "10"), Card("Clubs", "6")]
    game.add_player(p1)
    game.add_player(p2)
    game.dealer_hand = [Card("Spades", "10"), Card("Diamonds", "7")]

    monkeypatch.setattr(game, "dealer_play", lambda: None)

    results = game.finalize_round()

    assert results["Luis"]["outcome"] == "win"
    assert results["Bob"]["outcome"] == "lose"
    assert p1.balance == 1000
    assert p2.balance == 800


def test_finalize_round_marks_bust_player_as_bust(monkeypatch):
    game = Game()
    p1 = Player("Luis")
    p1.bet = 20
    p1.balance = 500
    p1.is_bust = True
    p1.hand = [Card("Hearts", "10"), Card("Clubs", "9"), Card("Spades", "5")]
    game.add_player(p1)
    game.dealer_hand = [Card("Spades", "10"), Card("Diamonds", "7")]

    monkeypatch.setattr(game, "dealer_play", lambda: None)

    results = game.finalize_round()

    assert results["Luis"]["outcome"] == "lose"
    assert results["Luis"]["hand_value"] == "BUST"
