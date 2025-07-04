import smtplib
import asyncio
from email.message import EmailMessage
from Const.const import email_name, email_password

SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 587  # Если используешь SSL, поменяй на 465
SMTP_USER = email_name
SMTP_PASSWORD = email_password

async def send_activation_email(email: str, token: str):
    msg = EmailMessage()
    msg["Subject"] = "Activate your account"
    msg["From"] = f"{SMTP_USER}@yandex.ru"
    msg["To"] = email
    
    activation_link = f"http://localhost:3000/activate/{token}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; text-align: center; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">Welcome to TradeSnake!</h2>
                <p>Click the button below to activate your account:</p>
                <a href="{activation_link}" style="display: inline-block; padding: 10px 20px; color: white; background: #007BFF; text-decoration: none; border-radius: 5px;">
                    Activate Account
                </a>
                <p>If the button doesn't work, use this link:</p>
                <p><a href="{activation_link}" style="word-break: break-all;">{activation_link}</a></p>
            </div>
        </body>
    </html>
    """

    msg.set_content(f"Hi! It's TradeSnake! Activate your account: {activation_link}")
    msg.add_alternative(html_content, subtype='html')

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_email_sync, msg)
    except Exception as e:
        print(f"Error for email: {e}")  # Лучше заменить на логирование

async def send_change_password_email(email: str, token: str):
    msg = EmailMessage()
    msg["Subject"] = "Change Password"
    msg["From"] = f"{SMTP_USER}@yandex.ru"
    msg["To"] = email

    reset_link = f"http://localhost:3000/change-password/{token}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; text-align: center; background-color: #f4f4f4; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333;">Reset Your Password</h2>
                <p>Click the button below to change your password:</p>
                <a href="{reset_link}" style="display: inline-block; padding: 10px 20px; color: white; background: #dc3545; text-decoration: none; border-radius: 5px;">
                    Change Password
                </a>
                <p>If the button doesn't work, use this link:</p>
                <p><a href="{reset_link}" style="word-break: break-all;">{reset_link}</a></p>
            </div>
        </body>
    </html>
    """

    msg.set_content(f"Hi! It's TradeSnake! Change your password: {reset_link}")
    msg.add_alternative(html_content, subtype='html')

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_email_sync, msg)
    except Exception as e:
        print(f"Error for email: {e}")  # Лучше заменить на логирование

def _send_email_sync(msg):
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except smtplib.SMTPException as e:
        print(f"Error for email: {e}")  # Тут можно записать в лог
