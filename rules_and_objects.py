import random

SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
    # TODO: Implement __str__ method to display the card nicely

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
        self.hand = []

    def draw_from_deck(self, deck):
        card = deck.draw_card()
        self.hand.append(card)

    def show_hand(self):
        return [str(card) for card in self.hand]