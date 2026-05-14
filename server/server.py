"""
=============================================================================
server.py  —  Multi-threaded TCP Chat Server  (deep-fixed)
=============================================================================
HANDSHAKE PROTOCOL
──────────────────
1. Client connects.
2. Server immediately sends a plaintext JSON "hello" frame containing the
   session Fernet key.
3. From that point on EVERY frame (client→server and server→client) is
   encrypted with that key.

Frame format: 4-byte big-endian length  +  UTF-8 ciphertext (or plaintext
for the hello frame only).
=============================================================================
"""

import socket
import threading
import json
import os
import sys
import time
import base64
import logging
from datetime import datetime

# ── Path fix ──────────────────────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from database.db_manager import DatabaseManager
from server.room_manager import RoomManager
from server.encryption import EncryptionManager
from server.protocol import Protocol

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(APP_DIR, "server.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 9001
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
class ClientHandler(threading.Thread):
    """One daemon thread per connected client."""

    def __init__(self, conn: socket.socket, addr, server: "ChatServer"):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.server = server
        self.username: str | None = None
        self.current_room: str = "General"
        self.authenticated: bool = False
        self._running = True
        self._send_lock = threading.Lock()
        # Each client gets the server's shared Fernet key
        self.enc = server.encryption

    # ── Thread entry ─────────────────────────────────────────────────────────
    def run(self):
        logger.info(f"New connection: {self.addr}")
        try:
            # Step 1: send the Fernet key as PLAIN JSON so the client can
            #         start decrypting subsequent frames.
            self._send_plain({"action": "hello", "key": self.enc.get_key_b64()})

            while self._running:
                pkt = self._recv()
                if pkt is None:
                    break
                self._dispatch(pkt)
        except Exception as exc:
            logger.error(f"Handler error {self.addr}: {exc}", exc_info=True)
        finally:
            self._disconnect()

    # ── Low-level I/O ─────────────────────────────────────────────────────────
    def _send_plain(self, data: dict):
        """Send a frame as plain JSON (used only for the hello handshake)."""
        try:
            raw = json.dumps(data).encode()
            packet = len(raw).to_bytes(4, "big") + raw
            with self._send_lock:
                self.conn.sendall(packet)
        except Exception as exc:
            logger.warning(f"send_plain error: {exc}")

    def _send(self, data: dict):
        """Encrypt then send a framed JSON packet."""
        try:
            cipher = self.enc.encrypt(json.dumps(data))
            raw = cipher.encode()
            packet = len(raw).to_bytes(4, "big") + raw
            with self._send_lock:
                self.conn.sendall(packet)
        except Exception as exc:
            logger.warning(f"send error to {self.username or self.addr}: {exc}")
            self._running = False

    def _recv_exact(self, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv(self) -> dict | None:
        try:
            raw_len = self._recv_exact(4)
            if raw_len is None:
                return None
            length = int.from_bytes(raw_len, "big")
            if length > MAX_FILE_SIZE + 4096:
                return None
            body = self._recv_exact(length)
            if body is None:
                return None
            plain = self.enc.decrypt(body.decode())
            return json.loads(plain)
        except (ConnectionResetError, BrokenPipeError, OSError):
            return None
        except Exception as exc:
            logger.error(f"recv error {self.addr}: {exc}")
            return None

    # ── Dispatcher ────────────────────────────────────────────────────────────
    def _dispatch(self, pkt: dict):
        action = pkt.get("action", "")
        table = {
            Protocol.REGISTER:     self._on_register,
            Protocol.LOGIN:        self._on_login,
            Protocol.SEND_MSG:     self._on_message,
            Protocol.PRIVATE_MSG:  self._on_private_message,
            Protocol.CREATE_ROOM:  self._on_create_room,
            Protocol.JOIN_ROOM:    self._on_join_room,
            Protocol.LEAVE_ROOM:   self._on_leave_room,
            Protocol.LIST_ROOMS:   self._on_list_rooms,
            Protocol.LIST_USERS:   self._on_list_users,
            Protocol.TYPING_START: self._on_typing_start,
            Protocol.TYPING_STOP:  self._on_typing_stop,
            Protocol.FILE_UPLOAD:  self._on_file_upload,
            Protocol.HISTORY:      self._on_history,
            Protocol.SEARCH:       self._on_search,
            Protocol.READ_RECEIPT: self._on_read_receipt,
        }
        fn = table.get(action)
        if fn:
            fn(pkt)
        else:
            logger.debug(f"Unknown action '{action}' from {self.addr}")

    # ── Auth ──────────────────────────────────────────────────────────────────
    def _on_register(self, pkt):
        username = pkt.get("username", "").strip()
        password = pkt.get("password", "")
        ok, msg = self.server.db.register_user(username, password)
        if ok:
            self._send({"action": Protocol.REGISTER_OK, "message": msg})
        else:
            self._send({"action": Protocol.ERROR, "message": msg})

    def _on_login(self, pkt):
        username = pkt.get("username", "").strip()
        password = pkt.get("password", "")
        if username in self.server.clients:
            self._send({"action": Protocol.ERROR, "message": "User already logged in."})
            return
        ok, msg = self.server.db.verify_user(username, password)
        if not ok:
            self._send({"action": Protocol.ERROR, "message": msg})
            return
        self.username = username
        self.authenticated = True
        with self.server.lock:
            self.server.clients[username] = self
        self.server.room_manager.join_room("General", username)
        self._send({"action": Protocol.LOGIN_OK, "username": username, "room": "General",
                    "message": f"Welcome, {username}!"})
        self.server.broadcast_room("General", {
            "action": Protocol.SYSTEM_MSG,
            "message": f"🟢 {username} joined the chat",
            "timestamp": _now(), "room": "General",
        }, exclude=username)
        self.server.broadcast_online_users()
        logger.info(f"'{username}' logged in from {self.addr}")

    # ── Messaging ─────────────────────────────────────────────────────────────
    def _on_message(self, pkt):
        if not self.authenticated:
            return
        text = pkt.get("text", "").strip()
        room = pkt.get("room", self.current_room)
        if not text:
            return
        ts = _now()
        msg_id = self.server.db.save_message(self.username, room, text, ts)
        self.server.broadcast_room(room, {
            "action": Protocol.NEW_MSG, "id": msg_id,
            "username": self.username, "text": text,
            "room": room, "timestamp": ts,
        })

    def _on_private_message(self, pkt):
        if not self.authenticated:
            return
        target = pkt.get("to", "")
        text = pkt.get("text", "").strip()
        if not text or not target:
            return
        ts = _now()
        msg_id = self.server.db.save_message(self.username, f"__dm__{target}", text, ts)
        payload = {"action": Protocol.PRIVATE_MSG, "id": msg_id,
                   "from": self.username, "to": target, "text": text, "timestamp": ts}
        if target in self.server.clients:
            self.server.clients[target]._send(payload)
        self._send(payload)

    # ── Rooms ─────────────────────────────────────────────────────────────────
    def _on_create_room(self, pkt):
        if not self.authenticated:
            return
        name = pkt.get("room", "").strip()
        ok, msg = self.server.room_manager.create_room(name, self.username)
        if ok:
            self.server.db.ensure_room(name)
            self._send({"action": Protocol.ROOM_CREATED, "room": name, "message": msg})
            self.server.broadcast_all({
                "action": Protocol.ROOMS_UPDATED,
                "rooms": self.server.room_manager.list_rooms(),
            })
        else:
            self._send({"action": Protocol.ERROR, "message": msg})

    def _on_join_room(self, pkt):
        if not self.authenticated:
            return
        name = pkt.get("room", "").strip()
        if not self.server.room_manager.room_exists(name):
            self._send({"action": Protocol.ERROR, "message": f"Room '{name}' does not exist."})
            return
        old = self.current_room
        self.server.room_manager.leave_room(old, self.username)
        self.server.broadcast_room(old, {"action": Protocol.SYSTEM_MSG,
            "message": f"⬅️ {self.username} left {old}", "timestamp": _now(), "room": old},
            exclude=self.username)
        self.current_room = name
        self.server.room_manager.join_room(name, self.username)
        self._send({"action": Protocol.ROOM_JOINED, "room": name})
        self.server.broadcast_room(name, {"action": Protocol.SYSTEM_MSG,
            "message": f"➡️ {self.username} joined {name}", "timestamp": _now(), "room": name},
            exclude=self.username)
        self.server.broadcast_online_users()

    def _on_leave_room(self, pkt):
        if not self.authenticated:
            return
        room = pkt.get("room", self.current_room)
        self.server.room_manager.leave_room(room, self.username)
        if self.current_room == room:
            self.current_room = "General"
            self.server.room_manager.join_room("General", self.username)
        self._send({"action": Protocol.ROOM_LEFT, "room": room})
        self.server.broadcast_room(room, {"action": Protocol.SYSTEM_MSG,
            "message": f"⬅️ {self.username} left {room}", "timestamp": _now(), "room": room},
            exclude=self.username)
        self.server.broadcast_online_users()

    def _on_list_rooms(self, _pkt):
        if not self.authenticated:
            return
        self._send({"action": Protocol.ROOMS_LIST, "rooms": self.server.room_manager.list_rooms()})

    def _on_list_users(self, _pkt):
        if not self.authenticated:
            return
        self._send({"action": Protocol.USERS_LIST, "users": list(self.server.clients.keys())})

    # ── Typing ────────────────────────────────────────────────────────────────
    def _on_typing_start(self, pkt):
        if not self.authenticated:
            return
        room = pkt.get("room", self.current_room)
        self.server.broadcast_room(room, {"action": Protocol.TYPING_START,
            "username": self.username, "room": room}, exclude=self.username)

    def _on_typing_stop(self, pkt):
        if not self.authenticated:
            return
        room = pkt.get("room", self.current_room)
        self.server.broadcast_room(room, {"action": Protocol.TYPING_STOP,
            "username": self.username, "room": room}, exclude=self.username)

    # ── File upload ───────────────────────────────────────────────────────────
    def _on_file_upload(self, pkt):
        if not self.authenticated:
            return
        filename = pkt.get("filename", "file")
        room = pkt.get("room", self.current_room)
        file_b64 = pkt.get("data", "")
        if not file_b64:
            return
        try:
            file_bytes = base64.b64decode(file_b64)
            if len(file_bytes) > MAX_FILE_SIZE:
                self._send({"action": Protocol.ERROR, "message": "File too large (max 10 MB)."})
                return
            safe_name = f"{int(time.time())}_{self.username}_{os.path.basename(filename)}"
            with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
                f.write(file_bytes)
            ts = _now()
            msg_id = self.server.db.save_message(self.username, room, f"[FILE:{safe_name}]", ts)
            self.server.broadcast_room(room, {
                "action": Protocol.FILE_SHARED, "id": msg_id,
                "username": self.username, "filename": safe_name,
                "original_name": filename, "room": room, "timestamp": ts, "data": file_b64,
            })
        except Exception as exc:
            logger.error(f"File upload error: {exc}")
            self._send({"action": Protocol.ERROR, "message": "File upload failed."})

    # ── History / search ──────────────────────────────────────────────────────
    def _on_history(self, pkt):
        if not self.authenticated:
            return
        room = pkt.get("room", self.current_room)
        limit = int(pkt.get("limit", 50))
        self._send({"action": Protocol.HISTORY, "room": room,
                    "messages": self.server.db.get_history(room, limit)})

    def _on_search(self, pkt):
        if not self.authenticated:
            return
        query = pkt.get("query", "")
        room = pkt.get("room", self.current_room)
        self._send({"action": Protocol.SEARCH_RESULTS,
                    "results": self.server.db.search_messages(room, query)})

    def _on_read_receipt(self, pkt):
        if not self.authenticated:
            return
        msg_id = pkt.get("msg_id")
        if msg_id:
            self.server.db.mark_read(msg_id, self.username)
            self.server.broadcast_room(self.current_room, {
                "action": Protocol.READ_RECEIPT, "msg_id": msg_id, "reader": self.username,
            }, exclude=self.username)

    # ── Disconnect ────────────────────────────────────────────────────────────
    def _disconnect(self):
        self._running = False
        if self.username:
            with self.server.lock:
                self.server.clients.pop(self.username, None)
            self.server.room_manager.leave_all(self.username)
            self.server.broadcast_room(self.current_room, {
                "action": Protocol.SYSTEM_MSG,
                "message": f"🔴 {self.username} left the chat",
                "timestamp": _now(), "room": self.current_room,
            })
            self.server.broadcast_online_users()
            logger.info(f"'{self.username}' disconnected")
        try:
            self.conn.close()
        except Exception:
            pass


# =============================================================================
class ChatServer:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.clients: dict[str, ClientHandler] = {}
        self.lock = threading.Lock()
        self.db = DatabaseManager()
        self.room_manager = RoomManager()
        self.encryption = EncryptionManager()
        self._sock: socket.socket | None = None

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(100)
        logger.info(f"ChatServer listening on {self.host}:{self.port}")
        try:
            while True:
                conn, addr = self._sock.accept()
                ClientHandler(conn, addr, self).start()
        except KeyboardInterrupt:
            logger.info("Server shutting down …")
        finally:
            if self._sock:
                self._sock.close()

    # ── Broadcast helpers ─────────────────────────────────────────────────────
    def broadcast_room(self, room: str, payload: dict, exclude: str | None = None):
        members = self.room_manager.get_members(room)
        with self.lock:
            for uname, handler in list(self.clients.items()):
                if uname != exclude and uname in members:
                    handler._send(payload)

    def broadcast_all(self, payload: dict, exclude: str | None = None):
        with self.lock:
            for uname, handler in list(self.clients.items()):
                if uname != exclude:
                    handler._send(payload)

    def broadcast_online_users(self):
        with self.lock:
            users = [{"username": u, "room": h.current_room}
                     for u, h in self.clients.items()]
        self.broadcast_all({"action": "users_online", "users": users})


if __name__ == "__main__":
    ChatServer().start()
