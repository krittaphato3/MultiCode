"""
Secure credential storage for MultiCode.

Uses OS-level keyring when available (Windows Credential Manager,
macOS Keychain, Linux Secret Service), with obfuscated file fallback.

Security features:
- Keys never logged or printed
- Masked display (shows only first/last few chars)
- Obfuscated storage when keyring unavailable (XOR + base64, not cryptographic)
- Automatic key rotation support
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import keyring for secure storage
try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.debug("keyring not available, using fallback storage")


class CredentialStorage:
    """
    Secure credential storage with OS keyring integration.
    
    Usage:
        storage = CredentialStorage()
        storage.set_api_key("sk-or-v1-...")
        key = storage.get_api_key()  # Returns full key or None
        key_masked = storage.get_api_key_masked()  # Returns "sk-or-v1-abc...xyz"
    """
    
    SERVICE_NAME = "multicode"
    USERNAME = "openrouter_api_key"
    
    def __init__(self) -> None:
        """Initialize credential storage."""
        self._config_dir = Path.home() / ".multicode"
        self._fallback_file = self._config_dir / ".credentials.enc"
        self._ensure_config_dir()
    
    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner read/write only)
        try:
            os.chmod(self._config_dir, 0o700)
        except Exception:
            pass  # May fail on Windows, continue anyway
    
    def get_api_key(self) -> str | None:
        """
        Get API key from secure storage.
        
        Returns:
            API key string or None if not set
        """
        # Try keyring first
        if KEYRING_AVAILABLE:
            try:
                key = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
                if key:
                    logger.debug("API key retrieved from keyring")
                    return key
            except KeyringError as e:
                logger.warning(f"Keyring error: {e}")
            except Exception as e:
                logger.debug(f"Unexpected keyring error: {e}")
        
        # Fallback to obfuscated file storage
        # Uses XOR + base64 obfuscation with machine-derived key
        # Not cryptographically secure but prevents casual plaintext reading
        fallback_file = self._config_dir / ".credentials"
        if fallback_file.exists():
            try:
                key = self._read_obfuscated_file(fallback_file)
                if key:
                    logger.debug("API key retrieved from fallback file")
                    return key
            except Exception as e:
                logger.warning(f"Failed to read fallback credentials: {e}")
        
        # Last resort: check environment variable
        env_key = os.getenv("MULTICODE_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if env_key:
            logger.debug("API key retrieved from environment")
            return env_key
        
        logger.debug("No API key found")
        return None
    
    def set_api_key(self, key: str) -> bool:
        """
        Store API key securely.
        
        Args:
            key: API key to store
            
        Returns:
            True if successful, False otherwise
        """
        if not key or not key.strip():
            logger.warning("Attempted to store empty API key")
            return False
        
        key = key.strip()
        
        # Try keyring first
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(self.SERVICE_NAME, self.USERNAME, key)
                logger.info("API key stored in keyring")
                return True
            except KeyringError as e:
                logger.warning(f"Keyring error, using fallback: {e}")
            except Exception as e:
                logger.warning(f"Unexpected keyring error, using fallback: {e}")
        
        # Fallback to obfuscated file storage
        try:
            fallback_file = self._config_dir / ".credentials"
            self._write_obfuscated_file(fallback_file, key)
            # Set restrictive permissions
            try:
                os.chmod(fallback_file, 0o600)
            except Exception:
                pass
            logger.info("API key stored in fallback file (obfuscated)")
            return True
        except Exception as e:
            logger.error(f"Failed to store API key in fallback: {e}")
            return False
    
    def delete_api_key(self) -> bool:
        """
        Delete stored API key.
        
        Returns:
            True if key was deleted, False if no key existed
        """
        deleted = False
        
        # Delete from keyring
        if KEYRING_AVAILABLE:
            try:
                keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
                logger.info("API key deleted from keyring")
                deleted = True
            except KeyringError:
                pass  # Key wasn't in keyring
            except Exception:
                pass
        
        # Delete from fallback file
        fallback_file = self._config_dir / ".credentials"
        if fallback_file.exists():
            try:
                fallback_file.unlink()
                logger.info("API key deleted from fallback file")
                deleted = True
            except Exception:
                pass
        
        # Clear environment variable
        for env_var in ["MULTICODE_API_KEY", "OPENROUTER_API_KEY"]:
            if os.getenv(env_var):
                del os.environ[env_var]
                logger.debug(f"Cleared {env_var} from environment")
                deleted = True
        
        if deleted:
            logger.info("API key completely removed")
        else:
            logger.debug("No API key was stored")
        
        return deleted
    
    def get_api_key_masked(self) -> str:
        """
        Get masked version of API key for display.
        
        Returns:
            Masked key string (e.g., "sk-or-v1-abc...xyz") or "[not set]"
        """
        key = self.get_api_key()
        
        if not key:
            return "[not set]"
        
        # Show first 15 and last 4 characters
        if len(key) > 20:
            return f"{key[:15]}...{key[-4:]}"
        elif len(key) > 5:
            return f"{key[:5]}..."
        else:
            return "***"
    
    def _get_machine_key(self) -> bytes:
        """Derive a machine-specific key for basic obfuscation.

        Uses hashlib with machine identifiers. This is NOT cryptographic
        security — it prevents casual plaintext reading of the credential
        file while remaining dependency-free.
        """
        import getpass
        import hashlib
        import socket
        machine_id = f"{getpass.getuser()}:{socket.gethostname()}"
        return hashlib.sha256(machine_id.encode()).digest()

    def _write_obfuscated_file(self, path: Path, key: str) -> None:
        """Write an API key with XOR + base64 obfuscation."""
        import base64
        mk = self._get_machine_key()
        key_bytes = key.encode("utf-8")
        # XOR with repeating machine key
        xored = bytes(
            b ^ mk[i % len(mk)] for i, b in enumerate(key_bytes)
        )
        encoded = base64.b64encode(xored).decode("ascii")
        path.write_text(f"MC1:{encoded}\n")
        # Set restrictive permissions
        try:
            import os
            os.chmod(path, 0o600)
        except Exception:
            pass

    def _read_obfuscated_file(self, path: Path) -> str | None:
        """Read and de-obfuscate an API key from file."""
        import base64
        raw = path.read_text().strip()
        if not raw.startswith("MC1:"):
            # Legacy plaintext — migrate silently
            key = raw.strip()
            if key:
                self._write_obfuscated_file(path, key)
            return key
        encoded = raw[4:]  # Strip "MC1:" prefix
        xored = base64.b64decode(encoded)
        mk = self._get_machine_key()
        key_bytes = bytes(
            b ^ mk[i % len(mk)] for i, b in enumerate(xored)
        )
        return key_bytes.decode("utf-8")

    def has_api_key(self) -> bool:
        """
        Check if API key is stored.
        
        Returns:
            True if key exists, False otherwise
        """
        return self.get_api_key() is not None


# Global credential storage instance
_storage: CredentialStorage | None = None


def get_credential_storage() -> CredentialStorage:
    """Get the global credential storage instance."""
    global _storage
    if _storage is None:
        _storage = CredentialStorage()
    return _storage


# Convenience functions
def get_api_key() -> str | None:
    """Get API key from secure storage."""
    return get_credential_storage().get_api_key()


def set_api_key(key: str) -> bool:
    """Store API key securely."""
    return get_credential_storage().set_api_key(key)


def delete_api_key() -> bool:
    """Delete stored API key."""
    return get_credential_storage().delete_api_key()


def get_api_key_masked() -> str:
    """Get masked API key for display."""
    return get_credential_storage().get_api_key_masked()


def has_api_key() -> bool:
    """Check if API key is stored."""
    return get_credential_storage().has_api_key()
