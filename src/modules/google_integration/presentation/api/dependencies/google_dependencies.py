from uuid import UUID

from src.modules.google_integration.application.services.google_access_token_service import (
    GoogleAccessTokenService,
)
from src.modules.google_integration.application.use_cases.complete_google_connect import (
    CompleteGoogleConnectUseCase,
)
from src.modules.google_integration.application.use_cases.disconnect_google import (
    DisconnectGoogleUseCase,
)
from src.modules.google_integration.application.use_cases.get_google_connection_status import (
    GetGoogleConnectionStatusUseCase,
)
from src.modules.google_integration.application.use_cases.start_google_connect import (
    StartGoogleConnectUseCase,
)
from src.modules.google_integration.infrastructure.fernet_token_cipher import (
    FernetTokenCipher,
)
from src.modules.google_integration.infrastructure.google_oauth_http_client import (
    GoogleOAuthHttpClient,
)
from src.modules.google_integration.infrastructure.persistence.django_google_connection_repository import (
    DjangoGoogleConnectionRepository,
)
from src.modules.google_integration.infrastructure.signed_oauth_state import (
    SignedOAuthStateSigner,
)
from src.modules.shared.application.tenant_context import TenantContext
from src.modules.users.infrastructure.persistence.user_repository import DjangoUserRepository


def get_state_signer() -> SignedOAuthStateSigner:
    return SignedOAuthStateSigner()


def get_google_access_token_service(company_id: UUID) -> GoogleAccessTokenService:
    """Also used by other modules (e.g. meetings) to call Google as a user."""
    return GoogleAccessTokenService(
        DjangoGoogleConnectionRepository(company_id=company_id),
        GoogleOAuthHttpClient(),
        FernetTokenCipher(),
    )


def get_google_connection_status_use_case(ctx: TenantContext) -> GetGoogleConnectionStatusUseCase:
    return GetGoogleConnectionStatusUseCase(
        DjangoGoogleConnectionRepository(company_id=ctx.company_id),
        GoogleOAuthHttpClient(),
    )


def get_start_google_connect_use_case(ctx: TenantContext) -> StartGoogleConnectUseCase:
    return StartGoogleConnectUseCase(
        DjangoUserRepository(company_id=ctx.company_id),
        GoogleOAuthHttpClient(),
        get_state_signer(),
    )


def get_complete_google_connect_use_case(company_id: UUID) -> CompleteGoogleConnectUseCase:
    # The callback has no authenticated request; the company comes from the
    # verified (signed) OAuth state instead.
    return CompleteGoogleConnectUseCase(
        DjangoGoogleConnectionRepository(company_id=company_id),
        DjangoUserRepository(company_id=company_id),
        GoogleOAuthHttpClient(),
        FernetTokenCipher(),
    )


def get_disconnect_google_use_case(ctx: TenantContext) -> DisconnectGoogleUseCase:
    return DisconnectGoogleUseCase(
        DjangoGoogleConnectionRepository(company_id=ctx.company_id),
        GoogleOAuthHttpClient(),
        FernetTokenCipher(),
    )
