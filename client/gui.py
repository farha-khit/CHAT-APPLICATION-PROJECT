"""
=============================================================================
gui.py  —  CustomTkinter Chat GUI  (deep-fixed)
=============================================================================
• Auto-connects to server on launch (no manual connect step needed)
• Handles hello handshake transparently via ChatClient
• Full dark theme using CustomTkinter
• Rooms, DMs, typing indicator, file sharing, search
=============================================================================
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os
import sys
from datetime import datetime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from client.client_network import ChatClient
from server.protocol import Protocol

# ─── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Palette ──────────────────────────────────────────────────────────────────
C_BG       = "#1a1b26"
C_SIDEBAR  = "#16161e"
C_ACCENT   = "#7aa2f7"
C_TEXT     = "#c0caf5"
C_ME       = "#3d59a1"
C_OTHER    = "#24283b"
C_SYS      = "#e0af68"
C_TYPING   = "#bb9af7"
C_ONLINE   = "#9ece6a"


class ChatAppGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("NexusChat")
        self.root.geometry("1100x720")
        self.root.configure(fg_color=C_BG)

        self.username: str | None = None
        self.current_room = "General"

        # ── Network ──────────────────────────────────────────────────────────
        self.client = ChatClient()
        self._register_callbacks()

        # ── Show login first ──────────────────────────────────────────────────
        self._show_login()

    # =========================================================================
    # Network bootstrap
    # =========================================================================

    def _bg_connect(self):
        """Called from a background thread — connect to server silently."""
        host = self._ip_entry.get().strip() or "127.0.0.1"
        self.client.host = host
        if self.client.connect():
            self._safe(lambda: self._status_lbl.configure(text=f"Connected to {host} ✅", text_color=C_ONLINE))
        else:
            self._safe(lambda: self._status_lbl.configure(text="Connection failed ❌", text_color="#f7768e"))
            self._safe(lambda: messagebox.showerror(
                "Connection Error",
                f"Could not connect to server at {host}.\n"
                "Make sure the server is running on port 9001"
            ))

    def _register_callbacks(self):
        c = self.client
        c.on(Protocol.REGISTER_OK,  self._cb_register_ok)
        c.on(Protocol.LOGIN_OK,     self._cb_login_ok)
        c.on(Protocol.ERROR,        self._cb_error)
        c.on(Protocol.NEW_MSG,      self._cb_new_msg)
        c.on(Protocol.PRIVATE_MSG,  self._cb_private_msg)
        c.on(Protocol.SYSTEM_MSG,   self._cb_system_msg)
        c.on("users_online",        self._cb_users_online)
        c.on(Protocol.ROOMS_LIST,   self._cb_rooms_list)
        c.on(Protocol.ROOMS_UPDATED,lambda _: self.client.list_rooms())
        c.on(Protocol.HISTORY,      self._cb_history)
        c.on(Protocol.TYPING_START, self._cb_typing_start)
        c.on(Protocol.TYPING_STOP,  self._cb_typing_stop)
        c.on(Protocol.SEARCH_RESULTS, self._cb_search_results)
        c.on(Protocol.FILE_SHARED,  self._cb_file_shared)
        c.on("disconnected",        lambda _: self._safe(
            lambda: self._system("⚠️ Disconnected — reconnecting…")))
        c.on("reconnected",         lambda _: self._safe(
            lambda: self._system("✅ Reconnected!")))

    # =========================================================================
    # Login screen
    # =========================================================================

    def _show_login(self):
        self._clear()
        frame = ctk.CTkFrame(self.root, width=420, height=520, corner_radius=20)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="💬 NexusChat",
                     font=("Segoe UI", 26, "bold"),
                     text_color=C_ACCENT).pack(pady=(40, 10))
        ctk.CTkLabel(frame, text="Real-time encrypted messaging",
                     font=("Segoe UI", 11), text_color="#565f89").pack(pady=(0, 20))

        self._ip_entry = ctk.CTkEntry(frame, placeholder_text="Server IP (e.g. 127.0.0.1)",
                                      width=280, height=45,
                                      font=("Segoe UI", 13))
        self._ip_entry.insert(0, "127.0.0.1")
        self._ip_entry.pack(pady=8)

        self._user_entry = ctk.CTkEntry(frame, placeholder_text="Username",
                                        width=280, height=45,
                                        font=("Segoe UI", 13))
        self._user_entry.pack(pady=8)

        self._pass_entry = ctk.CTkEntry(frame, placeholder_text="Password",
                                        show="*", width=280, height=45,
                                        font=("Segoe UI", 13))
        self._pass_entry.pack(pady=8)
        self._pass_entry.bind("<Return>", lambda _: self._do_login())

        ctk.CTkButton(frame, text="Login", width=280, height=45,
                      font=("Segoe UI", 14, "bold"),
                      command=self._do_login).pack(pady=(20, 8))

        ctk.CTkButton(frame, text="Create Account", width=280, height=45,
                      fg_color="transparent", border_width=2,
                      font=("Segoe UI", 13),
                      command=self._do_register).pack(pady=4)

        self._status_lbl = ctk.CTkLabel(frame, text="Connecting to server…",
                                        font=("Segoe UI", 10),
                                        text_color="#565f89")
        self._status_lbl.pack(pady=(20, 0))

    def _do_login(self):
        u = self._user_entry.get().strip()
        p = self._pass_entry.get()
        if not u or not p:
            return
        
        # If not connected yet, try to connect using the specified IP
        if not self.client._connected:
            self._status_lbl.configure(text="Connecting...", text_color="#565f89")
            self._bg_connect()
            
        if not self.client._connected:
            return
            
        self.client.login(u, p)

    def _do_register(self):
        u = self._user_entry.get().strip()
        p = self._pass_entry.get()
        if not u or not p:
            return
            
        # If not connected yet, try to connect using the specified IP
        if not self.client._connected:
            self._status_lbl.configure(text="Connecting...", text_color="#565f89")
            self._bg_connect()
            
        if not self.client._connected:
            return
            
        self.client.register(u, p)

    # =========================================================================
    # Main chat UI
    # =========================================================================

    def _show_main(self):
        self._clear()
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(self.root, width=260, fg_color=C_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="NEXUSCHAT",
                     font=("Segoe UI", 18, "bold"),
                     text_color=C_ACCENT).pack(pady=(24, 4))
        ctk.CTkLabel(sidebar, text=f"● {self.username}",
                     font=("Segoe UI", 12, "bold"),
                     text_color=C_ONLINE).pack(pady=(0, 16))

        ctk.CTkLabel(sidebar, text="ROOMS", font=("Segoe UI", 10, "bold"),
                     text_color="#565f89").pack(anchor="w", padx=16)

        self._room_lb = tk.Listbox(sidebar, bg=C_SIDEBAR, fg=C_TEXT,
                                   selectbackground=C_ME, activestyle="none",
                                   borderwidth=0, highlightthickness=0,
                                   font=("Segoe UI", 11))
        self._room_lb.pack(fill="x", padx=8, pady=4)
        self._room_lb.bind("<<ListboxSelect>>", self._on_room_select)

        ctk.CTkButton(sidebar, text="＋ New Room", height=36,
                      font=("Segoe UI", 12),
                      command=self._create_room_dlg).pack(padx=16, pady=8, fill="x")

        ctk.CTkLabel(sidebar, text="ONLINE", font=("Segoe UI", 10, "bold"),
                     text_color="#565f89").pack(anchor="w", padx=16, pady=(8, 0))

        self._user_lb = tk.Listbox(sidebar, bg=C_SIDEBAR, fg=C_TEXT,
                                   borderwidth=0, highlightthickness=0,
                                   font=("Segoe UI", 11))
        self._user_lb.pack(fill="both", expand=True, padx=8, pady=4)

        # Voice / Video placeholders
        btn_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=8, pady=12)
        ctk.CTkButton(btn_row, text="📞 Voice", width=110, height=32,
                      fg_color="#1c6e3d", hover_color="#1a5c34",
                      font=("Segoe UI", 11),
                      command=lambda: messagebox.showinfo(
                          "Coming Soon", "Voice calling — future feature!")).pack(
                          side="left", padx=4)
        ctk.CTkButton(btn_row, text="🎥 Video", width=110, height=32,
                      fg_color="#6b3a1f", hover_color="#5a301a",
                      font=("Segoe UI", 11),
                      command=lambda: messagebox.showinfo(
                          "Coming Soon", "Video calling — future feature!")).pack(
                          side="left", padx=4)

        # ── Chat pane ────────────────────────────────────────────────────────
        chat = ctk.CTkFrame(self.root, fg_color=C_BG, corner_radius=0)
        chat.grid(row=0, column=1, sticky="nsew")
        chat.grid_columnconfigure(0, weight=1)
        chat.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(chat, height=64, fg_color=C_SIDEBAR, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)

        self._room_lbl = ctk.CTkLabel(hdr, text=f"# {self.current_room}",
                                      font=("Segoe UI", 16, "bold"),
                                      text_color=C_TEXT)
        self._room_lbl.pack(side="left", padx=20)

        self._search_entry = ctk.CTkEntry(hdr, placeholder_text="🔍  Search…",
                                          width=200, height=34)
        self._search_entry.pack(side="right", padx=16, pady=15)
        self._search_entry.bind("<Return>", lambda _: self._do_search())

        # Messages text widget
        self._txt = tk.Text(chat, bg=C_BG, fg=C_TEXT,
                            font=("Segoe UI", 11), borderwidth=0,
                            padx=16, pady=12, state="disabled",
                            wrap="word", cursor="arrow")
        self._txt.grid(row=1, column=0, sticky="nsew")

        # Scrollbar
        sb = ctk.CTkScrollbar(chat, command=self._txt.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self._txt.configure(yscrollcommand=sb.set)

        # Typing indicator
        self._typing_lbl = ctk.CTkLabel(chat, text="",
                                         font=("Segoe UI", 10, "italic"),
                                         text_color=C_TYPING, height=18)
        self._typing_lbl.grid(row=2, column=0, sticky="w", padx=20)

        # Input row
        inp = ctk.CTkFrame(chat, fg_color="transparent")
        inp.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 16))

        self._msg_entry = ctk.CTkEntry(inp, placeholder_text="Message…  (/w user msg for DM)",
                                       height=46, font=("Segoe UI", 12))
        self._msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._msg_entry.bind("<Return>", lambda _: self._send_msg())
        self._msg_entry.bind("<KeyPress>", lambda _: self._on_keypress())

        ctk.CTkButton(inp, text="📎", width=46, height=46,
                      fg_color=C_OTHER, hover_color="#313244",
                      command=self._upload_file).pack(side="left", padx=(0, 8))

        ctk.CTkButton(inp, text="Send ➤", width=100, height=46,
                      font=("Segoe UI", 13, "bold"),
                      command=self._send_msg).pack(side="left")

        # Load initial data
        self.client.list_rooms()
        self.client.request_history()

    # =========================================================================
    # Actions
    # =========================================================================

    def _send_msg(self):
        text = self._msg_entry.get().strip()
        if not text:
            return
        if text.startswith("/w "):
            parts = text.split(" ", 2)
            if len(parts) == 3:
                self.client.send_private(parts[1], parts[2])
            else:
                self._system("Usage: /w <username> <message>")
        else:
            self.client.send_message(text)
        self._msg_entry.delete(0, "end")
        self.client.send_typing_stop()

    def _on_keypress(self):
        self.client.send_typing_start()
        if hasattr(self, "_typ_timer"):
            self.root.after_cancel(self._typ_timer)
        self._typ_timer = self.root.after(2000, self.client.send_typing_stop)

    def _upload_file(self):
        path = filedialog.askopenfilename()
        if path:
            threading.Thread(target=self.client.upload_file,
                             args=(path,), daemon=True).start()

    def _create_room_dlg(self):
        dlg = ctk.CTkInputDialog(text="Enter new room name:", title="Create Room")
        name = dlg.get_input()
        if name and name.strip():
            self.client.create_room(name.strip())

    def _on_room_select(self, _event):
        sel = self._room_lb.curselection()
        if not sel:
            return
        room = self._room_lb.get(sel[0])
        if room != self.current_room:
            self.current_room = room
            self._room_lbl.configure(text=f"# {room}")
            self.client.join_room(room)
            self._clear_chat()
            self.client.request_history(room)

    def _do_search(self):
        q = self._search_entry.get().strip()
        if q:
            self.client.search(q)

    # =========================================================================
    # Message rendering
    # =========================================================================

    def _append(self, sender: str, text: str, ts: str):
        self._txt.configure(state="normal")
        time_part = ts.split(" ")[1] if " " in ts else ts

        # Tags (defined lazily, no error if re-defined)
        self._txt.tag_configure("time",  foreground="#565f89", font=("Segoe UI", 9))
        self._txt.tag_configure("me",    foreground=C_ACCENT,  font=("Segoe UI", 11, "bold"))
        self._txt.tag_configure("other", foreground=C_TYPING,  font=("Segoe UI", 11, "bold"))
        self._txt.tag_configure("body",  foreground=C_TEXT)

        tag = "me" if sender == self.username else "other"
        self._txt.insert("end", f"  {time_part}  ", "time")
        self._txt.insert("end", f"{sender}  ", tag)
        self._txt.insert("end", f"{text}\n", "body")
        self._txt.see("end")
        self._txt.configure(state="disabled")

    def _system(self, text: str):
        """Insert a system notification line — safe to call from any thread."""
        def _do():
            if not hasattr(self, "_txt"):
                return
            self._txt.configure(state="normal")
            self._txt.tag_configure("sys", foreground=C_SYS,
                                    font=("Segoe UI", 10, "italic"))
            self._txt.insert("end", f"  ✦ {text}\n", "sys")
            self._txt.see("end")
            self._txt.configure(state="disabled")
        self._safe(_do)

    def _clear_chat(self):
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")

    # =========================================================================
    # Callbacks (called from network thread → must schedule on main thread)
    # =========================================================================

    def _cb_register_ok(self, pkt):
        self._safe(lambda: messagebox.showinfo("Registered",
                                               pkt.get("message", "Account created!")))

    def _cb_login_ok(self, pkt):
        self.username = pkt["username"]
        self.client.current_room = "General"
        self.current_room = "General"
        self._safe(self._show_main)

    def _cb_error(self, pkt):
        msg = pkt.get("message", "Server error")
        self._safe(lambda: messagebox.showerror("Error", msg))

    def _cb_new_msg(self, pkt):
        if pkt.get("room") == self.current_room:
            self._safe(lambda: self._append(pkt["username"], pkt["text"], pkt["timestamp"]))

    def _cb_private_msg(self, pkt):
        sender = pkt["from"]
        receiver = pkt["to"]
        label = f"DM ▸ {receiver}" if sender == self.username else f"DM ◂ {sender}"
        self._safe(lambda: self._append(label, pkt["text"], pkt["timestamp"]))

    def _cb_system_msg(self, pkt):
        room = pkt.get("room")
        if not room or room == self.current_room:
            self._system(pkt["message"])

    def _cb_history(self, pkt):
        if pkt.get("room") != self.current_room:
            return
        def _do():
            self._clear_chat()
            for m in pkt["messages"]:
                self._append(m["username"], m["text"], m["timestamp"])
        self._safe(_do)

    def _cb_users_online(self, pkt):
        users = pkt.get("users", [])
        def _do():
            if not hasattr(self, "_user_lb"):
                return
            self._user_lb.delete(0, "end")
            for u in users:
                self._user_lb.insert("end", f"● {u['username']}  ({u['room']})")
        self._safe(_do)

    def _cb_rooms_list(self, pkt):
        rooms = [r["name"] for r in pkt.get("rooms", [])]
        def _do():
            if not hasattr(self, "_room_lb"):
                return
            self._room_lb.delete(0, "end")
            for r in rooms:
                self._room_lb.insert("end", r)
        self._safe(_do)

    def _cb_typing_start(self, pkt):
        if pkt.get("room") == self.current_room:
            user = pkt["username"]
            self._safe(lambda: self._typing_lbl.configure(
                text=f"{user} is typing…"))

    def _cb_typing_stop(self, _pkt):
        self._safe(lambda: self._typing_lbl.configure(text=""))

    def _cb_search_results(self, pkt):
        results = pkt.get("results", [])
        def _do():
            self._clear_chat()
            self._system(f"Search results: {len(results)} found")
            for m in results:
                self._append(m["username"], m["text"], m["timestamp"])
        self._safe(_do)

    def _cb_file_shared(self, pkt):
        if pkt.get("room") == self.current_room:
            self._safe(lambda: self._append(
                pkt["username"],
                f"📁 Shared: {pkt['original_name']}",
                pkt["timestamp"]))

    # =========================================================================
    # Utility
    # =========================================================================

    def _safe(self, fn):
        """Schedule *fn* on the Tkinter main thread."""
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()


# ─── Standalone entry ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = ctk.CTk()
    ChatAppGUI(root)
    root.mainloop()
