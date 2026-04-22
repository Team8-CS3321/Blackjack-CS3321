import random

SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']

# Gets the value of a hand of cards, accounting for Aces being worth 1 or 11.
# Hands are represented as lists of Card objects.
# Returns a tuple of (hand value, is soft hand).
def hand_value(hand):
    value = 0
    aces = 0
    soft = False

    for card in hand:
        if card.rank in ['Jack', 'Queen', 'King']:
            value += 10
        elif card.rank == 'Ace':
            aces += 1
            value += 11
        else:
            value += int(card.rank)

    while value > 21 and aces:
        value -= 10
        aces -= 1

    if aces > 0:
        soft = True

    return value, soft


class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return f"{self.rank} of {self.suit}"

class Deck:
    def __init__(self):
        self.cards = []
        self.build_deck()

    def shuffle(self):
        random.shuffle(self.cards)

    def build_deck(self):
        self.cards = []
        for suit in SUITS:
            for rank in RANKS:
                self.cards.append(Card(suit, rank))

    def draw_card(self):
        return self.cards.pop()

    def peak_card(self, index):
        return self.cards[index]

class Chip:
    def __init__(self, color, value):
        self.color = color
        self.value = value

class Player:
    def __init__(self, name):
        self.name = name
        self.bet = 0
        self.balance = 1000  # Default starting balance in chips
        self.hand = []
        self.is_bust = False
        self.is_stand = False
        self.is_blackjack = False

    def draw_from_deck(self, deck):
        card = deck.draw_card()
        self.hand.append(card)

    def get_hand(self):
        return self.hand
    
    def place_bet(self, amount):
        """Place a bet, returning True if successful."""
        if amount <= 0 or amount > self.balance:
            return False
        self.bet = amount
        self.balance -= amount
        return True
    
    def reset_hand(self):
        """Reset player state for new round."""
        self.hand = []
        self.is_bust = False
        self.is_stand = False
        self.is_blackjack = False

    def check_blackjack(self) -> bool:
        """Natural blackjack: exactly two cards totaling 21."""
        return len(self.hand) == 2 and self.get_hand_value() == 21
    
    def get_hand_value(self):
        """Get current hand value."""
        value, _ = hand_value(self.hand)
        return value
    
    def hit(self, deck):
        """Draw a card from deck."""
        self.draw_from_deck(deck)
        if self.get_hand_value() > 21:
            self.is_bust = True
    
    def stand(self):
        """Player chooses to stand."""
        self.is_stand = True
    
class Game:
    def __init__(self):
        self.deck = Deck()
        self.players = []
        self.dealer_hand = []
        self.is_active = False

    def add_player(self, player):
        self.players.append(player)

    def remove_player(self, player):
        self.players.remove(player)

    def reset_round(self):
        """Reset all hands for a new round."""
        self.dealer_hand = []
        for player in self.players:
            player.reset_hand()
        # Reshuffle if deck is running low
        if len(self.deck.cards) < 20:
            self.deck.build_deck()
            self.deck.shuffle()

    def deal_initial(self):
        """Deal 2 cards to each player and dealer."""
        for player in self.players:
            player.draw_from_deck(self.deck)
            player.draw_from_deck(self.deck)
        self.dealer_hand.append(self.deck.draw_card())
        self.dealer_hand.append(self.deck.draw_card())

    def dealer_play(self):
        """Execute dealer's turn (hit on 16 or less, stand on 17+)."""
        while True:
            dealer_value = hand_value(self.dealer_hand)[0]
            if dealer_value > 21:
                break
            if dealer_value < 17:
                self.dealer_hand.append(self.deck.draw_card())
            else:
                break

    def get_dealer_hand_value(self):
        """Get dealer's hand value."""
        value, _ = hand_value(self.dealer_hand)
        return value

    def is_dealer_blackjack(self) -> bool:
        """Natural dealer blackjack: exactly two cards totaling 21."""
        return len(self.dealer_hand) == 2 and self.get_dealer_hand_value() == 21

    def determine_winner(self, player):
        """
        Determine outcome for a player.
        Returns: ('win' | 'blackjack' | 'push' | 'lose', payout).
        'blackjack' pays 2x bet plus a 30% bonus on the 2x win (bet 100 -> 260).
        """
        dealer_blackjack = self.is_dealer_blackjack()
        player_blackjack = len(player.hand) == 2 and player.get_hand_value() == 21

        if player_blackjack and dealer_blackjack:
            return ('push', player.bet)
        if player_blackjack:
            base = player.bet * 2
            bonus = (base * 3) // 10
            return ('blackjack', base + bonus)
        if dealer_blackjack:
            return ('lose', 0)

        if player.is_bust:
            return ('lose', 0)

        dealer_value = self.get_dealer_hand_value()
        player_value = player.get_hand_value()

        if dealer_value > 21:
            return ('win', player.bet * 2)
        elif player_value > dealer_value:
            return ('win', player.bet * 2)
        elif player_value == dealer_value:
            return ('push', player.bet)
        else:
            return ('lose', 0)

    def finalize_round(self):
        """Finalize the round and return results for all players."""
        self.dealer_play()
        results = {}
        for player in self.players:
            outcome, payout = self.determine_winner(player)
            player.balance += payout
            results[player.name] = {
                'outcome': outcome,
                'payout': payout,
                'hand_value': player.get_hand_value() if not player.is_bust else 'BUST',
            }
        return results