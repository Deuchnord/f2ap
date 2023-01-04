import base64

from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

from .config import Configuration


def sign_headers(config: Configuration, request_target: str, headers: dict, http_method: str = "post") -> str:
    signed_headers = ["(request-target)"] + list(map(lambda s: s.lower(), headers.keys()))
    to_sign = [f"(request-target): {http_method} {request_target}"]

    for header in headers:
        to_sign.append(f"{header.lower()}: {headers[header]}")

    key = RSA.import_key(config.actor.private_key)
    signer = pkcs1_15.new(key)
    hash = SHA256.new()
    hash.update("\n".join(to_sign).encode())

    signature = base64.b64encode(signer.sign(hash)).decode()

    return ",".join([
        f'keyId="{config.actor.key_id}"',
        'algorithm="rsa-sha256"',
        f'headers="{" ".join(signed_headers)}"',
        f'signature="{signature}"',
    ])


def validate_headers(public_key: str, headers: dict, request_target: str, http_method: str = "post"):
    signature_header = headers.get("signature")

    if signature_header is None:
        raise ValueError("Missing signature")

    signature = {}
    for s in signature_header.split(","):
        key, value = tuple(s.split("=", 1))
        signature[key] = value.strip('"')

    message = []
    signature_headers_to_validate = signature.get("headers").split(" ")
    for header in signature_headers_to_validate:
        if header == "(request-target)":
            message.append(f'(request-target): {http_method} {request_target}')
            continue

        message.append(f'{header}: {headers.get(header)}')

    message = '\n'.join(message)

    key = RSA.import_key(public_key)
    verifier = pkcs1_15.new(key)
    hash = SHA256.new()
    hash.update(message.encode())

    try:
        verifier.verify(hash, base64.b64decode(signature["signature"]))
    except ValueError:
        raise ValueError("Invalid signature")
