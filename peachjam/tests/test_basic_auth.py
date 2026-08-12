import base64

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from peachjam.middleware import BasicAuthMiddleware


class BasicAuthMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def get_response(self, path, authorization=None):
        request_kwargs = {}
        if authorization:
            request_kwargs["HTTP_AUTHORIZATION"] = authorization
        request = self.factory.get(path, **request_kwargs)
        middleware = BasicAuthMiddleware(lambda request: HttpResponse("ok"))
        return middleware(request)

    def basic_auth(self, username, password):
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        return f"Basic {credentials}"

    @override_settings(BASIC_AUTH_USERNAME="", BASIC_AUTH_PASSWORD="")
    def test_allows_requests_when_not_configured(self):
        response = self.get_response("/")

        self.assertEqual(response.status_code, 200)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_REALM="Test",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=[],
    )
    def test_challenges_requests_without_credentials(self):
        response = self.get_response("/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], 'Basic realm="Test"')

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=[],
    )
    def test_allows_requests_with_valid_credentials(self):
        response = self.get_response("/", self.basic_auth("user", "secret"))

        self.assertEqual(response.status_code, 200)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=[],
    )
    def test_allows_case_insensitive_basic_auth_scheme(self):
        response = self.get_response(
            "/",
            self.basic_auth("user", "secret").replace("Basic", "basic"),
        )

        self.assertEqual(response.status_code, 200)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=[],
    )
    def test_challenges_requests_with_invalid_credentials(self):
        response = self.get_response("/", self.basic_auth("user", "wrong"))

        self.assertEqual(response.status_code, 401)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=[],
    )
    def test_challenges_requests_with_malformed_basic_credentials(self):
        response = self.get_response("/", "Basic invalid")

        self.assertEqual(response.status_code, 401)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=["/api/"],
    )
    def test_allows_excluded_path_prefixes_without_credentials(self):
        response = self.get_response("/api/v1/")

        self.assertEqual(response.status_code, 200)

    @override_settings(
        BASIC_AUTH_USERNAME="user",
        BASIC_AUTH_PASSWORD="secret",
        BASIC_AUTH_EXCLUDED_PATH_PREFIXES=["/admin/"],
    )
    def test_allows_admin_path_prefix_without_credentials(self):
        response = self.get_response("/admin/login/")

        self.assertEqual(response.status_code, 200)
