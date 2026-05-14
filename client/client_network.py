"""
=============================================================================
client_network.py  —  ChatClient  (deep-fixed)
=============================================================================
HANDSHAKE (must match server.py exactly):
  1. Connect TCP.
  2. Read ONE plain JSON frame  →  {"action": "hello", "key": "<b64 fernet key>"}
  3. Build EncryptionManager from that key.
  4. All subsequent frames (send AND recv) are Fernet-encrypted.
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

from server.protocol import Protocol
from server.encryption import EncryptionManager

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9001
MAX_RECONNECT_DELAY = 30


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ChatClient:
    """Non-blocking TCP chat client with auto-reconnect."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.enc: EncryptionManager | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.current_room: str = "General"
        self._running = False
        self._connected = False
        self._recv_thread: threading.Thread | None = None
        self._callbacks: dict[str, list] = {}
        self._reconnect_enabled = True
        self._send_lock = threading.Lock()

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """
        Connect to server and perform the hello handshake.
        Returns True on success.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)

            # ── Step 2: read the plain hello frame ───────────────────────────
            hello = self._recv_plain()
            if hello is None or hello.get("action") != "hello":
                logger.error("Did not receive hello frame from server")
                self.socket.close()
                return False

            # ── Step 3: set up encryption from the shared key ─────────────
            self.enc = EncryptionManager.from_b64(hello["key"])

            self._connected = True
            self._running = True

            self._recv_thread = threading.Thread(
                target=self._receive_loop, daemon=True, name="RecvThread"
            )
            self._recv_thread.start()
            logger.info(f"Connected to {self.host}:{self.port}")
            return True

        except Exception as exc:
            logger.error(f"Connection failed: {exc}")
            self._connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
            return False

    def disconnect(self):
        self._running = False
        self._connected = False
        self._reconnect_enabled = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass

    def _auto_reconnect(self):
        delay = 1
        while self._reconnect_enabled and not self._connected:
            self._fire("system_msg", {
                "action": Protocol.SYSTEM_MSG,
                "message": f"⏳ Reconnecting in {delay}s…",
                "timestamp": _now(),
            })
            time.sleep(delay)
            if self.connect():
                # Re-authenticate
                if self.username and self.password:
                    self.login(self.username, self.password)
                    self._fire("reconnected", {})
                return
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    # ── I/O helpers ───────────────────────────────────────────────────────────

    def _recv_exact(self, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = self.socket.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_plain(self) -> dict | None:
        """Read one PLAIN (unencrypted) framed JSON packet."""
        try:
            raw_len = self._recv_exact(4)
            if raw_len is None:
                return None
            length = int.from_bytes(raw_len, "big")
            body = self._recv_exact(length)
            if body is None:
                return None
            return json.loads(body.decode())
        except Exception as exc:
            logger.error(f"recv_plain error: {exc}")
            return None

    def _recv_encrypted(self) -> dict | None:
        """Read one ENCRYPTED framed packet."""
        try:
            raw_len = self._recv_exact(4)
            if raw_len is None:
                return None
            length = int.from_bytes(raw_len, "big")
            body = self._recv_exact(length)
            if body is None:
                return None
            plain = self.enc.decrypt(body.decode())
            return json.loads(plain)
        except Exception as exc:
            logger.error(f"recv_encrypted error: {exc}")
            return None

    def _send(self, data: dict):
        """Encrypt and send a framed packet."""
        if not self._connected or not self.socket or not self.enc:
            return
        try:
            cipher = self.enc.encrypt(json.dumps(data))
            raw = cipher.encode()
            packet = len(raw).to_bytes(4, "big") + raw
            with self._send_lock:
                self.socket.sendall(packet)
        except Exception as exc:
            logger.error(f"Send error: {exc}")
            self._handle_disconnect()

    def _receive_loop(self):
        while self._running:
            pkt = self._recv_encrypted()
            if pkt is None:
                break
            self._fire(pkt.get("action", ""), pkt)
        self._handle_disconnect()

    def _handle_disconnect(self):
        if not self._connected:
            return
        self._connected = False
        self._fire("disconnected", {})
        if self._reconnect_enabled:
            threading.Thread(target=self._auto_reconnect, daemon=True).start()

    # ── Callback system ───────────────────────────────────────────────────────

    def on(self, action: str, callback):
        self._callbacks.setdefault(action, []).append(callback)

    def _fire(self, action: str, pkt: dict):
        for cb in self._callbacks.get(action, []):
            try:
                cb(pkt)
            except Exception as exc:
                logger.error(f"Callback error '{action}': {exc}")

    # ── High-level API ────────────────────────────────────────────────────────

    def register(self, username: str, password: str):
        self._send({"action": Protocol.REGISTER,
                    "username": username, "password": password})

    def login(self, username: str, password: str):
        self.username = username
        self.password = password
        self._send({"action": Protocol.LOGIN,
                    "username": username, "password": password})

    def send_message(self, text: str, room: str | None = None):
        self._send({"action": Protocol.SEND_MSG,
                    "text": text, "room": room or self.current_room})

    def send_private(self, to: str, text: str):
        self._send({"action": Protocol.PRIVATE_MSG, "to": to, "text": text})

    def create_room(self, name: str):
        self._send({"action": Protocol.CREATE_ROOM, "room": name})

    def join_room(self, name: str):
        self.current_room = name
        self._send({"action": Protocol.JOIN_ROOM, "room": name})

    def leave_room(self, name: str):
        self._send({"action": Protocol.LEAVE_ROOM, "room": name})

    def list_rooms(self):
        self._send({"action": Protocol.LIST_ROOMS})

    def list_users(self):
        self._send({"action": Protocol.LIST_USERS})

    def request_history(self, room: str | None = None, limit: int = 50):
        self._send({"action": Protocol.HISTORY,
                    "room": room or self.current_room, "limit": limit})

    def search(self, query: str, room: str | None = None):
        self._send({"action": Protocol.SEARCH,
                    "query": query, "room": room or self.current_room})

    def send_typing_start(self):
        self._send({"action": Protocol.TYPING_START, "room": self.current_room})

    def send_typing_stop(self):
        self._send({"action": Protocol.TYPING_STOP, "room": self.current_room})

    def send_read_receipt(self, msg_id: int):
        self._send({"action": Protocol.READ_RECEIPT, "msg_id": msg_id})

    def upload_file(self, filepath: str):
        if not os.path.isfile(filepath):
            return
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        self._send({"action": Protocol.FILE_UPLOAD,
                    "filename": filename, "room": self.current_room, "data": data})
