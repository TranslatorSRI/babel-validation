"""Core data types shared across babel_validation, plus the cache location they use."""

import os
from pathlib import Path


def cache_dir() -> Path:
    """A private, per-user directory for cached downloads, created if missing.

    Deliberately not the shared temp directory. These caches have predictable, fixed
    names, so on a multi-user machine or a CI runner anyone could pre-create one as a
    symlink — we would then overwrite whatever it points at — or simply rewrite its
    contents. That second one matters more than it looks: the GitHub issue cache holds a
    list of issue IDs that a later run fetches and executes BabelTest assertions from, so
    being able to write it is close to being able to choose what the run tests.

    A directory under the user's own home has neither exposure, which removes the problem
    rather than mitigating it. Set BABEL_VALIDATION_CACHE_DIR to override it (a CI runner
    without a writable home, say).
    """
    override = os.environ.get("BABEL_VALIDATION_CACHE_DIR")
    try:
        path = Path(override) if override else Path.home() / ".cache" / "babel-validation"
        # mode applies to this directory only; any parents get the default permissions.
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as e:
        # A read-only or absent home is the realistic case, on a locked-down runner or in a
        # container. The bare PermissionError names a path but gives no hint that there is an
        # override, which is the whole reason it exists.
        raise RuntimeError(
            f"Could not create the cache directory: {e}. Set BABEL_VALIDATION_CACHE_DIR to a "
            f"writable location."
        ) from e
    return path
