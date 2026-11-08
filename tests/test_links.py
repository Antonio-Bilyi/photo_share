import base64

import pytest

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def create_link(client, account, photo_id, params):
    return client.post(f'/api/photos/{photo_id}/links', headers=account.headers if account else {}, json=params)


# ---------------------------------------------------------------- створення посилання

def test_create_link_returns_url_and_qr_code(client, alice, create_photo):
    photo = create_photo(alice)

    response = create_link(client, alice, photo['id'], {'effect': 'sepia'})

    assert response.status_code == 201
    body = response.json()
    link = body['link']
    assert link['photo_id'] == photo['id']
    assert link['params'] == {'effect': 'sepia'}
    assert link['url'].startswith('https://')
    assert 'e_sepia' in link['url']
    assert base64.b64decode(body['qr_code']).startswith(PNG_SIGNATURE)


@pytest.mark.parametrize('params, expected_fragments', [
    ({'width': 300, 'height': 300, 'crop': 'fill'}, ['c_fill', 'w_300', 'h_300']),
    ({'width': 300, 'crop': 'fit'}, ['c_fit', 'w_300']),
    ({'angle': 90}, ['a_90']),
    ({'effect': 'grayscale'}, ['e_grayscale']),
    ({'effect': 'blur:300'}, ['e_blur']),
    ({'radius': 20}, ['r_20']),
])
def test_transformation_parameters_end_up_in_the_url(client, alice, create_photo, params, expected_fragments):
    photo = create_photo(alice)

    response = create_link(client, alice, photo['id'], params)

    assert response.status_code == 201
    url = response.json()['link']['url']
    for fragment in expected_fragments:
        assert fragment in url


def test_link_url_points_to_the_photo_in_cloud(client, alice, cloud, create_photo):
    photo = create_photo(alice)
    public_id = cloud.uploaded[0]['public_id']

    response = create_link(client, alice, photo['id'], {'effect': 'sepia'})

    assert public_id in response.json()['link']['url']


@pytest.mark.parametrize('params', [
    {},                                          # немає жодного параметра
    {'crop': 'fill'},                            # crop без розмірів
    {'crop': 'fill', 'angle': 90},               # crop без розмірів, хоч є інший параметр
    {'crop': 'fill', 'width': 300},              # для fill потрібні обидва розміри
    {'crop': 'thumb', 'height': 300},            # для thumb теж
    {'width': 5000},                             # більше за максимум
    {'width': 0},                                # менше за мінімум
    {'angle': 45},                               # недозволений кут
    {'effect': 'invert'},                        # недозволений ефект
    {'radius': 501},                             # більше за максимум
    {'foo': 1},                                  # зайве поле
    {'effect': 'sepia', 'foo': 1},               # зайве поле разом із валідним
])
def test_invalid_transformation_parameters_return_422(client, alice, create_photo, params):
    photo = create_photo(alice)

    response = create_link(client, alice, photo['id'], params)

    assert response.status_code == 422


def test_create_link_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = create_link(client, None, photo['id'], {'effect': 'sepia'})

    assert response.status_code == 401


def test_create_link_for_unknown_photo_returns_404(client, alice):
    response = create_link(client, alice, 9999, {'effect': 'sepia'})

    assert response.status_code == 404


def test_other_user_cannot_create_link(client, alice, bob, create_photo):
    photo = create_photo(alice)

    response = create_link(client, bob, photo['id'], {'effect': 'sepia'})

    assert response.status_code == 403


def test_admin_can_create_link_for_someone_elses_photo(client, admin, alice, create_photo):
    photo = create_photo(alice)

    response = create_link(client, admin, photo['id'], {'effect': 'sepia'})

    assert response.status_code == 201


# ---------------------------------------------------------------- QR-код

def test_qr_endpoint_returns_png_image(client, alice, create_photo):
    photo = create_photo(alice)
    link = create_link(client, alice, photo['id'], {'effect': 'sepia'}).json()['link']

    response = client.get(f'/api/photos/{photo["id"]}/links/{link["id"]}/qr', headers=alice.headers)

    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'
    assert response.content.startswith(PNG_SIGNATURE)


def test_any_authenticated_user_can_get_qr(client, alice, bob, create_photo):
    photo = create_photo(alice)
    link = create_link(client, alice, photo['id'], {'effect': 'sepia'}).json()['link']

    response = client.get(f'/api/photos/{photo["id"]}/links/{link["id"]}/qr', headers=bob.headers)

    assert response.status_code == 200


def test_qr_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)
    link = create_link(client, alice, photo['id'], {'effect': 'sepia'}).json()['link']

    response = client.get(f'/api/photos/{photo["id"]}/links/{link["id"]}/qr')

    assert response.status_code == 401


def test_qr_for_unknown_link_returns_404(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.get(f'/api/photos/{photo["id"]}/links/9999/qr', headers=alice.headers)

    assert response.status_code == 404


def test_qr_of_link_from_another_photo_returns_404(client, alice, create_photo):
    first = create_photo(alice)
    second = create_photo(alice)
    link = create_link(client, alice, first['id'], {'effect': 'sepia'}).json()['link']

    response = client.get(f'/api/photos/{second["id"]}/links/{link["id"]}/qr', headers=alice.headers)

    assert response.status_code == 404


# ---------------------------------------------------------------- список посилань

def test_list_links_requires_authentication(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.get(f'/api/photos/{photo["id"]}/links')

    assert response.status_code == 401


def test_list_links_of_unknown_photo_returns_404(client, alice):
    response = client.get('/api/photos/9999/links', headers=alice.headers)

    assert response.status_code == 404


def test_list_links_returns_only_links_of_this_photo(client, alice, create_photo):
    first = create_photo(alice)
    second = create_photo(alice)
    first_link = create_link(client, alice, first['id'], {'effect': 'sepia'}).json()['link']
    second_link = create_link(client, alice, first['id'], {'angle': 90}).json()['link']
    create_link(client, alice, second['id'], {'effect': 'grayscale'})

    response = client.get(f'/api/photos/{first["id"]}/links', headers=alice.headers)

    assert response.status_code == 200
    assert {link['id'] for link in response.json()} == {first_link['id'], second_link['id']}


def test_list_links_is_empty_for_photo_without_links(client, alice, create_photo):
    photo = create_photo(alice)

    response = client.get(f'/api/photos/{photo["id"]}/links', headers=alice.headers)

    assert response.status_code == 200
    assert response.json() == []


def test_any_authenticated_user_can_list_links(client, alice, bob, create_photo):
    # Правило «список бачить будь-який авторизований користувач».
    # Якщо ментор вимагатиме «лише власник або admin», зміни очікуваний код на 403.
    photo = create_photo(alice)
    create_link(client, alice, photo['id'], {'effect': 'sepia'})

    response = client.get(f'/api/photos/{photo["id"]}/links', headers=bob.headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
