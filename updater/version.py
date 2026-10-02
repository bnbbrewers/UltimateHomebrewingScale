"""Release tags and the installed version.

Leaf module: the launcher's update notice reads it on every boot, so it must
not drag the HTTP or archive code onto the heap.
"""

VERSION_FILE = "uhs-version.txt"


def parse(tag):
    """`vX.Y.Z` (leading `v` optional) as three integers, else None."""
    text = str(tag or "").strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    parts = text.split(".")
    if len(parts) != 3:
        return None
    for part in parts:
        if not part.isdigit():
            return None
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def is_newer(remote, local):
    """True only when both tags parse and the remote one is newer.

    An unknown local version (no version file, a dev build) never counts as
    outdated: the notice must not offer to replace a build nobody tagged.
    """
    remote_version = parse(remote)
    local_version = parse(local)
    if remote_version is None or local_version is None:
        return False
    return remote_version > local_version


def read_local_version(path=VERSION_FILE):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""
