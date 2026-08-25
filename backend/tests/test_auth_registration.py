import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, User
from routers.auth import RegisterRequest, register, registration_status
from security import verify_password


class FirstAdministratorRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_first_registration_creates_admin_and_returns_login_token(self):
        self.assertTrue(registration_status(self.db).available)

        response = register(RegisterRequest(username=" first-admin ", password="1"), self.db)
        user = self.db.query(User).one()

        self.assertEqual(user.username, "first-admin")
        self.assertEqual(user.role, "admin")
        self.assertTrue(verify_password("1", user.password)[0])
        self.assertEqual(response.user.id, user.id)
        self.assertEqual(response.user.role, "admin")
        self.assertTrue(response.access_token)
        self.assertFalse(registration_status(self.db).available)

    def test_registration_closes_after_any_user_exists(self):
        self.db.add(User(username="existing", password="legacy", role="analyst"))
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            register(RegisterRequest(username="another", password="secret"), self.db)

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(self.db.query(User).count(), 1)

    def test_blank_credentials_are_rejected(self):
        with self.assertRaises(HTTPException) as username_error:
            register(RegisterRequest(username="   ", password="secret"), self.db)
        self.assertEqual(username_error.exception.status_code, 400)

        with self.assertRaises(HTTPException) as password_error:
            register(RegisterRequest(username="admin", password=""), self.db)
        self.assertEqual(password_error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
