RESERVATION = {
    "guest_name": "Ada Lovelace",
    "property_id": "prop-1",
    "check_in": "2026-09-01T15:00:00Z",
    "check_out": "2026-09-05T11:00:00Z",
}


def test_create_and_get_reservation(client):
    created = client.post("/reservations", json=RESERVATION)
    assert created.status_code == 201
    assert created.json()["status"] == "pending"

    fetched = client.get(f"/reservations/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["guest_name"] == "Ada Lovelace"


def test_list_reservations_empty(client):
    response = client.get("/reservations")
    assert response.status_code == 200
    assert response.json() == []


def test_update_status(client):
    created = client.post("/reservations", json=RESERVATION).json()

    response = client.patch(
        f"/reservations/{created['id']}", json={"status": "confirmed"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_delete_reservation(client):
    created = client.post("/reservations", json=RESERVATION).json()

    response = client.delete(f"/reservations/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/reservations/{created['id']}").status_code == 404


def test_get_missing_reservation_returns_404(client):
    response = client.get("/reservations/999")
    assert response.status_code == 404
