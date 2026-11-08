import pytest
from sqlalchemy.exc import SQLAlchemyError

import app.repository.photos as repository_photos
from app.database.models import Comment, PhotoLink, Tag
from tests.conftest import image_bytes, png_bytes

PHOTOS_URL = '/api/photos/'


def upload(client, account, *, description='Test photo', tags=None, content=None,
           content_type='image/png', filename='photo.png', send_file=True):
    data = {}
    if description is not None:
        data['description'] = description
    if tags is not None:
        data['tags'] = tags

    files = {}
    if send_file:
        files['file'] = (filename, png_bytes() if content is None else content, content_type)

    return client.post(PHOTOS_URL, headers=account.headers if account else {}, data=data, files=files or None)


# ---------------------------------------------------------------- завантаження

def test_upload_requires_authentication(client):
    response = upload(client, None)

    assert response.status_code == 401


def test_upload_photo_with_tags(client, alice, cloud):
    response = upload(client, alice, description='Sunset', tags='Sunset, sea, #Sunset')

    assert response.status_code == 201
    body = response.json()
    assert body['description'] == 'Sunset'
    assert body['user_id'] == alice.id
    assert body['url'].startswith('https://')
    # теги в нижньому регістрі, без дублікатів і без решітки
    assert [tag['name'] for tag in body['tags']] == ['sunset', 'sea']
    assert len(cloud.uploaded) == 1


def test_upload_passes_non_empty_file_to_cloud(client, alice, cloud):
    # перевіряє, що після validate_image вказівник файлу повернуто на початок
    upload(client, alice)

    assert cloud.uploaded[0]['size'] > 0


def test_upload_without_tags_returns_empty_tags(client, alice):
    response = upload(client, alice)

    assert response.status_code == 201
    assert response.json()['tags'] == []


def test_upload_with_five_tags_is_allowed(client, alice):
    response = upload(client, alice, tags='a, b, c, d, e')

    assert response.status_code == 201
    assert len(response.json()['tags']) == 5


def test_upload_with_more_than_five_tags_is_rejected_before_cloud(client, alice, cloud):
    response = upload(client, alice, tags='a, b, c, d, e, f')

    assert response.status_code == 400
    assert cloud.uploaded == []


def test_duplicate_tags_do_not_count_towards_the_limit(client, alice):
    response = upload(client, alice, tags='a, A, b, c, d, e')

    assert response.status_code == 201
    assert len(response.json()['tags']) == 5


@pytest.mark.parametrize('tags', ['x' * 26, 'my tag', 'cat!', 'a,b$'])
def test_upload_with_invalid_tag_is_rejected(client, alice, cloud, tags):
    response = upload(client, alice, tags=tags)

    assert response.status_code == 400
    assert cloud.uploaded == []


def test_tags_are_shared_between_photos(client, alice, bob, session_factory):
    first = upload(client, alice, tags='cat, dog').json()
    second = upload(client, bob, tags='dog, bird').json()

    first_ids = {tag['name']: tag['id'] for tag in first['tags']}
    second_ids = {tag['name']: tag['id'] for tag in second['tags']}
    assert first_ids['dog'] == second_ids['dog']

    with session_factory() as db:
        assert db.query(Tag).count() == 3


@pytest.mark.parametrize('description', ['', None])
def test_upload_requires_description(client, alice, cloud, description):
    response = upload(client, alice, description=description)

    assert response.status_code == 422
    assert cloud.uploaded == []


def test_upload_requires_file(client, alice):
    response = upload(client, alice, send_file=False)

    assert response.status_code == 422


def test_upload_rejects_unsupported_content_type(client, alice, cloud):
    response = upload(client, alice, content=b'hello', content_type='text/plain', filename='a.txt')

    assert response.status_code == 415
    assert cloud.uploaded == []


def test_upload_rejects_fake_image(client, alice, cloud):
    response = upload(client, alice, content=b'this is not an image', content_type='image/png')

    assert response.status_code == 400
    assert cloud.uploaded == []


def test_upload_rejects_real_gif_disguised_as_png(client, alice, cloud):
    response = upload(client, alice, content=image_bytes('GIF'), content_type='image/png')

    assert response.status_code == 415
    assert cloud.uploaded == []


@pytest.mark.parametrize('fmt, content_type', [('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')])
def test_upload_accepts_jpeg_and_webp(client, alice, fmt, content_type):
    response = upload(client, alice, content=image_bytes(fmt), content_type=content_type)

    assert response.status_code == 201


def test_upload_rejects_empty_file(client, alice, cloud):
    response = upload(client, alice, content=b'')

    assert response.status_code == 400
    assert cloud.uploaded == []


