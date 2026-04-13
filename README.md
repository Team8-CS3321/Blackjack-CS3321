# Blackjack Multiplayer

> CS3321 Team 8 Project — Multiplayer Blackjack Game

## Quick Start

```bash
# Create virtual environment (one-time)
python -m venv venv

# Install dependencies
venv/Scripts/pip install -r requirements.txt

# Login to doppler for team secrets
doppler login

# Run the server
doppler run -- venv/Scripts/python src/app.py

# Open in browser
# http://localhost:3000
```

## What's Included

| File | Purpose |
|------|---------|
| `app.py` | Quart + python-socketio server — rooms, join codes, player tracking, chat |
| `public/index.html` | Retro ASCII-styled client — lobby, room view, chat |
| `requirements.txt` | Dependencies: `quart`, `python-socketio`, `uvicorn`, `openai` |

## How It Works

1. **Create a table** — server generates a 5-char room code (e.g., `K7F3P`)
2. **Share the code** — other players enter it to join (up to 6 per room)
3. **Chat** is scoped to the room
4. **Ready toggle** per player (prep for game start logic)

## Socket.IO Events

### Client -> Server

| Event | Payload | Description |
|-------|---------|-------------|
| `room:create` | `{ username }` | Create new room |
| `room:join` | `{ username, code }` | Join existing room |
| `room:leave` | — | Leave current room |
| `player:ready` | — | Toggle ready status |
| `chat:message` | `{ message }` | Send chat message |

### Server -> Client

| Event | Payload | Description |
|-------|---------|-------------|
| `room:update` | `{ code, players[], hostId, gameStarted }` | Full room state |
| `room:player-joined` | `{ username }` | New player notification |
| `room:player-left` | `{ username }` | Player left notification |
| `room:new-host` | `{ username }` | Host transferred |
| `chat:message` | `{ username, message, timestamp }` | Chat relay |

## TODO

- [ ] Integrate Deck of Cards API for card dealing
- [ ] Game logic (hit, stand, bust, dealer turn)
- [ ] Dockerfile for containerized deployment
- [ ] GitHub Actions CI/CD pipeline
- [ ] Doppler secret management
- [ ] AWS deployment (EC2/ECS)
- [ ] Unit tests (80% coverage target)

## Team

- **Pravesh Aryal** — Server (Quart/Python port)
- **Carter Luker** — GitHub org, architecture
- **Steve Taylor (Gavin)** — TBD
