"""Settings management with at-rest encryption — port of queries.ts:955-1138.

Sensitive keys (currently just brave_search_api_key) are encrypted with
AES-256-GCM before storage, using a key derived from the
NEWSIXITY_SETTINGS_ENCRYPTION_KEY env var. Format on disk:

    encv1:{base64(iv)}:{base64(tag)}:{base64(ciphertext)}

An env var override (BRAVE_SEARCH_API_KEY) always wins on read and is never
persisted to the DB, matching the Node behavior exactly.
"""

from __future__ import annotations

import base64
import hashlib
import os
from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import Setting as SettingModel
from app.db.session import SessionLocal

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - cryptography is a core dependency
    AESGCM = None

ENCRYPTED_SETTING_KEYS = {"brave_search_api_key"}
ENCRYPTED_VALUE_PREFIX = "encv1"


class SettingsEncryptionRequiredError(Exception):
    pass


def _get_env_override_for_setting(key: str) -> str | None:
    if key == "brave_search_api_key":
        val = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
        return val or None
    return None


def _get_settings_encryption_key() -> bytes | None:
    raw = os.environ.get("NEWSIXITY_SETTINGS_ENCRYPTION_KEY", "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _encrypt_setting_value(value: str) -> str:
    key = _get_settings_encryption_key()
    if not key:
        raise SettingsEncryptionRequiredError(
            "NEWSIXITY_SETTINGS_ENCRYPTION_KEY is required to store sensitive settings"
        )

    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    # AESGCM.encrypt returns ciphertext with the 16-byte tag appended.
    ct_and_tag = aesgcm.encrypt(iv, value.encode("utf-8"), None)
    ciphertext, tag = ct_and_tag[:-16], ct_and_tag[-16:]

    return ":".join([
        ENCRYPTED_VALUE_PREFIX,
        base64.b64encode(iv).decode("ascii"),
        base64.b64encode(tag).decode("ascii"),
        base64.b64encode(ciphertext).decode("ascii"),
    ])


def _decrypt_setting_value(value: str) -> str | None:
    if not value.startswith(f"{ENCRYPTED_VALUE_PREFIX}:"):
        return value

    key = _get_settings_encryption_key()
    if not key:
        return None

    payload = value[len(ENCRYPTED_VALUE_PREFIX) + 1:]
    parts = payload.split(":")
    if len(parts) != 3:
        return None
    iv_b64, tag_b64, data_b64 = parts

    try:
        iv = base64.b64decode(iv_b64)
        tag = base64.b64decode(tag_b64)
        ciphertext = base64.b64decode(data_b64)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(iv, ciphertext + tag, None)
        return plaintext.decode("utf-8")
    except Exception:
        return None


def _is_encrypted_setting_value(value: str) -> bool:
    return value.startswith(f"{ENCRYPTED_VALUE_PREFIX}:")


def _maybe_encrypt_stored_setting_value(key: str, stored_value: str | None) -> str | None:
    """Lazily upgrade a plaintext stored value to encrypted form, if a key is configured."""
    if stored_value is None:
        return None
    if key not in ENCRYPTED_SETTING_KEYS:
        return stored_value
    if _is_encrypted_setting_value(stored_value):
        return stored_value
    if not _get_settings_encryption_key():
        return stored_value

    encrypted_value = _encrypt_setting_value(stored_value)
    with SessionLocal() as db:
        db.execute(
            update(SettingModel)
            .where(SettingModel.key == key)
            .values(value=encrypted_value)
        )
        db.commit()

    return encrypted_value


def _normalize_setting_value_for_read(key: str, value: str | None) -> str | None:
    env_override = _get_env_override_for_setting(key)
    if env_override is not None:
        return env_override

    if value is None:
        return None
    if key not in ENCRYPTED_SETTING_KEYS:
        return value
    return _decrypt_setting_value(value)


def _normalize_setting_value_for_write(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if key not in ENCRYPTED_SETTING_KEYS:
        return value
    return _encrypt_setting_value(value)


def get_setting(key: str) -> str | None:
    with SessionLocal() as db:
        row = db.execute(
            select(SettingModel.value).where(SettingModel.key == key)
        ).scalar_one_or_none()

    stored_value = _maybe_encrypt_stored_setting_value(key, row)
    return _normalize_setting_value_for_read(key, stored_value)


def set_setting(key: str, value: str | None) -> None:
    # When a sensitive setting is provided via environment, don't persist DB overrides.
    if key in ENCRYPTED_SETTING_KEYS and _get_env_override_for_setting(key) is not None:
        return

    if key in ENCRYPTED_SETTING_KEYS and value is not None and not _get_settings_encryption_key():
        raise SettingsEncryptionRequiredError(
            "Configure NEWSIXITY_SETTINGS_ENCRYPTION_KEY before saving API keys"
        )

    value_for_write = _normalize_setting_value_for_write(key, value)

    with SessionLocal() as db:
        stmt = sqlite_insert(SettingModel).values(
            key=key, value=value_for_write, updated_at=func.datetime("now")
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": stmt.excluded.value, "updated_at": func.datetime("now")},
        )
        db.execute(stmt)
        db.commit()


def get_all_settings() -> dict[str, str | None]:
    with SessionLocal() as db:
        rows = db.execute(select(SettingModel.key, SettingModel.value)).all()

    settings: dict[str, str | None] = {}
    for key, value in rows:
        stored_value = _maybe_encrypt_stored_setting_value(key, value)
        settings[key] = _normalize_setting_value_for_read(key, stored_value)

    # Ensure env overrides are represented even if the DB has no row.
    brave_key_override = _get_env_override_for_setting("brave_search_api_key")
    if brave_key_override is not None:
        settings["brave_search_api_key"] = brave_key_override

    return settings


def delete_setting(key: str) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(SettingModel).where(SettingModel.key == key)
        ).scalar_one_or_none()
        if row:
            db.delete(row)
            db.commit()


def get_ollama_model_setting() -> str | None:
    return get_setting("ollama_model")


def set_ollama_model_setting(model: str) -> None:
    set_setting("ollama_model", model)
