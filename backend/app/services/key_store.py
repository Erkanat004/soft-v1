import logging
import keyring

logger = logging.getLogger("key_store")
SERVICE_NAME = "StoryForgeAI"

# In-memory session key store fallback (used when remember_key is False or keyring fails)
_IN_MEMORY_KEYS: dict[str, str] = {}

def set_api_key(provider_name: str, api_key: str, remember: bool = True) -> bool:
    """
    Save API key securely.
    If remember is True, save to Windows Credential Manager via keyring.
    If remember is False, store in-memory only.
    """
    key_name = f"{SERVICE_NAME}_{provider_name}"
    if not remember:
        _IN_MEMORY_KEYS[provider_name] = api_key
        # Remove from keyring if previously stored
        try:
            keyring.delete_password(SERVICE_NAME, key_name)
        except Exception:
            pass
        return True

    try:
        keyring.set_password(SERVICE_NAME, key_name, api_key)
        _IN_MEMORY_KEYS[provider_name] = api_key
        return True
    except Exception as e:
        logger.warning(f"Keyring failed to save key for {provider_name}, falling back to in-memory: {e}")
        _IN_MEMORY_KEYS[provider_name] = api_key
        return False

def get_api_key(provider_name: str) -> str:
    """
    Retrieve API key for provider. Check memory first, then Windows Credential Manager.
    """
    if provider_name in _IN_MEMORY_KEYS and _IN_MEMORY_KEYS[provider_name]:
        return _IN_MEMORY_KEYS[provider_name]

    key_name = f"{SERVICE_NAME}_{provider_name}"
    try:
        secret = keyring.get_password(SERVICE_NAME, key_name)
        if secret:
            _IN_MEMORY_KEYS[provider_name] = secret
            return secret
    except Exception as e:
        logger.warning(f"Failed to fetch key from keyring for {provider_name}: {e}")
    
    return ""

def delete_api_key(provider_name: str) -> bool:
    """Delete API key from memory and keyring."""
    _IN_MEMORY_KEYS.pop(provider_name, None)
    key_name = f"{SERVICE_NAME}_{provider_name}"
    try:
        keyring.delete_password(SERVICE_NAME, key_name)
        return True
    except Exception:
        return False

def has_api_key(provider_name: str) -> bool:
    """Check if an API key exists for the provider."""
    return bool(get_api_key(provider_name))
