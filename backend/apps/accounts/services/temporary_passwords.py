import secrets
import string


TEMPORARY_PASSWORD_LENGTH = 8


def generate_temporary_password() -> str:
    return "".join(
        secrets.choice(string.digits)
        for _ in range(TEMPORARY_PASSWORD_LENGTH)
    )
