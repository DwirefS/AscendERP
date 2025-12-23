"""
Encryption Tests

Test cryptographic operations and PII protection.
"""

import pytest
from src.core.security.encryption import EncryptionHelper, encrypt_field, decrypt_field


@pytest.fixture
def encryption_helper():
    """Get encryption helper with test key."""
    # Generate test key (32 bytes for AES-256)
    test_key = b"0" * 32
    return EncryptionHelper(master_key=test_key)


class TestEncryption:
    """Test encryption and decryption."""

    def test_encrypt_decrypt_string(self, encryption_helper):
        """Test encrypting and decrypting a string."""
        plaintext = "This is a secret message"

        # Encrypt
        ciphertext = encryption_helper.encrypt(plaintext)
        assert ciphertext != plaintext
        assert len(ciphertext) > 0

        # Decrypt
        decrypted = encryption_helper.decrypt_to_string(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_decrypt_bytes(self, encryption_helper):
        """Test encrypting and decrypting bytes."""
        plaintext = b"Secret binary data"

        # Encrypt
        ciphertext = encryption_helper.encrypt(plaintext)

        # Decrypt
        decrypted = encryption_helper.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_different_ciphertexts_same_plaintext(self, encryption_helper):
        """Test same plaintext produces different ciphertexts (due to random nonce)."""
        plaintext = "Same message"

        ciphertext1 = encryption_helper.encrypt(plaintext)
        ciphertext2 = encryption_helper.encrypt(plaintext)

        # Ciphertexts should differ (random nonce)
        assert ciphertext1 != ciphertext2

        # But both decrypt to same plaintext
        assert encryption_helper.decrypt_to_string(ciphertext1) == plaintext
        assert encryption_helper.decrypt_to_string(ciphertext2) == plaintext

    def test_tampered_ciphertext_rejected(self, encryption_helper):
        """Test tampered ciphertext is detected and rejected."""
        plaintext = "Original message"
        ciphertext = encryption_helper.encrypt(plaintext)

        # Tamper with ciphertext
        tampered = ciphertext[:-1] + ("X" if ciphertext[-1] != "X" else "Y")

        # Should fail to decrypt
        with pytest.raises(ValueError, match="Decryption failed"):
            encryption_helper.decrypt(tampered)

    def test_authenticated_encryption_with_associated_data(self, encryption_helper):
        """Test authenticated encryption with associated data."""
        plaintext = "Secret data"
        associated_data = b"field_name"

        # Encrypt with associated data
        ciphertext = encryption_helper.encrypt(plaintext, associated_data=associated_data)

        # Decrypt with correct associated data
        decrypted = encryption_helper.decrypt_to_string(ciphertext, associated_data=associated_data)
        assert decrypted == plaintext

        # Decrypt with wrong associated data should fail
        with pytest.raises(ValueError):
            encryption_helper.decrypt_to_string(ciphertext, associated_data=b"wrong_field")


class TestPIIMasking:
    """Test PII masking."""

    def test_mask_credit_card(self, encryption_helper):
        """Test credit card masking."""
        cc_number = "4111111111111111"
        masked = encryption_helper.mask_pii(cc_number, reveal_last=4)

        assert masked == "************1111"
        assert len(masked) == len(cc_number)

    def test_mask_ssn(self, encryption_helper):
        """Test SSN masking."""
        ssn = "123-45-6789"
        masked = encryption_helper.mask_pii(ssn, reveal_last=4)

        assert masked == "*******6789"

    def test_mask_short_value(self, encryption_helper):
        """Test masking value shorter than reveal_last."""
        short_value = "ABC"
        masked = encryption_helper.mask_pii(short_value, reveal_last=4)

        # Should mask entire value
        assert masked == "***"


class TestPIITokenization:
    """Test PII tokenization."""

    def test_deterministic_tokenization(self, encryption_helper):
        """Test same value always produces same token."""
        pii = "123-45-6789"

        token1 = encryption_helper.tokenize_pii(pii, context="ssn")
        token2 = encryption_helper.tokenize_pii(pii, context="ssn")

        assert token1 == token2

    def test_different_context_different_token(self, encryption_helper):
        """Test different context produces different token."""
        pii = "123-45-6789"

        token_ssn = encryption_helper.tokenize_pii(pii, context="ssn")
        token_id = encryption_helper.tokenize_pii(pii, context="id")

        assert token_ssn != token_id

    def test_different_values_different_tokens(self, encryption_helper):
        """Test different values produce different tokens."""
        token1 = encryption_helper.tokenize_pii("123-45-6789", context="ssn")
        token2 = encryption_helper.tokenize_pii("987-65-4321", context="ssn")

        assert token1 != token2


class TestPasswordHashing:
    """Test password hashing."""

    def test_hash_password(self, encryption_helper):
        """Test password hashing."""
        password = "SecureP@ssw0rd!"

        password_hash, salt = encryption_helper.hash_password(password)

        assert password_hash != password
        assert len(password_hash) > 0
        assert len(salt) > 0

    def test_verify_correct_password(self, encryption_helper):
        """Test verifying correct password."""
        password = "SecureP@ssw0rd!"

        password_hash, salt = encryption_helper.hash_password(password)

        # Verify correct password
        assert encryption_helper.verify_password(password, password_hash, salt) is True

    def test_verify_incorrect_password(self, encryption_helper):
        """Test verifying incorrect password fails."""
        password = "SecureP@ssw0rd!"
        wrong_password = "WrongP@ssw0rd!"

        password_hash, salt = encryption_helper.hash_password(password)

        # Verify wrong password
        assert encryption_helper.verify_password(wrong_password, password_hash, salt) is False

    def test_same_password_different_hashes(self, encryption_helper):
        """Test same password produces different hashes (due to random salt)."""
        password = "SecureP@ssw0rd!"

        hash1, salt1 = encryption_helper.hash_password(password)
        hash2, salt2 = encryption_helper.hash_password(password)

        # Hashes should differ (different salts)
        assert hash1 != hash2
        assert salt1 != salt2


class TestSecureTokenGeneration:
    """Test secure token generation."""

    def test_generate_secure_token(self, encryption_helper):
        """Test generating secure random tokens."""
        token1 = encryption_helper.generate_secure_token(length=32)
        token2 = encryption_helper.generate_secure_token(length=32)

        # Tokens should be different
        assert token1 != token2

        # Tokens should be hex strings
        assert len(token1) == 64  # 32 bytes = 64 hex chars
        assert all(c in "0123456789abcdef" for c in token1)

    def test_generate_api_key(self, encryption_helper):
        """Test API key generation."""
        api_key1 = encryption_helper.generate_api_key()
        api_key2 = encryption_helper.generate_api_key()

        # Keys should be different
        assert api_key1 != api_key2

        # Keys should have correct format
        assert api_key1.startswith("ants_")
        assert len(api_key1) == 69  # "ants_" + 64 hex chars


class TestDataHashing:
    """Test SHA-256 hashing."""

    def test_hash_string(self, encryption_helper):
        """Test hashing a string."""
        data = "Hash this data"
        hash1 = encryption_helper.hash_data(data)

        # Hash should be deterministic
        hash2 = encryption_helper.hash_data(data)
        assert hash1 == hash2

        # Hash should be SHA-256 (64 hex chars)
        assert len(hash1) == 64

    def test_different_data_different_hash(self, encryption_helper):
        """Test different data produces different hash."""
        hash1 = encryption_helper.hash_data("Data 1")
        hash2 = encryption_helper.hash_data("Data 2")

        assert hash1 != hash2


class TestFieldEncryption:
    """Test database field encryption helpers."""

    def test_encrypt_decrypt_field(self, encryption_helper):
        """Test field encryption with field name as associated data."""
        value = "Sensitive customer data"
        field_name = "customer_ssn"

        # Encrypt field
        encrypted = encrypt_field(value, field_name)

        # Decrypt field (with correct field name)
        decrypted = decrypt_field(encrypted, field_name)
        assert decrypted == value

        # Decrypt with wrong field name should fail
        with pytest.raises(ValueError):
            decrypt_field(encrypted, "wrong_field")
