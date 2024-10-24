from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import os
import json
from datetime import datetime, timedelta

class ChatCrypto:
    def __init__(self, user_id: str, friend_id: str):
        self.user_id = str(user_id)
        self.friend_id = str(friend_id)
        self.key_version = 1
        self.key = self._generate_key()
        self.last_rotation = datetime.now()

    def _generate_key(self) -> bytes:
        shared_info = f"{min(self.user_id, self.friend_id)}_{max(self.user_id, self.friend_id)}_{self.key_version}"
        salt = b'fixed_salt_for_chat'
        
        kdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=shared_info.encode(),
        )
        key = kdf.derive(shared_info.encode())
        return key

    def encrypt(self, message: str) -> dict:
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, message.encode(), None)
        
        return {
            'ciphertext': ciphertext.hex(),
            'nonce': nonce.hex()
        }

    def decrypt(self, encrypted_data: dict) -> str:
        try:
            aesgcm = AESGCM(self.key)
            nonce = bytes.fromhex(encrypted_data['nonce'])
            ciphertext = bytes.fromhex(encrypted_data['ciphertext'])
            
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            print(f"Error en decrypt: {str(e)}")
            return None

    def _should_rotate_key(self) -> bool:
        return datetime.now() - self.last_rotation > timedelta(hours=24)

    def rotate_key(self):
        self.key_version += 1
        self.key = self._generate_key()
        self.last_rotation = datetime.now()
        return self.key_version

    def __getstate__(self):
        return {
            'user_id': self.user_id,
            'friend_id': self.friend_id,
            'key_version': self.key_version,
            'key': self.key,
            'last_rotation': self.last_rotation
        }

    def __setstate__(self, state):
        self.user_id = state['user_id']
        self.friend_id = state['friend_id']
        self.key_version = state['key_version']
        self.key = state['key']
        self.last_rotation = state['last_rotation']
