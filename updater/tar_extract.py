import gc
import os


def _join(root, path):
    if not root:
        return path
    if root.endswith("/") or root.endswith("\\"):
        root = root[:-1]
    if path.startswith("/") or path.startswith("\\"):
        path = path[1:]
    return root + "/" + path


def _mkdirs(path):
    parts = []
    p = path
    while p not in ("", "/", ".", "\\"):
        parts.append(p)
        p = p.rsplit("/", 1)[0] if "/" in p else ""
    for d in reversed(parts):
        try:
            os.stat(d)
        except OSError:
            try:
                os.mkdir(d)
            except OSError:
                pass


def _safe_path(path):
    text = str(path or "").replace("\\", "/").strip()
    if not text or text in (".", ".."):
        raise RuntimeError("unsafe path")
    if len(text) >= 2 and text[1] == ":":
        raise RuntimeError("unsafe path: %s" % text)
    if text.startswith("/") or text.startswith("../") or "/../" in text or text.endswith("/.."):
        raise RuntimeError("unsafe path: %s" % text)
    for segment in text.split("/"):
        if segment in (".", ".."):
            raise RuntimeError("unsafe path: %s" % text)
    if text == "config.py" or text.startswith("storage/") and text.endswith(".json"):
        raise RuntimeError("unsafe path: %s" % text)
    return text


def _octal(block, start, length):
    raw = block[start : start + length]
    text = raw.split(b"\0", 1)[0].strip() or b"0"
    return int(text, 8)


def _name(block):
    name = block[0:100].split(b"\0", 1)[0].decode()
    prefix = block[345:500].split(b"\0", 1)[0].decode()
    if prefix:
        name = prefix + "/" + name
    return _safe_path(name)


def _skip(f, size):
    remaining = size
    while remaining > 0:
        chunk = f.read(512 if remaining > 512 else remaining)
        if not chunk:
            break
        remaining -= len(chunk)
        del chunk


def _replace(tmp, dest):
    backup = dest + ".bak"
    has_backup = False
    try:
        os.remove(backup)
    except OSError:
        pass
    try:
        os.stat(dest)
        os.rename(dest, backup)
        has_backup = True
    except OSError:
        pass
    try:
        os.rename(tmp, dest)
    except Exception:
        if has_backup:
            try:
                os.rename(backup, dest)
            except OSError:
                pass
        raise
    if has_backup:
        try:
            os.remove(backup)
        except OSError:
            pass


def extract(tar_path, dest_root="", progress_callback=None, i18n=None):
    count = 0
    with open(tar_path, "rb") as f:
        while True:
            block = f.read(512)
            if not block or block == b"\0" * 512:
                break
            path = _name(block)
            size = _octal(block, 124, 12)
            typeflag = block[156:157]
            dest = _join(dest_root, path) if dest_root else path
            if typeflag == b"5":
                _mkdirs(dest)
            elif typeflag in (b"0", b""):
                parent = dest.rsplit("/", 1)[0] if "/" in dest else ""
                if parent:
                    _mkdirs(parent)
                tmp = dest + ".tmp"
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                remaining = size
                with open(tmp, "wb") as out:
                    while remaining > 0:
                        chunk = f.read(512 if remaining > 512 else remaining)
                        if not chunk:
                            raise RuntimeError("truncated tar")
                        out.write(chunk)
                        remaining -= len(chunk)
                        del chunk
                _replace(tmp, dest)
                count += 1
                if progress_callback:
                    progress_callback(
                        {
                            "stage": "extract",
                            "message": i18n.t("updater.installing") if i18n else "Installing",
                            "detail": path,
                            "current": count,
                            "total": 0,
                            "percent": 0,
                        }
                    )
            else:
                _skip(f, size)
            padding = (512 - (size % 512)) % 512
            if padding:
                _skip(f, padding)
            del block, path, dest
            gc.collect()
    return count
