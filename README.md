# 🚀 NexusChat Real-Time Chat Application

A professional-grade, multi-client chat application built with Python using TCP sockets, threading, and a modern GUI.

## ✨ Features

- **Real-Time Messaging:** Instant message broadcasting using TCP sockets.
- **Modern UI:** Dark-themed interface built with Tkinter (customizable).
- **Secure Authentication:** User registration and login with bcrypt password hashing.
- **Private Messaging:** Secure 1-on-1 chats using `/w <username> <message>`.
- **Chat Rooms:** Create and join multiple rooms (General is default).
- **End-to-End Encryption:** Messages are encrypted using Fernet (cryptography library).
- **File & Image Sharing:** Send files locally via the chat interface.
- **Persistent History:** All messages and rooms stored in a SQLite database.
- **Online Status:** Real-time online user tracking.
- **Notifications:** Desktop popups and system alerts.
- **Auto-Reconnect:** Client automatically attempts to reconnect if the server drops.

## 📁 Project Structure

```text
/chat_app
  /client
    gui.py             # Main application window
    client_network.py  # Network & Protocol logic
  /server
    server.py          # Multi-threaded TCP server
    protocol.py        # Shared communication constants
    encryption.py      # Fernet encryption wrapper
    room_manager.py    # Room & Membership logic
  /database
    db_manager.py      # SQLite & bcrypt logic
  /uploads             # Locally saved shared files
  requirements.txt     # Dependency list
```

## 🛠️ Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
python -m server.server
```

### 4. Run the Client
Open multiple terminals to simulate different users:
```bash
python -m client.gui
```

## 🔐 Security Features
- **Hashing:** No plain-text passwords. We use `bcrypt` with salt.
- **Encryption:** Every packet sent over the network is encrypted with a unique session key shared during login.
- **Validation:** Server-side checks for existing users and room names.

## 🌐 Deployment

### Local Network
1. Find your local IP address (`ipconfig` on Windows, `ifconfig` on Linux).
2. Change `DEFAULT_HOST` in `client_network.py` to your server's IP.
3. Ensure the firewall allows traffic on port `9001`.

### Online (Production)
1. **VPS:** Host the `server/` and `database/` on a VPS (like AWS, DigitalOcean).
2. **Static IP:** Use the VPS's public IP in the client code.
3. **SSL/TLS:** For production, it is recommended to wrap the socket in an SSL context using Python's `ssl` module.

## 📝 Usage Tips
- **Whisper:** Type `/w username message` in any room to send a private message.
- **Rooms:** Click on room names in the sidebar to switch channels.
- **Files:** Click the 📎 button to select and send files to the current room.

---
Built with ❤️ by NexusChat.
