import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.database.models import Role
from app.services.qr import generate_qr
from app.services.roles import roles_required
from app.services.tags import parse_tags


# ---------------------------------------------------------------- parse_tags

@pytest.mark.parametrize('raw', [None, '', '   ', ',', ' , , ', '#'])
def test_parse_tags_returns_empty_list_for_empty_input(raw):
    assert parse_tags(raw) == []


@pytest.mark.parametrize('raw, expected', [
    ('cat, dog', ['cat', 'dog']),
    ('  Cat ,DOG  ', ['cat', 'dog']),
    ('#cat, # dog', ['cat', 'dog']),
    ('cat,,dog,', ['cat', 'dog']),
    ('cat, Cat, CAT', ['cat']),
    ('a,b,c,d,e', ['a', 'b', 'c', 'd', 'e']),
    ('кіт, собака', ['кіт', 'собака']),
    ('my-tag, my_tag, 2026', ['my-tag', 'my_tag', '2026']),
])
def test_parse_tags_normalizes_input(raw, expected):
    assert parse_tags(raw) == expected


def test_parse_tags_keeps_order_of_first_occurrence():
    assert parse_tags('b, a, b, c, a') == ['b', 'a', 'c']


@pytest.mark.parametrize('raw', [
    'a,b,c,d,e,f',          # більше п'яти
    'x' * 26,               # задовгий тег
    'my tag',               # пробіл усередині
    'cat!',                 # недозволений символ
    'ok, bad$tag',          # один тег некоректний
])
def test_parse_tags_rejects_invalid_input(raw):
    with pytest.raises(HTTPException) as error:
        parse_tags(raw)

    assert error.value.status_code == 400


def test_parse_tags_accepts_tag_of_maximum_length():
    assert parse_tags('x' * 25) == ['x' * 25]


# ---------------------------------------------------------------- generate_qr

def test_generate_qr_returns_png_bytes():
    data = generate_qr('https://example.com')

    assert isinstance(data, bytes)
    assert data.startswith(b'\x89PNG\r\n\x1a\n')


def test_generate_qr_handles_long_urls():
    data = generate_qr('https://res.cloudinary.com/demo/image/upload/' + 'a' * 300)

    assert data.startswith(b'\x89PNG')


# ---------------------------------------------------------------- roles_required

async def endpoint(current_user):
    return 'ok'


def call(protected, **kwargs):
    return asyncio.run(protected(**kwargs))


def user_with(role):
    return SimpleNamespace(role=role)


def test_roles_required_allows_listed_roles():
    protected = roles_required(Role.ADMIN, Role.MODERATOR)(endpoint)

    assert call(protected, current_user=user_with(Role.ADMIN)) == 'ok'
    assert call(protected, current_user=user_with(Role.MODERATOR)) == 'ok'


def test_roles_required_rejects_other_roles_with_403():
    protected = roles_required(Role.ADMIN, Role.MODERATOR)(endpoint)

    with pytest.raises(HTTPException) as error:
        call(protected, current_user=user_with(Role.USER))

    assert error.value.status_code == 403


def test_roles_required_reports_missing_current_user_parameter():
    protected = roles_required(Role.ADMIN)(endpoint)

    with pytest.raises(RuntimeError) as error:
        call(protected)

    assert 'endpoint' in str(error.value)


def test_roles_required_keeps_function_name_for_fastapi():
    protected = roles_required(Role.ADMIN)(endpoint)

    assert protected.__name__ == 'endpoint'


def test_roles_required_default_message():
    protected = roles_required(Role.ADMIN)(endpoint)

    with pytest.raises(HTTPException) as error:
        call(protected, current_user=user_with(Role.USER))

    assert error.value.detail == 'Insufficient rights'


def test_roles_required_custom_message():
    protected = roles_required(Role.ADMIN, detail='Only admins allowed')(endpoint)

    with pytest.raises(HTTPException) as error:
        call(protected, current_user=user_with(Role.USER))

    assert error.value.status_code == 403
    assert error.value.detail == 'Only admins allowed'
