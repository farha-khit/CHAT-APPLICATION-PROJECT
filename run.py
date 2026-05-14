import sys
import os

# Add the current directory to sys.path so sub-packages can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import sys
import os

# Add the current directory to sys.path so sub-packages can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("========================================")
    print("        NEXUSCHAT CHAT LAUNCHER         ")
    print("========================================")
    print("1. Host a Chat Server")
    print("2. Join as a Client (GUI)")
    print("3. Start Both (Local Testing)")
    print("----------------------------------------")
    
    try:
        choice = input("Enter choice (1/2/3): ").strip()
        
        if choice == "1":
            from server.server import ChatServer
            # Listen on all interfaces so friends can connect
            server = ChatServer(host="0.0.0.0", port=9001)
            server.start()
            
        elif choice == "2":
            import customtkinter as ctk
            from client.gui import ChatAppGUI
            root = ctk.CTk()
            app = ChatAppGUI(root)
            root.mainloop()
            
        elif choice == "3":
            import threading
            import time
            from server.server import ChatServer
            import customtkinter as ctk
            from client.gui import ChatAppGUI
            
            def start_server():
                srv = ChatServer(host="0.0.0.0", port=9001)
                srv.start()
                
            threading.Thread(target=start_server, daemon=True).start()
            time.sleep(0.5) # Give server a moment to bind
            
            root = ctk.CTk()
            app = ChatAppGUI(root)
            root.mainloop()
            
        else:
            print("Invalid choice.")
    except KeyboardInterrupt:
        print("\nExiting...")
