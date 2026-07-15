import secrets
import string


TEMPORARY_PASSWORD_LENGTH = 16
TEMPORARY_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%*-_"


def generate_temporary_password() -> str:
    characters = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%*-_"),
    ]
    characters.extend(
        secrets.choice(TEMPORARY_PASSWORD_ALPHABET)
        for _ in range(TEMPORARY_PASSWORD_LENGTH - len(characters))
    )
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
