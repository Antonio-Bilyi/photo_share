from pathlib import Path
import os
from dotenv import load_dotenv

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors

from pydantic import EmailStr

from app.authorize import create_email_token

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

configurations = ConnectionConfig(
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_FROM=os.getenv('MAIL_FROM'),
    MAIL_PORT=os.getenv('MAIL_PORT'),
    MAIL_SERVER=os.getenv('MAIL_SERVER'),
    MAIL_FROM_NAME=os.getenv('MAIL_FROM_NAME'),
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent / 'templates'
)

async def send_email(email: EmailStr, username: str, host: str):
    try:
        token_verification = await create_email_token({'sub': email})

        message = MessageSchema(
            subject='Confirm your email',
            recipients=[email],
            template_body={
                'host': host,
                'username': username,
                'token': token_verification
            },
            subtype=MessageType.html
        )

        fm = FastMail(configurations)

        await fm.send_message(message, template_name='email_template.html')
    except ConnectionErrors as err:
        print(err)