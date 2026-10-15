"""Content sniffing for uploaded files.

libmagic is the most accurate detector, but loading it can hang indefinitely on
some Windows installs (the whole request, and the dev server, then freezes on the
first upload).  So it is only used when ``USE_LIBMAGIC`` is on; otherwise a small
table of file signatures covers the image, video and audio types the app accepts.
"""

from django.conf import settings

_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"\x1a\x45\xdf\xa3", "video/webm"),
)


def _by_signature(header: bytes):
    for prefix, mime in _SIGNATURES:
        if header.startswith(prefix):
            return mime
    if header[:4] == b"RIFF":
        kind = header[8:12]
        if kind == b"WEBP":
            return "image/webp"
        if kind == b"WAVE":
            return "audio/wav"
        if kind == b"AVI ":
            return "video/x-msvideo"
    if header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"msf1"):
            return "image/heic"
        if brand == b"M4A ":
            return "audio/mp4"
        if brand == b"qt  ":
            return "video/quicktime"
        return "video/mp4"
    return None


def detect_mime(header: bytes):
    """Best-guess MIME type for the start of a file, or ``None`` if unrecognised."""
    if getattr(settings, "USE_LIBMAGIC", False):
        try:
            import magic

            return magic.from_buffer(header, mime=True)
        except ImportError:
            pass
    return _by_signature(header)
