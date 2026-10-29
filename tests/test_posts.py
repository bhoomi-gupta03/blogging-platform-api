import pytest

from tests.helpers import auth_header


def create_post(client, headers, title="My post", content="Some content"):
    return client.post("/posts", headers=headers, json={"title": title, "content": content})


# ---------- create ----------
def test_authenticated_user_can_create_post(client, make_user):
    headers = make_user("writer")
    response = create_post(client, headers)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "My post" and body["content"] == "Some content"
    assert body["id"] and body["created_at"] and body["updated_at"]


def test_create_requires_authentication(client):
    response = client.post("/posts", json={"title": "No auth", "content": "Rejected"})
    assert response.status_code == 401


def test_owner_id_in_request_body_is_ignored(client, make_user):
    make_user("writer_a")  # user id 1
    headers_b = make_user("writer_b")  # user id 2
    response = client.post(
        "/posts", headers=headers_b, json={"title": "t", "content": "c", "owner_id": 1}
    )
    assert response.status_code == 201
    assert response.json()["owner_id"] == 2  # taken from the token, not the body


def test_title_and_content_are_stripped(client, make_user):
    body = create_post(client, make_user(), "  Padded title  ", "  body  ").json()
    assert body["title"] == "Padded title" and body["content"] == "body"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "ok"},
        {"title": "   ", "content": "ok"},
        {"title": "ok", "content": ""},
        {"title": "ok", "content": "   "},
        {"title": "x" * 201, "content": "ok"},
        {"title": "ok", "content": "x" * 20001},
        {"title": "only title"},
        {},
    ],
)
def test_invalid_post_data_is_rejected(client, make_user, payload):
    assert client.post("/posts", headers=make_user(), json=payload).status_code == 422


# ---------- list / pagination ----------
def test_list_is_public_and_empty_at_first(client):
    response = client.get("/posts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_is_newest_first_and_paginates(client, make_user):
    headers = make_user()
    for i in range(1, 6):
        create_post(client, headers, title=f"Post {i}")

    def titles(**params):
        return [p["title"] for p in client.get("/posts", params=params).json()]

    assert titles(limit=2) == ["Post 5", "Post 4"]
    assert titles(limit=2, offset=2) == ["Post 3", "Post 2"]
    assert titles(limit=2, offset=4) == ["Post 1"]
    assert titles(offset=10) == []
    assert len(titles()) == 5  # default limit is 10


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
def test_invalid_pagination_is_rejected(client, params):
    assert client.get("/posts", params=params).status_code == 422


# ---------- retrieve ----------
def test_get_existing_post_without_login(client, make_user):
    post_id = create_post(client, make_user()).json()["id"]
    response = client.get(f"/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["id"] == post_id


def test_get_missing_post_is_404(client):
    assert client.get("/posts/999").status_code == 404


def test_get_with_invalid_id_is_422(client):
    assert client.get("/posts/abc").status_code == 422


# ---------- update ----------
def test_owner_can_update_post(client, make_user):
    headers = make_user()
    created = create_post(client, headers).json()
    response = client.put(
        f"/posts/{created['id']}", headers=headers, json={"title": "New", "content": "New body"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New" and body["content"] == "New body"
    assert body["updated_at"] >= created["updated_at"]
    assert client.get(f"/posts/{created['id']}").json()["title"] == "New"


def test_update_requires_authentication(client, make_user):
    post_id = create_post(client, make_user()).json()["id"]
    response = client.put(f"/posts/{post_id}", json={"title": "x", "content": "y"})
    assert response.status_code == 401


def test_update_missing_post_is_404(client, make_user):
    response = client.put("/posts/999", headers=make_user(), json={"title": "x", "content": "y"})
    assert response.status_code == 404


def test_update_with_invalid_or_partial_body_is_422(client, make_user):
    headers = make_user()
    post_id = create_post(client, headers).json()["id"]
    assert client.put(f"/posts/{post_id}", headers=headers, json={"title": "only"}).status_code == 422
    assert client.put(f"/posts/{post_id}", headers=headers, json={"title": "", "content": "y"}).status_code == 422


def test_user_cannot_update_another_users_post(client, make_user):
    headers_a, headers_b = make_user("writer_a"), make_user("writer_b")
    post_id = create_post(client, headers_a, title="Original").json()["id"]
    response = client.put(
        f"/posts/{post_id}", headers=headers_b, json={"title": "Hijacked", "content": "x"}
    )
    assert response.status_code == 403
    assert client.get(f"/posts/{post_id}").json()["title"] == "Original"  # unchanged


# ---------- delete ----------
def test_owner_can_delete_post(client, make_user):
    headers = make_user()
    post_id = create_post(client, headers).json()["id"]
    assert client.delete(f"/posts/{post_id}", headers=headers).status_code == 204
    assert client.get(f"/posts/{post_id}").status_code == 404


def test_delete_requires_authentication(client, make_user):
    post_id = create_post(client, make_user()).json()["id"]
    assert client.delete(f"/posts/{post_id}").status_code == 401


def test_delete_missing_post_is_404(client, make_user):
    assert client.delete("/posts/999", headers=make_user()).status_code == 404


def test_user_cannot_delete_another_users_post(client, make_user):
    headers_a, headers_b = make_user("writer_a"), make_user("writer_b")
    post_id = create_post(client, headers_a).json()["id"]
    assert client.delete(f"/posts/{post_id}", headers=headers_b).status_code == 403
    assert client.get(f"/posts/{post_id}").status_code == 200  # still there
