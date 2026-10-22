import os
import unittest

os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "testing-secret-not-for-production"
os.environ.pop("BOOTSTRAP_MASTER_EMAIL", None)
os.environ.pop("BOOTSTRAP_MASTER_PASSWORD", None)

from app import create_app, db, User
from werkzeug.security import generate_password_hash

class ArenaRunApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(User(name="Master Tester", email="master@example.test", password_hash=generate_password_hash("superstrong123"), role="master", approved=True))
            db.session.commit()

    def register(self, email, role="runner"):
        return self.client.post("/api/auth/register", json={"name":"Atleta Teste", "email":email, "password":"verystrong123", "role":role})

    def login(self, email, password):
        data=self.client.post("/api/auth/login",json={"email":email,"password":password})
        self.assertEqual(data.status_code,200)
        return {"Authorization":"Bearer "+data.json["token"]}

    def test_health_and_empty_catalog(self):
        self.assertEqual(self.client.get("/api/health").status_code,200)
        self.assertEqual(self.client.get("/api/events").json["events"],[])

    def test_registration_login_and_duplicate_email(self):
        created=self.register("runner@example.test")
        self.assertEqual(created.status_code,201)
        self.assertEqual(self.register("runner@example.test").status_code,409)
        self.assertEqual(self.client.post("/api/auth/login",json={"email":"runner@example.test","password":"wrong"}).status_code,401)
        headers=self.login("runner@example.test","verystrong123")
        self.assertEqual(self.client.get("/api/me",headers=headers).json["role"],"runner")

    def test_organizer_approval_and_registration(self):
        organizer=self.register("org@example.test","organizer").json
        org_headers={"Authorization":"Bearer "+organizer["token"]}
        payload={"title":"Circuito Teste","city":"Belém","date":"2026-11-15","distances":[{"label":"5 KM","price_cents":6500,"capacity":2}]}
        self.assertEqual(self.client.post("/api/events",headers=org_headers,json=payload).status_code,403)
        master=self.login("master@example.test","superstrong123")
        self.assertEqual(self.client.post("/api/master/organizers/"+str(organizer["user"]["id"])+"/approve",headers=master).status_code,200)
        created=self.client.post("/api/events",headers=org_headers,json=payload)
        self.assertEqual(created.status_code,201)
        distance_id=created.json["distances"][0]["id"]
        runner=self.register("runner@example.test").json
        runner_headers={"Authorization":"Bearer "+runner["token"]}
        reg=self.client.post("/api/registrations",headers=runner_headers,json={"distance_id":distance_id,"shirt_size":"M"})
        self.assertEqual(reg.status_code,201)
        self.assertEqual(reg.json["status"],"awaiting_payment")
        self.assertEqual(self.client.post("/api/registrations",headers=runner_headers,json={"distance_id":distance_id,"shirt_size":"M"}).status_code,409)
        self.assertEqual(len(self.client.get("/api/organizer/registrations",headers=org_headers).json["registrations"]),1)
        self.assertEqual(len(self.client.get("/api/registrations/me",headers=runner_headers).json["registrations"]),1)
        self.assertEqual(self.client.post("/api/demo/registrations/"+str(reg.json["id"])+"/confirm",headers=master).status_code,403)

if __name__=="__main__":
    unittest.main()
