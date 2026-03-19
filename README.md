# ♠ Blackjack Multiplayer – Game Server

> CS3321 Team Project – `game-server` feature branch

## Quick Start

```bash
# Install dependencies
npm install

# Run the server
npm run dev

# Open in browser
# http://localhost:3000
```

## What's Included

| File | Purpose |
|------|---------|
| `server.js` | Express + Socket.io server — rooms, join codes, player tracking, chat |
| `index.html` | Retro ASCII-styled client — lobby, room view, chat |
| `package.json` | Dependencies: `express`, `socket.io` |

## How It Works

1. **Create a table** → server generates a 5-char room code (e.g., `K7F3P`)
2. **Share the code** → other players enter it to join (up to 6 per room)
3. **Players tracked** by socket ID, username, and IP address
4. **Chat** is scoped to the room
5. **Ready toggle** per player (prep for game start logic)

## Architecture (for connecting to game-core)

The server emits/listens for these Socket.io events:

### Client → Server
| Event | Payload | Description |
|-------|---------|-------------|
| `room:create` | `{ username }` | Create new room |
| `room:join` | `{ username, code }` | Join existing room |
| `room:leave` | — | Leave current room |
| `player:ready` | — | Toggle ready status |
| `chat:message` | `{ message }` | Send chat message |

### Server → Client
| Event | Payload | Description |
|-------|---------|-------------|
| `room:update` | `{ code, players[], hostId, gameStarted }` | Full room state |
| `room:player-joined` | `{ username }` | New player notification |
| `room:new-host` | `{ username }` | Host transferred |
| `chat:message` | `{ username, message, timestamp }` | Chat relay |

## Next Steps (TODO)

- [ ] Hook into Carter's `game-core` — emit `game:start`, `game:deal`, `game:hit`, `game:stand`
- [ ] Broadcast game state (hands, scores, turn order) to all players
- [ ] Integrate Gavin's ChatGPT API advisor as an optional toggle
- [ ] Add player kick (host only)
- [ ] Persist player stats across sessions (optional)

## Branch Strategy

This lives on `game-server`. When ready, PR into `main` (trunk).
