import hashlib
import json


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def fingerprints(material):
    return {name: digest(text.encode()) if isinstance(text, str) else digest(encode(text))
            for name, text in material.items()}
