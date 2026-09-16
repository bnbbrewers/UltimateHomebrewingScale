"""Read one field out of a multipart/form-data request body.

A file picker forces the browser to send multipart rather than urlencoded, and
MicroPython ships no cgi module. Only what the portal needs is implemented: a
single named field, read from a body the request parser already capped at
MAX_REQUEST_BODY_BYTES and decoded to text.
"""

_BOUNDARY_MARKER = "boundary="


def boundary_of(content_type):
    """Return the boundary declared in a Content-Type header, or None."""
    text = str(content_type or "")
    if "multipart/form-data" not in text:
        return None
    index = text.find(_BOUNDARY_MARKER)
    if index < 0:
        return None
    boundary = text[index + len(_BOUNDARY_MARKER):].split(";")[0].strip()
    if len(boundary) >= 2 and boundary[0] == '"' and boundary[-1] == '"':
        boundary = boundary[1:-1]
    return boundary or None


def field_value(body, boundary, name):
    """Return the content of the named field, or None when it is absent.

    The content is returned exactly as uploaded, minus the CRLF the browser
    inserts before the next delimiter: a backup file must survive the trip
    unchanged, trailing blank line included.
    """
    if not boundary:
        return None
    marker = 'name="{}"'.format(name)
    for part in str(body or "").split("--" + boundary):
        head, separator, content = part.partition("\r\n\r\n")
        if not separator or marker not in head:
            continue
        if content.endswith("\r\n"):
            content = content[:-2]
        return content
    return None
