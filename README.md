# Blackjack Multiplayer  
  
> CS3321 Team 8 Project — Multiplayer Blackjack Game  
  
## Quick Start  
  
```bash  
# Clone repo (requires authentication)
gh repo clone Team8-CS3321/Blackjack-CS3321
cd Blackjack-CS3321

# Create virtual environment with dependencies(one-time)  
uv sync

# Login to doppler for team secrets  
doppler login  

# Setup Doppler configuration
doppler setup # Select "dev"
  
# Run the server  
doppler run -- uv run python .\backend\blackjack\app.py

# Open in browser  
http://localhost:3000  
```  
## Docker (WIP)
 ```bash
 # Build image
 docker build -t # blackjack-isu-cs3321-s26:<tag> .

# Run with secrets
doppler run -- docker run blackjack-isu-cs3321-s26
 ``` 

 ## Testing
 ```bash
 # Run unit tests
 uv run pytest

 # Get coverage report
 uv run pytest --cov=backend --cov-report=html
 ```

## What's Included

| File | Purpose |
|------|---------|
| `backend/app.py` | Quart + python-socketio server — rooms, join codes, player tracking, chat |
| `backend/ChatGPTClient.py` | ChatGPT client for AI-powered blackjack advice and rule reminders |
| `backend/game.py` | Core blackjack game logic and room management |
| `backend/rules_and_objects.py` | Definitions for cards, deck, hands, players, and game rules |
| `frontend/index.html` | Retro ASCII-styled client — lobby, room view, chat |
| `pyproject.toml` | Dependencies: `quart`, `python-socketio`, `uvicorn`, `openai` |
  
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
| `ai:help` | `{ query }` | Request AI advice |
| `game:start` | — | Start the game (host only) |
| `game:place-bet` | `{ amount }` | Place bet for the round |
| `game:hit` | — | Hit (draw a card) |
| `game:stand` | — | Stand (end turn) |
| `game:get-state` | — | Request current game state |
| `game:next-round` | — | Start next round (host or solo) |
| `singleplayer:start` | `{ username }` | Start single-player game |


### Server -> Client

  

| Event | Payload | Description |
|-------|---------|-------------|
| `room:update` | `{ code, players[], hostId, gameStarted }` | Full room state |
| `room:player-joined` | `{ username, spectator }` | New player notification |
| `room:player-left` | `{ username }` | Player left notification |
| `room:new-host` | `{ username }` | Host transferred |
| `chat:message` | `{ username, message, timestamp }` | Chat relay |
| `game:started` | `{ message }` | Game started notification |
| `game:round-started` | game state | Round started with initial hands |
| `game:state` | game state | Current game state update |
| `singleplayer:ready` | `{ code, player_id, room, state }` | Single-player game ready |


## Team  
  
- **Pravesh Aryal** — Server (Quart/Python port)  and UI Design
- **Carter Luker** — Project Management and Architecture  
- **Steve Taylor (Gavin)** — Chat and AI Tools
- **Luis Hernandez** — Testing Lead
