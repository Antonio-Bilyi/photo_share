import os

# Змінні середовища потрібно задати ДО імпорту застосунку: модулі читають їх під час імпорту
# (ключ JWT, налаштування пошти та Cloudinary). Значення примусові, тож тести не залежать
# від твого справжнього .env і ніколи не торкаються реальної бази чи сервісів.
os.environ.update({
    'POSTGRES_USER': 'test',
    'POSTGRES_PASSWORD': 'test',
    'POSTGRES_DB': 'test',
    'POSTGRES_HOST': 'localhost',
    'POSTGRES_PORT': '5432',
    'SECRET_KEY': 'test-secret-key',
    'ALGORITHM': 'HS256',
    'MAIL_USERNAME': 'test',
    'MAIL_PASSWORD': 'test',
    'MAIL_FROM': 'test@example.com',
    'MAIL_PORT': '465',
    'MAIL_SERVER': 'localhost',
    'MAIL_FROM_NAME': 'PhotoShare Tests',
    'CLOUD_NAME': 'test-cloud',
    'CLOUD_KEY': 'test-key',
    'CLOUD_SECRET': 'test-secret',
})

import io
import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.cloudinary_service as cloudinary_service
from app.authorize import Hash
from app.database.connect_to_db import db_connect
from app.database.models import Base, Role, User
from main import app

PASSWORD = 'secret123'

# Мінімальна вартість bcrypt, щоб хешування паролів не сповільнювало тести (лише в тестах)
Hash.pwd_context = CryptContext(schemes=['bcrypt'], bcrypt__rounds=4)


# ---------------------------------------------------------------- допоміжні функції

def png_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    """Справжнє мініатюрне PNG-зображення, яке проходить перевірку validate_image."""
    buffer = io.BytesIO()
    Image.new('RGB', size, 'red').save(buffer, format='PNG')
    return buffer.getvalue()


def image_bytes(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), 'blue').save(buffer, format=fmt)
    return buffer.getvalue()


@dataclass
class Account:
    username: str
    id: int
    headers: dict


# ---------------------------------------------------------------- база даних

@pytest.fixture()
def session_factory():
    """Чиста in-memory SQLite база для кожного тесту (PostgreSQL для тестів не потрібен)."""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

    Base.metadata.create_all(engine)

    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_db_connect():
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[db_connect] = override_db_connect

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------- підміна зовнішніх сервісів

@pytest.fixture(autouse=True)
def sent_emails(monkeypatch):
    """Листи не відправляються, а лише записуються в список."""
    sent = []

    async def fake_send_email(email, username, host):
        sent.append({'email': email, 'username': username, 'host': host})

    monkeypatch.setattr('app.repository.users.send_email', fake_send_email)
    return sent


class FakeCloud:
    def __init__(self):
        self.uploaded = []
        self.deleted = []


@pytest.fixture(autouse=True)
def cloud(monkeypatch):
    """Cloudinary підмінено: завантаження і видалення записуються, мережа не використовується.
    Побудова трансформованих URL (transform) лишається справжньою: вона працює без мережі."""
    fake = FakeCloud()

    def fake_upload(user_id, file):
        file.seek(0)
        data = file.read()
        public_id = f'PhotoShare/{user_id}/{uuid.uuid4().hex}'
        fake.uploaded.append({'public_id': public_id, 'size': len(data)})
        return f'https://res.cloudinary.com/test-cloud/image/upload/{public_id}', public_id

    def fake_delete(public_id):
        fake.deleted.append(public_id)
        return True

    monkeypatch.setattr(cloudinary_service, 'upload', fake_upload)
    monkeypatch.setattr(cloudinary_service, 'delete', fake_delete)
    return fake


# ---------------------------------------------------------------- користувачі

@pytest.fixture()
def make_user(client, session_factory):
    """Реєструє користувача через API, підтверджує email напряму в БД і логінить його."""

    def _make(username: str, role: Role | None = None) -> Account:
        response = client.post('/api/users/signup', json={
            'username': username,
            'email': f'{username}@example.com',
            'password': PASSWORD,
        })
        assert response.status_code == 201, response.text
        user_id = response.json()['user']['id']

        with session_factory() as db:
            user = db.get(User, user_id)
            user.confirmed = True
            if role is not None:
                user.role = role
            db.commit()

        response = client.post('/api/users/login', data={'username': username, 'password': PASSWORD})
        assert response.status_code == 200, response.text
        token = response.json()['access_token']

        return Account(username, user_id, {'Authorization': f'Bearer {token}'})

    return _make


# Усі фікстури нижче залежать від admin, тому адміністратором завжди стає саме він
# (перший зареєстрований користувач).

@pytest.fixture()
def admin(make_user):
    return make_user('admin')


@pytest.fixture()
def alice(admin, make_user):
    return make_user('alice')


@pytest.fixture()
def bob(admin, make_user):
    return make_user('bob')


@pytest.fixture()
def moderator(admin, make_user):
    return make_user('moderator', role=Role.MODERATOR)


# ---------------------------------------------------------------- світлини і коментарі

@pytest.fixture()
def create_photo(client):
    def _create(account: Account, description: str = 'Test photo', tags: str | None = None) -> dict:
        data = {'description': description}
        if tags is not None:
            data['tags'] = tags

        response = client.post(
            '/api/photos/',
            headers=account.headers,
            data=data,
            files={'file': ('photo.png', png_bytes(), 'image/png')},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture()
def create_comment(client):
    def _create(account: Account, photo_id: int, text: str = 'Nice photo!') -> dict:
        response = client.post(
            f'/api/photos/{photo_id}/comments/',
            headers=account.headers,
            json={'text': text},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create
