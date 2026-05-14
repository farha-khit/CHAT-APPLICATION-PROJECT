"""
=============================================================================
RoomManager — In-memory chat-room tracking
=============================================================================
Keeps track of which rooms exist and which users are in each room.
The "General" room is created automatically and cannot be deleted.
=============================================================================
"""

import threading


class RoomManager:
    """Thread-safe room membership tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        # room_name → set of usernames
        self._rooms: dict[str, set[str]] = {"General": set()}

    # ------------------------------------------------------------------
    # Room lifecycle
    # ------------------------------------------------------------------

    def create_room(self, name: str, creator: str) -> tuple[bool, str]:
        """Create a new room. Returns (success, message)."""
        with self._lock:
            if name in self._rooms:
                return False, f"Room '{name}' already exists."
            self._rooms[name] = set()
            return True, f"Room '{name}' created by {creator}."

    def room_exists(self, name: str) -> bool:
        with self._lock:
            return name in self._rooms

    def list_rooms(self) -> list[dict]:
        """Return a list of dicts with room name and member count."""
        with self._lock:
            return [
                {"name": r, "members": len(m)}
                for r, m in self._rooms.items()
            ]

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def join_room(self, room: str, username: str):
        with self._lock:
            if room not in self._rooms:
                self._rooms[room] = set()
            self._rooms[room].add(username)

    def leave_room(self, room: str, username: str):
        with self._lock:
            if room in self._rooms:
                self._rooms[room].discard(username)

    def leave_all(self, username: str):
        """Remove *username* from every room (called on disconnect)."""
        with self._lock:
            for members in self._rooms.values():
                members.discard(username)

    def get_members(self, room: str) -> set[str]:
        with self._lock:
            return set(self._rooms.get(room, set()))
