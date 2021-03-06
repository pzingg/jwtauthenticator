from jupyterhub.handlers import BaseHandler
from jupyterhub.auth import Authenticator
from jupyterhub.auth import LocalAuthenticator
from jupyterhub.utils import url_path_join
from tornado import gen, web
from traitlets import Unicode
from jose import jwt

class JSONWebTokenLoginHandler(BaseHandler):

    def get(self):
        header_name = self.authenticator.header_name
        param_name = self.authenticator.param_name

        auth_header_content = self.request.headers.get(header_name, "")
        auth_cookie_content = self.get_cookie("XSRF-TOKEN", "")
        signing_certificate = self.authenticator.signing_certificate
        secret = self.authenticator.secret
        username_claim_field = self.authenticator.username_claim_field
        audience = self.authenticator.expected_audience
        token_param = self.get_argument(param_name, default=False)

        if auth_header_content and token_param:
           raise web.HTTPError(400)
        elif auth_header_content:
           # We should not see "token" as first word in the Authorization header.
           # If we do, it could mean someone coming in with a stale API token.
           header_words = auth_header_content.split()
           # RFC 6750 section 2.1 states that the authentication scheme
           # for bearer tokens must be "Bearer", capitalized. We will also accept
           # legacy lowercase "bearer" scheme.
           if (len(header_words) < 2) or (header_words[0] not in ["Bearer", "bearer"]):
              raise web.HTTPError(403)
           token = header_words[1]
        elif auth_cookie_content:
           token = auth_cookie_content
        elif token_param:
           token = token_param
        else:
           raise web.HTTPError(401)

        claims = "";
        if secret:
            algorithms = list(jwt.ALGORITHMS.SUPPORTED)
            claims = self.verify_jwt_using_secret(token, secret, audience, algorithms)
        elif signing_certificate:
            claims = self.verify_jwt_using_certificate(token, signing_certificate, audience)
        else:
            raise web.HTTPError(401)

        username = self.retrieve_username(claims, username_claim_field)
        user = self.user_from_username(username)
        self.set_login_cookie(user)

        _url = url_path_join(self.hub.server.base_url, 'home')
        next_url = self.get_argument('next', default=False)
        if next_url:
             _url = next_url

        self.redirect(_url)

    @staticmethod
    def verify_jwt_using_certificate(token, signing_certificate, audience):
        with open(signing_certificate, 'r') as rsa_public_key_file:
            return verify_jwt_using_secret(token, rsa_public_key_file.read(), audience, None)

    @staticmethod
    def verify_jwt_using_secret(token, secret, audience, algorithms):
        # If no audience is supplied then assume we're not verifying the audience field.
        if audience == "":
            opts = {"verify_aud": False}
        else:
            opts = {}
        return jwt.decode(token, secret, algorithms=algorithms, audience=audience, options=opts)

    @staticmethod
    def retrieve_username(claims, username_claim_field):
        # retrieve the username from the claims
        username = claims[username_claim_field]
        if "@" in username:
            # process username as if email, pull out string before '@' symbol
            return username.split("@")[0]

        else:
            # assume not username and return the user
            return username


class JSONWebTokenAuthenticator(Authenticator):
    """
    Accept the authenticated JSON Web Token from header.
    """
    signing_certificate = Unicode(
        config=True,
        help="""
        The public certificate of the private key used to sign the incoming JSON Web Tokens.

        Should be a path to an X509 PEM format certificate filesystem.
        """
    )

    username_claim_field = Unicode(
        default_value='upn',
        config=True,
        help="""
        The field in the claims that contains the user name. It can be either a straight username,
        of an email/userPrincipalName.
        """
    )

    expected_audience = Unicode(
        default_value='',
        config=True,
        help="""If not an empty string, a string value that must be present in the JWT's `aud` claim."""
    )

    header_name = Unicode(
        default_value='Authorization',
        config=True,
        help="""HTTP header to inspect for the authenticated JSON Web Token.""")

    param_name = Unicode(
        config=True,
        default_value='access_token',
        help="""The name of the query parameter used to specify the JWT token""")

    secret = Unicode(
        config=True,
        help="""Shared secret key for siging JWT token.  If defined, it overrides any setting for signing_certificate""")

    def get_handlers(self, app):
        return [
            (r'/login', JSONWebTokenLoginHandler),
        ]

    @gen.coroutine
    def authenticate(self, *args):
        raise NotImplementedError()


class JSONWebTokenLocalAuthenticator(JSONWebTokenAuthenticator, LocalAuthenticator):
    """
    A version of JSONWebTokenAuthenticator that mixes in local system user creation
    """
    pass
