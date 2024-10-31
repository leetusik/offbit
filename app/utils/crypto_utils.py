from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


def encrypt_api_key(public_key, api_key: str) -> bytes:
    encrypted_api_key = public_key.encrypt(
        api_key.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return encrypted_api_key


def decrypt_api_key(private_key, encrypted_api_key: bytes) -> str:
    decrypted_api_key = private_key.decrypt(
        encrypted_api_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return decrypted_api_key