def test_upload_rejects_file_larger_than_limit(client, alice, cloud):
    response = upload(client, alice, content=b'0' * (5 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert cloud.uploaded == []


def test_failed_database_save_removes_uploaded_file_from_cloud(client, alice, cloud, monkeypatch):
    async def broken_create_photo(*args, **kwargs):
        raise SQLAlchemyError('database is down')

    monkeypatch.setattr(repository_photos, 'create_photo', broken_create_photo)

    response = upload(client, alice)

    assert response.status_code == 500
    assert len(cloud.uploaded) == 1
    assert cloud.deleted == [cloud.uploaded[0]['public_id']]


# ---------------------------------------------------------------- перегляд

def test_get_photo_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.get(f'/api/photos/{photo["id"]}')

    assert response.status_code == 401


def test_get_photo_returns_photo(client, alice, create_photo):
    photo = create_photo(alice, 'Hello', tags='cat')

    response = client.get(f'/api/photos/{photo["id"]}', headers=alice.headers)

    assert response.status_code == 200
    assert response.json() == photo


def test_any_authenticated_user_can_view_someone_elses_photo(client, alice, bob, create_photo):
    photo = create_photo(alice)

    response = client.get(f'/api/photos/{photo["id"]}', headers=bob.headers)

    assert response.status_code == 200


def test_get_unknown_photo_returns_404(client, alice):
    response = client.get('/api/photos/9999', headers=alice.headers)

    assert response.status_code == 404


# ---------------------------------------------------------------- редагування опису

def test_owner_can_update_description(client, alice, create_photo):
    photo = create_photo(alice, 'Old')

    response = client.put(f'/api/photos/{photo["id"]}', headers=alice.headers, json={'description': 'New'})

    assert response.status_code == 200
    assert response.json()['description'] == 'New'
    stored = client.get(f'/api/photos/{photo["id"]}', headers=alice.headers).json()
    assert stored['description'] == 'New'


def test_admin_can_update_someone_elses_photo(client, admin, alice, create_photo):
    photo = create_photo(alice, 'Old')

    response = client.put(f'/api/photos/{photo["id"]}', headers=admin.headers, json={'description': 'By admin'})

    assert response.status_code == 200
    assert response.json()['description'] == 'By admin'


def test_other_user_cannot_update_photo(client, alice, bob, create_photo):
    photo = create_photo(alice, 'Old')

    response = client.put(f'/api/photos/{photo["id"]}', headers=bob.headers, json={'description': 'Hacked'})

    assert response.status_code == 403
    stored = client.get(f'/api/photos/{photo["id"]}', headers=alice.headers).json()
    assert stored['description'] == 'Old'


def test_moderator_cannot_update_someone_elses_photo(client, alice, moderator, create_photo):
    photo = create_photo(alice, 'Old')

    response = client.put(f'/api/photos/{photo["id"]}', headers=moderator.headers, json={'description': 'Nope'})

    assert response.status_code == 403


def test_update_unknown_photo_returns_404(client, alice):
    response = client.put('/api/photos/9999', headers=alice.headers, json={'description': 'New'})

    assert response.status_code == 404


def test_update_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.put(f'/api/photos/{photo["id"]}', json={'description': 'New'})

    assert response.status_code == 401


@pytest.mark.parametrize('payload', [{'description': ''}, {}, {'description': 'x' * 256}])
def test_update_with_invalid_description_returns_422(client, alice, create_photo, payload):
    photo = create_photo(alice)

    response = client.put(f'/api/photos/{photo["id"]}', headers=alice.headers, json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------- видалення

def test_owner_can_delete_photo_and_file_is_removed_from_cloud(client, alice, cloud, create_photo):
    photo = create_photo(alice)
    public_id = cloud.uploaded[0]['public_id']

    response = client.delete(f'/api/photos/{photo["id"]}', headers=alice.headers)

    assert response.status_code == 204
    assert cloud.deleted == [public_id]
    assert client.get(f'/api/photos/{photo["id"]}', headers=alice.headers).status_code == 404


def test_admin_can_delete_someone_elses_photo(client, admin, alice, create_photo):
    photo = create_photo(alice)

    response = client.delete(f'/api/photos/{photo["id"]}', headers=admin.headers)

    assert response.status_code == 204


def test_other_user_cannot_delete_photo(client, alice, bob, cloud, create_photo):
    photo = create_photo(alice)

    response = client.delete(f'/api/photos/{photo["id"]}', headers=bob.headers)

    assert response.status_code == 403
    assert cloud.deleted == []
    assert client.get(f'/api/photos/{photo["id"]}', headers=alice.headers).status_code == 200


def test_delete_unknown_photo_returns_404(client, alice):
    response = client.delete('/api/photos/9999', headers=alice.headers)

    assert response.status_code == 404


def test_delete_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.delete(f'/api/photos/{photo["id"]}')

    assert response.status_code == 401


def test_deleting_photo_removes_its_comments_and_links_but_keeps_tags(
    client, alice, bob, create_photo, create_comment, session_factory
):
    photo = create_photo(alice, tags='cat, dog')
    create_comment(bob, photo['id'])
    client.post(f'/api/photos/{photo["id"]}/links', headers=alice.headers, json={'effect': 'sepia'})

    client.delete(f'/api/photos/{photo["id"]}', headers=alice.headers)

    with session_factory() as db:
        assert db.query(Comment).count() == 0
        assert db.query(PhotoLink).count() == 0
        assert db.query(Tag).count() == 2
