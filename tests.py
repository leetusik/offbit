import os
import unittest
from datetime import datetime, timedelta, timezone

from app import create_app, db
from app.models import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///"  # In-memory database for testing
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PUBLIC_KEY_PATH = os.path.join(os.getcwd(), "instance/public_key.pem")
    PRIVATE_KEY_PATH = os.path.join(os.getcwd(), "instance/private_key.pem")


class UserModelCase(unittest.TestCase):
    def setUp(self):  # Proper setUp method
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):  # Proper tearDown method
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username="sugang", email="sugang@gmail.com")
        u.set_password("cat")
        self.assertFalse(u.check_password("dog"))
        self.assertTrue(u.check_password("cat"))

    def test_avatar(self):
        u = User(username="john", email="john@example.com")
        self.assertEqual(
            u.avatar(128),
            (
                "https://www.gravatar.com/avatar/"
                "d4c74594d841139328695756648b6bd6"
                "?d=identicon&s=128"
            ),
        )

    def test_api_key_encryption(self):
        u = User(username="sugang", email="sugang@gmail.com")
        api_key = "my_super_secret_upbit_api_key"
        u.set_open_api_key(api_key)
        db.session.add(u)
        db.session.commit()

        # Retrieve the user and test decryption
        retrieved_user = User.query.filter_by(username="sugang").first()
        self.assertEqual(retrieved_user.get_open_api_key(), api_key)

    def test_verification_code_generation(self):
        u = User(username="testuser", email="test@example.com")
        db.session.add(u)
        db.session.commit()

        u.set_verification_code()
        self.assertIsNotNone(u.verification_code)
        self.assertIsNotNone(u.verification_code_expiration)

        # Check that the code is a 6-digit number
        self.assertTrue(100000 <= u.verification_code <= 999999)

    def test_verification_code_expiration(self):
        u = User(username="testuser", email="test@example.com")
        db.session.add(u)
        db.session.commit()

        u.set_verification_code()
        u.verification_code_expiration = u.verification_code_expiration.replace(
            tzinfo=timezone.utc
        )
        # Check that the verification code is valid for 1 minute
        now = datetime.now(timezone.utc)
        self.assertTrue(now < u.verification_code_expiration)

        # Fast-forward time by 2 minutes and check that it expires
        expired_time = now + timedelta(minutes=2)
        self.assertTrue(expired_time > u.verification_code_expiration)


if __name__ == "__main__":
    unittest.main(verbosity=2)
