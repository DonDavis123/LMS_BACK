from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from src.modules.authentication.presentation.api.serializer.reset_password import (
    ResetPasswordSerializer,
)
from src.modules.companies.presentation.api.serializers.company import (
    CreateCompanySerializer,
    CreateCompanyUserSerializer,
)
from src.modules.shared.presentation.password_validation import password_errors
from src.modules.users.presentation.api.serializers.create_user_serializer import (
    CreateUserSerializer,
)
from src.modules.users.presentation.api.serializers.reset_user_password import (
    ResetUserPasswordSerializer,
)

# `manage.py test` runs with the length rule only (see settings.py); these
# tests turn the real policy on.
_VALIDATION = "django.contrib.auth.password_validation."
FULL_POLICY = override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {
            "NAME": _VALIDATION + "UserAttributeSimilarityValidator",
            "OPTIONS": {"user_attributes": ("email", "name")},
        },
        {
            "NAME": _VALIDATION + "MinimumLengthValidator",
            "OPTIONS": {"min_length": 8},
        },
        {"NAME": _VALIDATION + "CommonPasswordValidator"},
        {"NAME": _VALIDATION + "NumericPasswordValidator"},
    ]
)

STRONG = "plum-Harbor-47-lantern"
AUTH_VIEWS = "src.modules.authentication.presentation.api.views"


@FULL_POLICY
class PasswordErrorsTests(SimpleTestCase):
    def test_strong_password_is_accepted(self):
        self.assertEqual(password_errors(STRONG), [])

    def test_one_character_password_is_rejected(self):
        self.assertTrue(password_errors("a"))

    def test_too_short_password_is_rejected(self):
        self.assertTrue(password_errors("Ab1!xyz"))

    def test_common_password_is_rejected(self):
        self.assertTrue(password_errors("password123"))

    def test_numeric_only_password_is_rejected(self):
        self.assertTrue(password_errors("48151623421"))

    def test_password_built_from_the_email_is_rejected(self):
        self.assertTrue(
            password_errors("alice.smith@acme.com", email="alice.smith@acme.com")
        )

    def test_password_built_from_the_name_is_rejected(self):
        self.assertTrue(
            password_errors("Alice Johnson", email="a@acme.com", name="Alice Johnson")
        )


@FULL_POLICY
class ResetPasswordSerializerTests(SimpleTestCase):
    def errors(self, password):
        serializer = ResetPasswordSerializer(
            data={"token": "tok", "new_password": password}
        )
        self.assertFalse(serializer.is_valid())
        return serializer.errors

    def test_one_character_password_is_invalid(self):
        self.assertIn("new_password", self.errors("1"))

    def test_common_password_is_invalid(self):
        self.assertIn("new_password", self.errors("password123"))

    def test_overlong_password_is_invalid(self):
        self.assertIn("new_password", self.errors("aB3-" * 40))

    def test_strong_password_is_valid(self):
        serializer = ResetPasswordSerializer(
            data={"token": "tok", "new_password": STRONG}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


@FULL_POLICY
class ResetUserPasswordSerializerTests(SimpleTestCase):
    def test_weak_passwords_are_invalid(self):
        for weak in ("a", "short", "password123", "12345678901"):
            with self.subTest(weak=weak):
                serializer = ResetUserPasswordSerializer(data={"new_password": weak})
                self.assertFalse(serializer.is_valid())
                self.assertIn("new_password", serializer.errors)

    def test_strong_password_is_valid(self):
        serializer = ResetUserPasswordSerializer(data={"new_password": STRONG})
        self.assertTrue(serializer.is_valid(), serializer.errors)


@FULL_POLICY
class CreateUserSerializerTests(SimpleTestCase):
    def payload(self, **extra):
        return {
            "name": "Bob Builder",
            "email": "bob@example.com",
            "password": STRONG,
            "role": "ADMIN",
            **extra,
        }

    def test_strong_password_is_valid(self):
        serializer = CreateUserSerializer(data=self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_common_password_is_reported_on_the_password_field(self):
        serializer = CreateUserSerializer(data=self.payload(password="password123"))
        self.assertFalse(serializer.is_valid())
        self.assertEqual(list(serializer.errors), ["password"])

    def test_password_similar_to_the_email_is_invalid(self):
        serializer = CreateUserSerializer(
            data=self.payload(password="bob@example.com")
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)


@FULL_POLICY
class CompanySerializersTests(SimpleTestCase):
    def company(self, **extra):
        return {
            "company_name": "Acme",
            "admin_name": "Alice Admin",
            "admin_email": "alice@acme.example.com",
            "admin_password": STRONG,
            **extra,
        }

    def test_company_admin_password_is_checked(self):
        good = CreateCompanySerializer(data=self.company())
        self.assertTrue(good.is_valid(), good.errors)

        weak = CreateCompanySerializer(data=self.company(admin_password="password123"))
        self.assertFalse(weak.is_valid())
        self.assertEqual(list(weak.errors), ["admin_password"])

    def test_company_user_password_is_checked(self):
        body = {
            "name": "Carol",
            "email": "carol@acme.example.com",
            "password": STRONG,
            "role": "ADMIN",
        }
        self.assertTrue(CreateCompanyUserSerializer(data=body).is_valid())

        weak = CreateCompanyUserSerializer(data={**body, "password": "11111111"})
        self.assertFalse(weak.is_valid())
        self.assertEqual(list(weak.errors), ["password"])


@FULL_POLICY
@override_settings(ALLOWED_HOSTS=["testserver"])
class ResetPasswordEndpointTests(SimpleTestCase):
    URL = "/api/auth/reset-password/"

    @patch(f"{AUTH_VIEWS}.reset_password.get_reset_password_use_case")
    def test_weak_password_is_a_400_and_the_token_is_not_used(self, get_use_case):
        use_case = get_use_case.return_value = Mock()

        response = APIClient().post(
            self.URL, {"token": "tok", "new_password": "1"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.json())
        use_case.execute.assert_not_called()

    @patch(f"{AUTH_VIEWS}.reset_password.get_reset_password_use_case")
    def test_strong_password_is_accepted(self, get_use_case):
        use_case = get_use_case.return_value = Mock()

        response = APIClient().post(
            self.URL, {"token": "tok", "new_password": STRONG}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        use_case.execute.assert_called_once()
