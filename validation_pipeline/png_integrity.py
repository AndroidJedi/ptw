"""Strict bounded PNG validation; a matching hash alone does not prove usable pixels."""
from io import BytesIO
import struct
import zlib


def validate_png(data: bytes) -> tuple[int, int]:
    from PIL import Image
    if not 33 <= len(data) <= 8 * 1024 * 1024 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG signature or size")
    offset, ended, seen_data = 8, False, False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Incomplete PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError("Incomplete PNG chunk")
        kind = data[offset + 4:offset + 8]
        if offset == 8 and (kind != b"IHDR" or size != 13):
            raise ValueError("Invalid PNG header")
        if zlib.crc32(data[offset + 4:end - 4]) & 0xffffffff != struct.unpack_from(">I", data, end - 4)[0]:
            raise ValueError("Invalid PNG checksum")
        if kind == b"acTL":
            raise ValueError("Animated PNG is not supported")
        seen_data |= kind == b"IDAT"
        offset = end
        if kind == b"IEND":
            if size or not seen_data or end != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
            break
    if not ended:
        raise ValueError("Missing PNG end")
    with Image.open(BytesIO(data)) as image:
        if min(image.size) < 64 or max(image.size) > 8192 or image.width * image.height > 16_777_216:
            raise ValueError("PNG dimensions exceed supported bounds")
        image.verify()
    with Image.open(BytesIO(data)) as image:
        image.load()
        return image.size
