import importlib
from types import SimpleNamespace
import pytest
import ChatGPTClient as chat_module


def test_chatgptclient_requires_api_key(monkeypatch):
    monkeypatch.delenv("CHATGPT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError):
        chat_module.ChatGPTClient()


def test_chatgptclient_init_uses_api_key(monkeypatch):
    created = {}

    def fake_openai(api_key):
        created["api_key"] = api_key
        return SimpleNamespace()

    monkeypatch.setenv("CHATGPT", "test-key")
    monkeypatch.setattr(chat_module, "OpenAI", fake_openai)

    client = chat_module.ChatGPTClient()

    assert created["api_key"] == "test-key"
    assert client.request_timeout_seconds == 12


def test_chatgptclient_ask_returns_message_content(monkeypatch):
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Stand."))]
    )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: fake_response
            )
        )
    )

    monkeypatch.setenv("CHATGPT", "test-key")
    monkeypatch.setattr(chat_module, "OpenAI", lambda api_key: fake_client)

    client = chat_module.ChatGPTClient()
    result = client.ask("I have 16 against 10")

    assert result == "Stand."


def test_get_recommended_move_calls_ask(monkeypatch):
    monkeypatch.setenv("CHATGPT", "test-key")
    monkeypatch.setattr(chat_module, "OpenAI", lambda api_key: SimpleNamespace())

    client = chat_module.ChatGPTClient()
    monkeypatch.setattr(client, "ask", lambda query: "Hit")

    result = client.getRecommendedMove("7 and queen", "8 and king")

    assert result == "Hit"


def test_get_rules_calls_ask(monkeypatch):
    monkeypatch.setenv("CHATGPT", "test-key")
    monkeypatch.setattr(chat_module, "OpenAI", lambda api_key: SimpleNamespace())

    client = chat_module.ChatGPTClient()
    monkeypatch.setattr(client, "ask", lambda query: "Blackjack rules")

    result = client.getRules()

    assert result == "Blackjack rules"


def test_example_calls_recommended_move(monkeypatch):
    monkeypatch.setenv("CHATGPT", "test-key")
    monkeypatch.setattr(chat_module, "OpenAI", lambda api_key: SimpleNamespace())

    client = chat_module.ChatGPTClient()
    monkeypatch.setattr(client, "getRecommendedMove", lambda player, dealer: "Stand")

    result = client.example()

    assert result == "Stand"
