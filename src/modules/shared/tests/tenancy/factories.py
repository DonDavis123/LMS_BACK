import itertools

from django.utils.text import slugify
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.users.infrastructure.persistence.models import User

DEFAULT_TEST_COMPANY_SLUG = "default-test-company"
DEFAULT_PASSWORD = "password123"

_counter = itertools.count(1)


def make_company(
    name: str = "Test Company",
    slug: str | None = None,
    status: str = DjangoCompanyModel.Status.ACTIVE,
) -> DjangoCompanyModel:
    if slug is None:
        slug = f"{slugify(name) or 'company'}-{next(_counter)}"

    return DjangoCompanyModel.objects.create(
        name=name,
        slug=slug,
        status=status,
    )


def make_user(
    company: DjangoCompanyModel | None,
    role: str = User.Role.ADMIN,
    email: str | None = None,
    *,
    name: str | None = None,
    password: str = DEFAULT_PASSWORD,
    is_active: bool = True,
) -> User:
    if email is None:
        email = f"user{next(_counter)}@example.com"

    return User.objects.create_user(
        email=email,
        password=password,
        name=name or email.split("@")[0],
        role=role,
        company=company,
        is_active=is_active,
    )


def default_test_company() -> DjangoCompanyModel:
    """One shared company for old tests that only need *a* company."""
    company, _ = DjangoCompanyModel.objects.get_or_create(
        slug=DEFAULT_TEST_COMPANY_SLUG,
        defaults={
            "name": "Default Test Company",
            "status": DjangoCompanyModel.Status.ACTIVE,
        },
    )
    return company


def authenticated_client(user: User) -> APIClient:
    """Client authenticated with force_authenticate (no token round-trip)."""
    client = APIClient()
    client.force_authenticate(user)
    return client


def access_token_for(user: User) -> str:
    return str(RefreshToken.for_user(user).access_token)


def token_client(user: User) -> APIClient:
    """Client that authenticates through the real JWT authentication."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")
    return client
