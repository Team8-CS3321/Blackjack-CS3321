const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const publicDir = path.join(__dirname, "public");

app.use(express.static(publicDir));

app.get("/", (req, res) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

// ─── In-memory store for rooms ───────────────────────────────────────
const rooms = new Map();

// ─── Helpers ─────────────────────────────────────────────────────────

function generateRoomCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no ambiguous chars
  let code = "";
  for (let i = 0; i < 5; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return rooms.has(code) ? generateRoomCode() : code;
}

function getPlayerIP(socket) {
  return (
    socket.handshake.headers["x-forwarded-for"] ||
    socket.handshake.address ||
    "unknown"
  );
}

function getRoomState(room) {
  return {
    code: room.code,
    players: room.players.map((p) => ({
      id: p.id,
      username: p.username,
      ready: p.ready,
    })),
    hostId: room.hostId,
    gameStarted: room.gameStarted,
  };
}

function normalizeUsername(username) {
  if (typeof username !== "string") return "";
  return username.trim().slice(0, 16);
}

function normalizeRoomCode(code) {
  if (typeof code !== "string") return "";
  return code.toUpperCase().trim().slice(0, 5);
}

function normalizeChatMessage(message) {
  if (typeof message !== "string") return "";
  return message.trim().slice(0, 200);
}

function roomHasUsername(room, username) {
  return room.players.some(
    (player) => player.username.toLowerCase() === username.toLowerCase()
  );
}

function broadcastRoomUpdate(roomCode) {
  const room = rooms.get(roomCode);
  if (!room) return;
  io.to(roomCode).emit("room:update", getRoomState(room));
}

// ─── Socket.io event handling ────────────────────────────────────────

io.on("connection", (socket) => {
  const ip = getPlayerIP(socket);
  console.log(`[connect] ${socket.id} from ${ip}`);

  let currentRoom = null;

  // ── Create a new room ──────────────────────────────────────────────
  socket.on("room:create", ({ username }, callback) => {
    if (currentRoom) {
      return callback({ error: "You are already in a room. Leave first." });
    }

    const normalizedUsername = normalizeUsername(username);
    if (!normalizedUsername) {
      return callback({ error: "Username is required." });
    }

    const code = generateRoomCode();
    const player = { id: socket.id, username: normalizedUsername, ip, ready: false };

    const room = {
      code,
      hostId: socket.id,
      players: [player],
      gameStarted: false,
    };

    rooms.set(code, room);
    socket.join(code);
    currentRoom = code;

    console.log(`[room:create] ${normalizedUsername} created room ${code}`);
    callback({ success: true, code });
    broadcastRoomUpdate(code);
  });

  // ── Join an existing room ──────────────────────────────────────────
  socket.on("room:join", ({ username, code }, callback) => {
    if (currentRoom) {
      return callback({ error: "You are already in a room. Leave first." });
    }

    const normalizedUsername = normalizeUsername(username);
    if (!normalizedUsername) {
      return callback({ error: "Username is required." });
    }

    const roomCode = normalizeRoomCode(code);
    if (!roomCode) {
      return callback({ error: "Room code is required." });
    }

    const room = rooms.get(roomCode);

    if (!room) {
      return callback({ error: `Room "${roomCode}" not found.` });
    }
    if (room.gameStarted) {
      return callback({ error: "Game already in progress." });
    }
    if (room.players.length >= 6) {
      return callback({ error: "Room is full (max 6 players)." });
    }
    if (roomHasUsername(room, normalizedUsername)) {
      return callback({ error: "Username already taken in this room." });
    }

    const player = { id: socket.id, username: normalizedUsername, ip, ready: false };
    room.players.push(player);
    socket.join(roomCode);
    currentRoom = roomCode;

    console.log(`[room:join] ${normalizedUsername} joined room ${roomCode}`);
    callback({ success: true, code: roomCode });

    // notify existing players
    socket.to(roomCode).emit("room:player-joined", { username: normalizedUsername });
    broadcastRoomUpdate(roomCode);
  });

  // ── Toggle ready status ────────────────────────────────────────────
  socket.on("player:ready", () => {
    if (!currentRoom) return;
    const room = rooms.get(currentRoom);
    if (!room) return;

    const player = room.players.find((p) => p.id === socket.id);
    if (player) {
      player.ready = !player.ready;
      broadcastRoomUpdate(currentRoom);
    }
  });

  // ── Chat message ───────────────────────────────────────────────────
  socket.on("chat:message", ({ message }) => {
    if (!currentRoom) return;
    const room = rooms.get(currentRoom);
    if (!room) return;

    const normalizedMessage = normalizeChatMessage(message);
    if (!normalizedMessage) return;

    const player = room.players.find((p) => p.id === socket.id);
    if (!player) return;

    io.to(currentRoom).emit("chat:message", {
      username: player.username,
      message: normalizedMessage,
      timestamp: Date.now(),
    });
  });

  // ── Leave room ─────────────────────────────────────────────────────
  socket.on("room:leave", () => {
    leaveRoom(socket);
  });

  // ── Disconnect ─────────────────────────────────────────────────────
  socket.on("disconnect", () => {
    console.log(`[disconnect] ${socket.id}`);
    leaveRoom(socket);
  });

  function leaveRoom(sock) {
    if (!currentRoom) return;
    const room = rooms.get(currentRoom);
    if (!room) return;

    const leavingPlayer = room.players.find((p) => p.id === sock.id);
    room.players = room.players.filter((p) => p.id !== sock.id);
    sock.leave(currentRoom);

    const leftRoom = currentRoom;
    currentRoom = null;

    if (room.players.length === 0) {
      rooms.delete(leftRoom);
      console.log(`[room:delete] room ${leftRoom} is now empty`);
    } else {
      io.to(leftRoom).emit("room:player-left", {
        username: leavingPlayer?.username || "A player",
      });

      // transfer host if needed
      if (room.hostId === sock.id) {
        room.hostId = room.players[0].id;
        io.to(leftRoom).emit("room:new-host", {
          username: room.players[0].username,
        });
      }
      broadcastRoomUpdate(leftRoom);
    }
  }
});

// ─── Start server ────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`\n  ♠ ♥ ♣ ♦  Blackjack server running on http://localhost:${PORT}\n`);
});
