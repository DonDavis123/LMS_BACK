from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from src.modules.authentication.infrastructure.security.cached_jwt_authentication import (
    CachedJWTAuthentication,
)
from src.modules.companies.infrastructure.persistence.company_suspension import (
    is_company_suspended,
)
from src.modules.companies.infrastructure.persistence.django_company_model import (
    DjangoCompanyModel,
)
from src.modules.shared.tests.tenancy.factories import (
    access_token_for,
    make_company,
    make_user,
)


@override_settings(AUTH_CACHE_TTL_SECONDS=60)
class CachedJWTAuthenticationTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.company = make_company()
        self.user = make_user(self.company)
        self.auth = CachedJWTAuthentication()
        self.token = self.auth.get_validated_token(
            access_token_for(self.user).encode()
        )

    def test_second_lookup_is_served_from_cache(self):
        with self.assertNumQueries(1):
            first = self.auth.get_user(self.token)
        with self.assertNumQueries(0):
            second = self.auth.get_user(self.token)

        self.assertEqual(first.pk, self.user.pk)
        self.assertEqual(second.pk, self.user.pk)
        self.assertEqual(second.company_id, self.company.id)
        self.assertEqual(second.role, self.user.role)

    def test_saving_the_user_clears_the_cache(self):
        self.auth.get_user(self.token)

        self.user.role = "SALES_EXECUTIVE"
        self.user.save(update_fields=["role", "updated_at"])

        refreshed = self.auth.get_user(self.token)
        self.assertEqual(refreshed.role, "SALES_EXECUTIVE")

    def test_blocked_user_is_rejected_on_the_next_request(self):
        self.auth.get_user(self.token)

        self.user.is_active = False
        self.user.save(update_fields=["is_active", "updated_at"])

        with self.assertRaises(AuthenticationFailed):
            self.auth.get_user(self.token)

    def test_inactive_user_is_never_cached(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active", "updated_at"])

        with self.assertRaises(AuthenticationFailed):
            self.auth.get_user(self.token)
        with self.assertRaises(AuthenticationFailed):
            self.auth.get_user(self.token)

    def test_deleted_user_is_rejected(self):
        self.auth.get_user(self.token)

        self.user.delete()

        with self.assertRaises(AuthenticationFailed):
            self.auth.get_user(self.token)

    def test_cache_error_falls_back_to_the_database(self):
        from unittest import mock

        with mock.patch(
            "src.modules.shared.infrastructure.caching.auth_cache.cache"
        ) as broken:
            broken.get.side_effect = ConnectionError("redis down")
            broken.set.side_effect = ConnectionError("redis down")
            user = self.auth.get_user(self.token)

        self.assertEqual(user.pk, self.user.pk)

    @override_settings(AUTH_CACHE_TTL_SECONDS=0)
    def test_ttl_zero_disables_the_cache(self):
        with self.assertNumQueries(1):
            self.auth.get_user(self.token)
        with self.assertNumQueries(1):
            self.auth.get_user(self.token)


@override_settings(AUTH_CACHE_TTL_SECONDS=60)
class CompanySuspensionCacheTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.company = make_company()

    def test_answer_is_cached(self):
        with self.assertNumQueries(1):
            self.assertFalse(is_company_suspended(self.company.id))
        with self.assertNumQueries(0):
            self.assertFalse(is_company_suspended(self.company.id))

    def test_suspending_applies_immediately(self):
        self.assertFalse(is_company_suspended(self.company.id))

        self.company.status = DjangoCompanyModel.Status.SUSPENDED
        self.company.save(update_fields=["status", "updated_at"])

        self.assertTrue(is_company_suspended(self.company.id))

    def test_reactivating_applies_immediately(self):
        self.company.status = DjangoCompanyModel.Status.SUSPENDED
        self.company.save(update_fields=["status", "updated_at"])
        self.assertTrue(is_company_suspended(self.company.id))

        self.company.status = DjangoCompanyModel.Status.ACTIVE
        self.company.save(update_fields=["status", "updated_at"])

        self.assertFalse(is_company_suspended(self.company.id))

    def test_none_company_is_not_suspended_without_a_query(self):
        with self.assertNumQueries(0):
            self.assertFalse(is_company_suspended(None))
