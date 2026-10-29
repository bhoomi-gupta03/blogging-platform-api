PASSWORD = "strong-password-123"


def register(client, username="writer", email="writer@example.com", password=PASSWORD):
    return client.post(
        "/auth/register", json={"username": username, "email": email, "password": password}
    )


def login(client, username="writer", password=PASSWORD) -> str:
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
