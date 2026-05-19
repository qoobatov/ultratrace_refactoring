def decode_bytes(byt: bytes) -> str:
    for enc in ["utf-8", "Windows-1251", "Windows-1252", "ISO-8859-1"]:
        try:
            return byt.decode(enc)
        except UnicodeDecodeError:
            pass
    return ""
