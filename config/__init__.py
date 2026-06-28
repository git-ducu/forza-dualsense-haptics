"""Settings model plus on-disk persistence."""
from . import paths, profile_store, profileManager
from .profile_store import PreferencesError
from .settings import Settings

preferences = profile_store
profiles = profileManager

__all__ = [
    "Settings",
    "paths",
    "profile_store",
    "preferences",
    "profileManager",
    "profiles",
    "PreferencesError",
]
