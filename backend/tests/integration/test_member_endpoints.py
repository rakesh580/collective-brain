"""Integration tests for member management endpoints."""


class TestMemberCRUD:
    def test_create_member(self, app_client, auth_headers):
        resp = app_client.post(
            "/members",
            headers=auth_headers,
            json={
                "name": "Dave",
                "email": "dave@company.com",
                "expertise_tags": ["python", "ml"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Dave"

    def test_list_members(self, app_client, auth_headers):
        # Create two members
        app_client.post("/members", headers=auth_headers, json={"name": "Eve"})
        app_client.post("/members", headers=auth_headers, json={"name": "Frank"})
        resp = app_client.get("/members", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_member_detail(self, app_client, auth_headers):
        create = app_client.post(
            "/members",
            headers=auth_headers,
            json={
                "name": "Grace",
                "expertise_tags": ["react"],
            },
        )
        member_id = create.json()["id"]
        resp = app_client.get(f"/members/{member_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Grace"

    def test_update_member(self, app_client, auth_headers):
        create = app_client.post("/members", headers=auth_headers, json={"name": "Hank"})
        member_id = create.json()["id"]
        resp = app_client.put(
            f"/members/{member_id}",
            headers=auth_headers,
            json={
                "name": "Hank Updated",
                "expertise_tags": ["devops", "k8s"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Hank Updated"

    def test_delete_member(self, app_client, auth_headers):
        create = app_client.post("/members", headers=auth_headers, json={"name": "Temp"})
        member_id = create.json()["id"]
        resp = app_client.delete(f"/members/{member_id}", headers=auth_headers)
        assert resp.status_code == 200

        # Verify deleted
        resp = app_client.get(f"/members/{member_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_nonexistent_member(self, app_client, auth_headers):
        resp = app_client.get("/members/does-not-exist", headers=auth_headers)
        assert resp.status_code == 404


class TestMemberAliases:
    def test_set_aliases(self, app_client, auth_headers):
        create = app_client.post("/members", headers=auth_headers, json={"name": "Ivy"})
        member_id = create.json()["id"]
        resp = app_client.put(
            f"/members/{member_id}/aliases",
            headers=auth_headers,
            json={"aliases": ["ivy", "ivy.g@corp.com"]},
        )
        assert resp.status_code == 200
        assert "ivy" in resp.json()["aliases"]


class TestMemberContributions:
    def test_list_contributions_empty(self, app_client, auth_headers):
        create = app_client.post("/members", headers=auth_headers, json={"name": "Newbie"})
        member_id = create.json()["id"]
        resp = app_client.get(f"/members/{member_id}/contributions", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 0


class TestMemberAuth:
    def test_members_require_auth(self, app_client):
        resp = app_client.get("/members")
        assert resp.status_code == 401

    def test_create_member_requires_auth(self, app_client):
        resp = app_client.post("/members", json={"name": "Unauthorized"})
        assert resp.status_code == 401
