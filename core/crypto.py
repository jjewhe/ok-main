import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

class OmegaCrypto:
    def __init__(self, secret: str = "omega_elite_master_secret_2024"):
        self.secret = secret.encode()

    def derive_key(self, salt: bytes):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self.secret)

    def encrypt(self, data: str, key_salt: str) -> str:
        """Encrypts a string payload using AES-256-GCM."""
        key = self.derive_key(key_salt.encode())
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data.encode(), None)
        # Result: nonce + ciphertext (base64)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted_b64: str, key_salt: str) -> str:
        """Decrypts an AES-256-GCM encrypted payload."""
        try:
            key = self.derive_key(key_salt.encode())
            aesgcm = AESGCM(key)
            data = base64.b64decode(encrypted_b64)
            nonce = data[:12]
            ciphertext = data[12:]
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode()
        except Exception:
            return None
