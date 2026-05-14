"""
=============================================================================
Protocol — Shared action-string constants
=============================================================================
Both the server and the client import this module so that every packet's
"action" field is always a well-known string constant rather than a magic
literal scattered throughout the codebase.
=============================================================================
"""


class Protocol:
    # ── Authentication ────────────────────────────────────────────────
    REGISTER       = "register"
    REGISTER_OK    = "register_ok"
    LOGIN          = "login"
    LOGIN_OK       = "login_ok"
    LOGOUT         = "logout"

    # ── Messaging ─────────────────────────────────────────────────────
    SEND_MSG       = "send_msg"
    NEW_MSG        = "new_msg"
    PRIVATE_MSG    = "private_msg"
    SYSTEM_MSG     = "system_msg"

    # ── Rooms ─────────────────────────────────────────────────────────
    CREATE_ROOM    = "create_room"
    ROOM_CREATED   = "room_created"
    JOIN_ROOM      = "join_room"
    ROOM_JOINED    = "room_joined"
    LEAVE_ROOM     = "leave_room"
    ROOM_LEFT      = "room_left"
    LIST_ROOMS     = "list_rooms"
    ROOMS_LIST     = "rooms_list"
    ROOMS_UPDATED  = "rooms_updated"

    # ── Users ─────────────────────────────────────────────────────────
    LIST_USERS     = "list_users"
    USERS_LIST     = "users_list"
    USERS_ONLINE   = "users_online"

    # ── Typing indicators ─────────────────────────────────────────────
    TYPING_START   = "typing_start"
    TYPING_STOP    = "typing_stop"

    # ── Files ─────────────────────────────────────────────────────────
    FILE_UPLOAD    = "file_upload"
    FILE_SHARED    = "file_shared"

    # ── History / search ──────────────────────────────────────────────
    HISTORY        = "history"
    SEARCH         = "search"
    SEARCH_RESULTS = "search_results"

    # ── Read receipts ─────────────────────────────────────────────────
    READ_RECEIPT   = "read_receipt"

    # ── Errors ────────────────────────────────────────────────────────
    ERROR          = "error"
