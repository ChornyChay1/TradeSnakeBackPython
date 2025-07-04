
from datetime import datetime, timedelta
import jwt
from Const.const import secret_key,secret_key_change_pass

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
EMAIL_TOKEN_EXPIRE_MINUTES = 3

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload.get("user_id"))
    except jwt.ExpiredSignatureError:
        return None
    except jwt.DecodeError:
        return None



def create_activation_token(user_id: int):
    expire = datetime.utcnow() + timedelta(minutes=EMAIL_TOKEN_EXPIRE_MINUTES)
    data = {"sub": str(user_id), "exp": expire}
    return jwt.encode(data, secret_key, algorithm=ALGORITHM)


def verify_activation_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except jwt.ExpiredSignatureError:
        return None
    except jwt.DecodeError:
        return None

def create_change_password_access(user_id: int):
    expire = datetime.utcnow() + timedelta(minutes=EMAIL_TOKEN_EXPIRE_MINUTES)
    data = {"sub": str(user_id), "exp": expire}
    return jwt.encode(data, secret_key_change_pass, algorithm=ALGORITHM)


def verify_change_password_access(token: str):
    try:
        payload = jwt.decode(token, secret_key_change_pass, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except jwt.ExpiredSignatureError:
        return None
    except jwt.DecodeError:
        return None