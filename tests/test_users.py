import asyncio

import pytest

from app.authorize import create_email_token
from app.database.models import User
from tests.conftest import PASSWORD

SIGNUP_URL = '/api/users/signup'
LOGIN_URL = '/api/users/login'
ME_URL = '/api/users/me'
REFRESH_URL = '/api/users/refresh_token'


def signup(client, username='anton', email=None, password=PASSWORD):
    return client.post(SIGNUP_URL, json={
        'username': username,
        'email': email or f'{username}@example.com',
        'password': password,
    })


def confirm(session_factory, username):
    with session_factory() as db:
        db.query(User).filter(User.username == username).update({'confirmed': True})
        db.commit()


def login(client, username='anton', password=PASSWORD):
    return client.post(LOGIN_URL, data={'username': username, 'password': password})


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


# ---------------------------------------------------------------- реєстрація

def test_first_user_becomes_admin_next_users_are_regular(client):
    first = signup(client, 'first')
    second = signup(client, 'second')

    assert first.status_code == 201
    assert first.json()['user']['role'] == 'admin'
    assert second.status_code == 201
    assert second.json()['user']['role'] == 'user'


def test_signup_response_has_no_password_and_user_is_unconfirmed(client):
    response = signup(client)

    user = response.json()['user']
    assert 'password' not in user
    assert user['username'] == 'anton'
    assert user['email'] == 'anton@example.com'
    assert user['confirmed'] is False
    assert response.json()['detail']


def test_signup_sends_confirmation_email(client, sent_emails):
    signup(client)

    assert len(sent_emails) == 1
    assert sent_emails[0]['email'] == 'anton@example.com'
    assert sent_emails[0]['username'] == 'anton'


def test_password_is_stored_hashed(client, session_factory):
    signup(client)

    with session_factory() as db:
        user = db.query(User).filter(User.username == 'anton').first()

    assert user.password != PASSWORD
    assert user.password.startswith('$2')


def test_signup_duplicate_username_returns_409(client):
    signup(client, 'anton', 'one@example.com')

    response = signup(client, 'anton', 'two@example.com')

    assert response.status_code == 409


def test_signup_duplicate_email_returns_409(client):
    signup(client, 'one', 'same@example.com')

    response = signup(client, 'two', 'same@example.com')

    assert response.status_code == 409


@pytest.mark.parametrize('payload', [
    {'username': 'a', 'email': 'a@example.com', 'password': PASSWORD},          # коротке ім'я
    {'username': 'anton', 'email': 'not-an-email', 'password': PASSWORD},       # некоректний email
    {'username': 'anton', 'email': 'a@example.com', 'password': '123'},         # короткий пароль
    {'username': 'anton', 'email': 'a@example.com'},                            # немає пароля
])
def test_signup_validation_errors_return_422(client, payload):
    response = client.post(SIGNUP_URL, json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------- логін

def test_login_before_email_confirmation_returns_401(client):
    signup(client)

    response = login(client)

    assert response.status_code == 401


def test_login_after_confirmation_returns_tokens(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body['token_type'] == 'bearer'
    assert body['access_token']
    assert body['refresh_token']


def test_login_wrong_password_returns_401(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')

    response = login(client, password='wrong-password')

    assert response.status_code == 401


def test_login_unknown_user_returns_401(client):
    response = login(client, username='nobody')

    assert response.status_code == 401


def test_login_saves_refresh_token_in_database(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')

    tokens = login(client).json()

    with session_factory() as db:
        user = db.query(User).filter(User.username == 'anton').first()
    assert user.refresh_token == tokens['refresh_token']


# ---------------------------------------------------------------- /me

def test_me_requires_token(client):
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_returns_current_user(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    token = login(client).json()['access_token']

    response = client.get(ME_URL, headers=bearer(token))

    assert response.status_code == 200
    assert response.json()['username'] == 'anton'


def test_me_rejects_garbage_token(client):
    response = client.get(ME_URL, headers=bearer('not.a.token'))

    assert response.status_code == 401


def test_me_rejects_refresh_token_used_as_access_token(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    refresh_token = login(client).json()['refresh_token']

    response = client.get(ME_URL, headers=bearer(refresh_token))

    assert response.status_code == 401


def test_me_rejects_email_token_used_as_access_token(client):
    signup(client)
    email_token = asyncio.run(create_email_token({'sub': 'anton@example.com'}))

    response = client.get(ME_URL, headers=bearer(email_token))

    assert response.status_code == 401


# ---------------------------------------------------------------- оновлення токенів

def test_refresh_token_returns_new_pair(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    tokens = login(client).json()

    response = client.post(REFRESH_URL, headers=bearer(tokens['refresh_token']))

    assert response.status_code == 200
    body = response.json()
    assert body['access_token']
    assert body['refresh_token']

    # новий access-токен справді працює
    me = client.get(ME_URL, headers=bearer(body['access_token']))
    assert me.status_code == 200


def test_refresh_rejects_access_token(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    access_token = login(client).json()['access_token']

    response = client.post(REFRESH_URL, headers=bearer(access_token))

    assert response.status_code == 401


def test_refresh_requires_token(client):
    response = client.post(REFRESH_URL)

    assert response.status_code in (401, 403)


def test_refresh_with_token_that_does_not_match_stored_one_is_rejected(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    tokens = login(client).json()

    # імітуємо ситуацію, коли в БД уже інший refresh-токен (наприклад, користувач увійшов деінде)
    with session_factory() as db:
        db.query(User).filter(User.username == 'anton').update({'refresh_token': 'another-token'})
        db.commit()

    response = client.post(REFRESH_URL, headers=bearer(tokens['refresh_token']))

    assert response.status_code == 401
    with session_factory() as db:
        user = db.query(User).filter(User.username == 'anton').first()
    assert user.refresh_token is None


# ---------------------------------------------------------------- підтвердження email

def test_confirm_email_with_valid_token(client, session_factory):
    signup(client)
    token = asyncio.run(create_email_token({'sub': 'anton@example.com'}))

    response = client.get(f'/api/users/confirmed_email/{token}')

    assert response.status_code == 200
    with session_factory() as db:
        user = db.query(User).filter(User.username == 'anton').first()
    assert user.confirmed is True


def test_confirm_email_twice_reports_already_confirmed(client):
    signup(client)
    token = asyncio.run(create_email_token({'sub': 'anton@example.com'}))
    client.get(f'/api/users/confirmed_email/{token}')

    response = client.get(f'/api/users/confirmed_email/{token}')

    assert response.status_code == 200
    assert 'already' in response.json()['message'].lower()


def test_confirm_email_for_unknown_user_returns_401(client):
    token = asyncio.run(create_email_token({'sub': 'ghost@example.com'}))

    response = client.get(f'/api/users/confirmed_email/{token}')

    assert response.status_code == 401


def test_confirm_email_rejects_access_token(client, session_factory):
    signup(client)
    confirm(session_factory, 'anton')
    access_token = login(client).json()['access_token']

    response = client.get(f'/api/users/confirmed_email/{access_token}')

    assert response.status_code == 401


def test_confirm_email_rejects_garbage_token(client):
    response = client.get('/api/users/confirmed_email/garbage')

    assert response.status_code == 422
