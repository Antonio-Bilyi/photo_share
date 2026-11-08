from datetime import datetime

import pytest

from app.database.models import Comment


def comments_url(photo_id, comment_id=None):
    base = f'/api/photos/{photo_id}/comments/'
    return base if comment_id is None else f'{base}{comment_id}'


def count_comments(session_factory):
    with session_factory() as db:
        return db.query(Comment).count()


# ---------------------------------------------------------------- створення

def test_user_can_comment_someone_elses_photo(client, alice, bob, create_photo):
    photo = create_photo(alice)

    response = client.post(comments_url(photo['id']), headers=bob.headers, json={'text': 'Nice!'})

    assert response.status_code == 201
    body = response.json()
    assert body['text'] == 'Nice!'
    assert body['user_id'] == bob.id
    assert body['photo_id'] == photo['id']
    assert body['created_at']
    assert body['updated_at']


def test_author_can_comment_own_photo(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.post(comments_url(photo['id']), headers=alice.headers, json={'text': 'Mine'})

    assert response.status_code == 201


def test_comment_text_is_stripped(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.post(comments_url(photo['id']), headers=alice.headers, json={'text': '  Hello  '})

    assert response.json()['text'] == 'Hello'


def test_create_comment_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.post(comments_url(photo['id']), json={'text': 'Nice!'})

    assert response.status_code == 401


def test_create_comment_for_unknown_photo_returns_404(client, alice):
    response = client.post(comments_url(9999), headers=alice.headers, json={'text': 'Nice!'})

    assert response.status_code == 404


@pytest.mark.parametrize('payload', [{'text': ''}, {'text': '   '}, {'text': 'x' * 501}, {}])
def test_create_comment_with_invalid_text_returns_422(client, alice, create_photo, payload):
    photo = create_photo(alice)

    response = client.post(comments_url(photo['id']), headers=alice.headers, json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------- список

def test_list_comments_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.get(comments_url(photo['id']))

    assert response.status_code == 401


def test_list_comments_of_unknown_photo_returns_404(client, alice):
    response = client.get(comments_url(9999), headers=alice.headers)

    assert response.status_code == 404


def test_list_comments_returns_only_comments_of_this_photo(client, alice, bob, create_photo, create_comment):
    first = create_photo(alice)
    second = create_photo(alice)
    create_comment(bob, first['id'], 'on first')
    create_comment(bob, second['id'], 'on second')

    response = client.get(comments_url(first['id']), headers=alice.headers)

    assert response.status_code == 200
    assert [comment['text'] for comment in response.json()] == ['on first']


@pytest.fixture()
def three_ordered_comments(client, alice, bob, create_photo, create_comment, session_factory):
    """Три коментарі з чітко різним часом створення (SQLite зберігає час із точністю до секунди,
    тому для надійного порядку виставляємо created_at вручну)."""
    photo = create_photo(alice)
    ids = [create_comment(bob, photo['id'], text)['id'] for text in ('first', 'second', 'third')]

    with session_factory() as db:
        for minute, comment_id in enumerate(ids):
            db.query(Comment).filter(Comment.id == comment_id).update({'created_at': datetime(2026, 1, 1, 12, minute)})
        db.commit()

    return photo


def test_comments_are_listed_from_oldest_to_newest(client, alice, three_ordered_comments):
    response = client.get(comments_url(three_ordered_comments['id']), headers=alice.headers)

    assert [comment['text'] for comment in response.json()] == ['first', 'second', 'third']


def test_comments_pagination(client, alice, three_ordered_comments):
    url = comments_url(three_ordered_comments['id'])

    limited = client.get(url, headers=alice.headers, params={'limit': 2}).json()
    skipped = client.get(url, headers=alice.headers, params={'skip': 2}).json()

    assert [comment['text'] for comment in limited] == ['first', 'second']
    assert [comment['text'] for comment in skipped] == ['third']


@pytest.mark.parametrize('params', [{'limit': 0}, {'limit': 101}, {'skip': -1}])
def test_invalid_pagination_returns_422(client, alice, create_photo, params):
    photo = create_photo(alice)

    response = client.get(comments_url(photo['id']), headers=alice.headers, params=params)

    assert response.status_code == 422


# ---------------------------------------------------------------- редагування (лише автор)

def test_author_can_edit_own_comment(client, alice, bob, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'], 'Old')

    response = client.put(comments_url(photo['id'], comment['id']), headers=bob.headers, json={'text': 'New'})

    assert response.status_code == 200
    assert response.json()['text'] == 'New'
    assert response.json()['updated_at']


def test_other_user_cannot_edit_comment(client, alice, bob, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'], 'Old')

    response = client.put(comments_url(photo['id'], comment['id']), headers=alice.headers, json={'text': 'Hacked'})

    assert response.status_code == 403
    texts = [c['text'] for c in client.get(comments_url(photo['id']), headers=bob.headers).json()]
    assert texts == ['Old']


def test_admin_cannot_edit_someone_elses_comment(client, admin, alice, bob, create_photo, create_comment):
    # За ТЗ адміністратори й модератори коментарі лише видаляють, але не редагують.
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'], 'Old')

    response = client.put(comments_url(photo['id'], comment['id']), headers=admin.headers, json={'text': 'By admin'})

    assert response.status_code == 403


def test_moderator_cannot_edit_someone_elses_comment(client, alice, bob, moderator, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'], 'Old')

    response = client.put(comments_url(photo['id'], comment['id']), headers=moderator.headers, json={'text': 'Nope'})

    assert response.status_code == 403


def test_edit_unknown_comment_returns_404(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.put(comments_url(photo['id'], 9999), headers=alice.headers, json={'text': 'New'})

    assert response.status_code == 404


def test_edit_comment_through_another_photo_returns_404(client, alice, bob, create_photo, create_comment):
    first = create_photo(alice)
    second = create_photo(alice)
    comment = create_comment(bob, first['id'])

    response = client.put(comments_url(second['id'], comment['id']), headers=bob.headers, json={'text': 'New'})

    assert response.status_code == 404


def test_edit_comment_requires_authentication(client, alice, bob, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.put(comments_url(photo['id'], comment['id']), json={'text': 'New'})

    assert response.status_code == 401


@pytest.mark.parametrize('payload', [{'text': ''}, {'text': '   '}, {'text': 'x' * 501}])
def test_edit_comment_with_invalid_text_returns_422(client, alice, bob, create_photo, create_comment, payload):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.put(comments_url(photo['id'], comment['id']), headers=bob.headers, json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------- видалення (admin і moderator)

def test_author_with_user_role_cannot_delete_own_comment(client, alice, bob, create_photo, create_comment, session_factory):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=bob.headers)

    assert response.status_code == 403
    assert count_comments(session_factory) == 1


def test_refusal_to_delete_explains_who_is_allowed(client, alice, bob, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=bob.headers)

    message = response.json()['detail'].lower()
    assert 'moderator' in message
    assert 'administrator' in message


def test_other_regular_user_cannot_delete_comment(client, alice, bob, create_photo, create_comment, session_factory):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=alice.headers)

    assert response.status_code == 403
    assert count_comments(session_factory) == 1


def test_photo_owner_with_user_role_cannot_delete_comment_under_own_photo(
    client, alice, bob, create_photo, create_comment, session_factory
):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=alice.headers)

    assert response.status_code == 403
    assert count_comments(session_factory) == 1


def test_moderator_can_delete_any_comment(client, alice, bob, moderator, create_photo, create_comment, session_factory):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=moderator.headers)

    assert response.status_code == 204
    assert count_comments(session_factory) == 0


def test_admin_can_delete_any_comment(client, admin, alice, bob, create_photo, create_comment, session_factory):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']), headers=admin.headers)

    assert response.status_code == 204
    assert count_comments(session_factory) == 0


def test_moderator_and_admin_can_delete_their_own_comments(
    client, admin, alice, moderator, create_photo, create_comment, session_factory
):
    # Обмеження «автор не видаляє» стосується лише ролі user:
    # модератор і адміністратор видаляють коментарі за роллю, зокрема власні.
    photo = create_photo(alice)
    by_moderator = create_comment(moderator, photo['id'], 'moderator says')
    by_admin = create_comment(admin, photo['id'], 'admin says')

    first = client.delete(comments_url(photo['id'], by_moderator['id']), headers=moderator.headers)
    second = client.delete(comments_url(photo['id'], by_admin['id']), headers=admin.headers)

    assert first.status_code == 204
    assert second.status_code == 204
    assert count_comments(session_factory) == 0


def test_delete_unknown_comment_as_moderator_returns_404(client, alice, moderator, create_photo):
    photo = create_photo(alice)

    response = client.delete(comments_url(photo['id'], 9999), headers=moderator.headers)

    assert response.status_code == 404


def test_delete_comment_through_another_photo_returns_404(client, alice, bob, moderator, create_photo, create_comment):
    first = create_photo(alice)
    second = create_photo(alice)
    comment = create_comment(bob, first['id'])

    response = client.delete(comments_url(second['id'], comment['id']), headers=moderator.headers)

    assert response.status_code == 404


def test_delete_comment_requires_authentication(client, alice, bob, create_photo, create_comment):
    photo = create_photo(alice)
    comment = create_comment(bob, photo['id'])

    response = client.delete(comments_url(photo['id'], comment['id']))

    assert response.status_code == 401


def test_regular_user_gets_403_even_for_unknown_comment(client, alice, create_photo):
    # Роль перевіряється раніше за пошук коментаря, тож user отримує 403, а не 404.
    photo = create_photo(alice)

    response = client.delete(comments_url(photo['id'], 9999), headers=alice.headers)

    assert response.status_code == 403
