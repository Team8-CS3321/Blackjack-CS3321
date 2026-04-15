from openai import OpenAI
import os

class ChatGPTClient:
    def __init__(self):
        api_key = os.getenv("CHATGPT")
        self.client = OpenAI(api_key=api_key)
        self.request_timeout_seconds = 12

    def ask(self, query: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
		 {"role": "system", "content": "Answer in 1-2 concise sentences. You are a friend helping someone decide their plays in blackjack."},
		 {"role": "user", "content": query}
            ],
	    max_tokens=60,
	    timeout=self.request_timeout_seconds,
        )

        return response.choices[0].message.content


    def getRecommendedMove(self, playerHand, dealerHand):
        return self.ask(f"I have {playerHand}, and the dealer has {dealerHand}. Should I hit, or stand?")


    def getRules(self):
        return self.ask("Remind me of the rules of blackjack.")


    def example(self):
        return self.getRecommendedMove("7 and queen", "8 and king")
