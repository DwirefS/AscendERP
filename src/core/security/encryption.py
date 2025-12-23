"""
Encryption Helper

Cryptographic utilities for:
- Data encryption at rest
- Field-level encryption
- PII masking and tokenization
- Secure hashing
- Digital signatures

Uses industry-standard algorithms:
- AES-256-GCM for encryption
- SHA-256 for hashing
- HMAC for message authentication
"""

import os
import logging
import hashlib
import hmac
import base64
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets

logger = logging.getLogger(__name__)


class EncryptionHelper:
    """
    Encryption and cryptographic utilities.

    Features:
    - AES-256-GCM encryption (authenticated encryption)
    - Secure key derivation
    - PII masking
    - Secure random generation
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize Encryption Helper.

        Args:
            master_key: Master encryption key (32 bytes for AES-256)
                       If not provided, will be loaded from environment or Key Vault
        """
        if master_key:
            if len(master_key) != 32:
                raise ValueError("Master key must be 32 bytes for AES-256")
            self.master_key = master_key
        else:
            # Load from environment (in production, use Key Vault)
            key_b64 = os.getenv("ENCRYPTION_MASTER_KEY")
            if key_b64:
                self.master_key = base64.b64decode(key_b64)
            else:
                logger.warning(
                    "No master key provided - encryption disabled. "
                    "Set ENCRYPTION_MASTER_KEY environment variable."
                )
                self.master_key = None

    def encrypt(self, plaintext: Union[str, bytes], associated_data: Optional[bytes] = None) -> str:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt (string or bytes)
            associated_data: Additional authenticated data (not encrypted, but authenticated)

        Returns:
            Base64-encoded ciphertext with nonce and tag

        Format: base64(nonce || ciphertext || tag)
        """
        if not self.master_key:
            raise ValueError("Master key not configured")

        # Convert string to bytes
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        # Generate random nonce (12 bytes for GCM)
        nonce = os.urandom(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.GCM(nonce),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()

        # Add associated data if provided
        if associated_data:
            encryptor.authenticate_additional_data(associated_data)

        # Encrypt
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # Get authentication tag
        tag = encryptor.tag

        # Combine: nonce || ciphertext || tag
        encrypted_data = nonce + ciphertext + tag

        # Base64 encode for storage
        return base64.b64encode(encrypted_data).decode("ascii")

    def decrypt(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            ciphertext_b64: Base64-encoded ciphertext (from encrypt())
            associated_data: Additional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext as bytes

        Raises:
            ValueError: If decryption fails (wrong key, tampered data, etc.)
        """
        if not self.master_key:
            raise ValueError("Master key not configured")

        # Decode from base64
        encrypted_data = base64.b64decode(ciphertext_b64)

        # Extract components
        nonce = encrypted_data[:12]
        tag = encrypted_data[-16:]
        ciphertext = encrypted_data[12:-16]

        # Create cipher
        cipher = Cipher(
            algorithms.AES(self.master_key),
            modes.GCM(nonce, tag),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        # Add associated data if provided
        if associated_data:
            decryptor.authenticate_additional_data(associated_data)

        # Decrypt
        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed - invalid key or tampered data")

    def decrypt_to_string(self, ciphertext_b64: str, associated_data: Optional[bytes] = None) -> str:
        """
        Decrypt and return as UTF-8 string.

        Args:
            ciphertext_b64: Base64-encoded ciphertext
            associated_data: Additional authenticated data

        Returns:
            Decrypted plaintext as string
        """
        plaintext_bytes = self.decrypt(ciphertext_b64, associated_data)
        return plaintext_bytes.decode("utf-8")

    def mask_pii(self, value: str, mask_char: str = "*", reveal_last: int = 4) -> str:
        """
        Mask PII for display (e.g., credit card, SSN).

        Args:
            value: Value to mask
            mask_char: Character to use for masking
            reveal_last: Number of characters to reveal at end

        Returns:
            Masked value

        Example:
            mask_pii("4111111111111111", reveal_last=4) -> "************1111"
        """
        if len(value) <= reveal_last:
            # Value too short to mask
            return mask_char * len(value)

        masked_length = len(value) - reveal_last
        return (mask_char * masked_length) + value[-reveal_last:]

    def tokenize_pii(self, value: str, context: str = "") -> str:
        """
        Tokenize PII (replace with irreversible token).

        Uses HMAC-SHA256 for deterministic tokenization.

        Args:
            value: Value to tokenize
            context: Context string (e.g., "ssn", "credit_card")

        Returns:
            Hex token

        Note: Same value always produces same token (deterministic).
        """
        if not self.master_key:
            raise ValueError("Master key not configured")

        # Create HMAC with context
        h = hmac.new(
            self.master_key,
            (context + value).encode("utf-8"),
            hashlib.sha256,
        )

        return h.hexdigest()

    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
        """
        Hash password using PBKDF2-HMAC-SHA256.

        Args:
            password: Password to hash
            salt: Salt (generated if not provided)

        Returns:
            Tuple of (hash_b64, salt_b64)
        """
        if salt is None:
            salt = os.urandom(16)

        # PBKDF2 with 100,000 iterations
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )

        password_hash = kdf.derive(password.encode("utf-8"))

        return (
            base64.b64encode(password_hash).decode("ascii"),
            base64.b64encode(salt).decode("ascii"),
        )

    def verify_password(self, password: str, password_hash_b64: str, salt_b64: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Password to verify
            password_hash_b64: Base64-encoded hash
            salt_b64: Base64-encoded salt

        Returns:
            True if password matches, False otherwise
        """
        salt = base64.b64decode(salt_b64)
        expected_hash = base64.b64decode(password_hash_b64)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )

        try:
            kdf.verify(password.encode("utf-8"), expected_hash)
            return True
        except Exception:
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate cryptographically secure random token.

        Args:
            length: Token length in bytes

        Returns:
            Hex token string
        """
        return secrets.token_hex(length)

    def generate_api_key(self) -> str:
        """
        Generate API key.

        Format: "ants_" + 32 bytes hex = 69 characters

        Returns:
            API key string
        """
        return f"ants_{secrets.token_hex(32)}"

    def hash_data(self, data: Union[str, bytes]) -> str:
        """
        Compute SHA-256 hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex hash string
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return hashlib.sha256(data).hexdigest()


# Global encryption helper instance
_encryption_helper: Optional[EncryptionHelper] = None


def get_encryption_helper(master_key: Optional[bytes] = None) -> EncryptionHelper:
    """
    Get or create the global EncryptionHelper instance.

    Args:
        master_key: Master encryption key

    Returns:
        EncryptionHelper singleton instance
    """
    global _encryption_helper

    if _encryption_helper is None:
        _encryption_helper = EncryptionHelper(master_key=master_key)

    return _encryption_helper


# Utility functions
def encrypt_field(value: str, field_name: str = "") -> str:
    """
    Encrypt a database field.

    Args:
        value: Value to encrypt
        field_name: Field name (used as associated data)

    Returns:
        Encrypted value
    """
    helper = get_encryption_helper()
    associated_data = field_name.encode("utf-8") if field_name else None
    return helper.encrypt(value, associated_data=associated_data)


def decrypt_field(encrypted_value: str, field_name: str = "") -> str:
    """
    Decrypt a database field.

    Args:
        encrypted_value: Encrypted value
        field_name: Field name (must match encryption)

    Returns:
        Decrypted value
    """
    helper = get_encryption_helper()
    associated_data = field_name.encode("utf-8") if field_name else None
    return helper.decrypt_to_string(encrypted_value, associated_data=associated_data)
