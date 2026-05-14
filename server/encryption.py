"""
=============================================================================
EncryptionManager — Fernet symmetric encryption wrapper
=============================================================================
Every message frame sent over the network is encrypted with the same
symmetric key so that packet sniffers see only ciphertext.

Key lifecycle
─────────────
• The key is generated once when the server starts and kept in memory.
• On login-ok the server sends the base-64 encoded key to the client so
  both sides share the same Fernet key for the lifetime of the session.
• For a production system you would use TLS or a proper key-exchange
  protocol; Fernet here serves as an educational demonstration.
=============================================================================
"""

import base64
import os
from cryptography.fernet import Fernet


class EncryptionManager:
    """Wrap Fernet so the rest of the code never touches raw crypto primitives."""

    def __init__(self, key: bytes | None = None):
        """
        Parameters
        ----------
        key : bytes | None
            A valid 32-byte URL-safe base-64 encoded Fernet key.
            If *None* a new key is generated automatically.
        """
        if key is None:
            self._key = Fernet.generate_key()
        else:
            self._key = key
        self._fernet = Fernet(self._key)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return a base-64 URL-safe ciphertext string."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt *ciphertext* and return the original plaintext string."""
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def get_key_b64(self) -> str:
        """Return the raw Fernet key as a base-64 string (for sharing with clients)."""
        return self._key.decode("utf-8")

    @staticmethod
    def from_b64(key_b64: str) -> "EncryptionManager":
        """Reconstruct an EncryptionManager from a base-64 key received from the server."""
        return EncryptionManager(key=key_b64.encode("utf-8"))
