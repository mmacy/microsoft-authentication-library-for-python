from . import oauth2
from .authority import Authority
from .request import decorate_scope
from .client_credential import ClientCredentialRequest


class ClientApplication(object):

    def __init__(
            self, client_id,
            authority_url="https://login.microsoftonline.com/common/",
            validate_authority=True):
        self.client_id = client_id
        self.authority = Authority(authority_url, validate_authority)

    def acquire_token_silent(
            self, scope,
            user=None,  # It can be a string as user id, or a User object
            authority=None,  # See get_authorization_request_url()
            policy='',
            force_refresh=False,  # To force refresh an Access Token (not a RT)
            **kwargs):
        a = Authority(authority) if authority else self.authority
        client = oauth2.Client(self.client_id, token_endpoint=a.token_endpoint)
        refresh_token = kwargs.get('refresh_token')  # For testing purpose
        response = client.get_token_by_refresh_token(
            refresh_token,
            scope=decorate_scope(scope, self.client_id, policy),
            client_secret=getattr(self, 'client_credential'),  # TODO: JWT too
            query={'policy': policy} if policy else None)
        # TODO: refresh the refresh_token
        return response


class PublicClientApplication(ClientApplication):  # browser app or mobile app

    ## TBD: what if redirect_uri is not needed in the constructor at all?
    ##  Device Code flow does not need redirect_uri anyway.

    # OUT_OF_BAND = "urn:ietf:wg:oauth:2.0:oob"
    # def __init__(self, client_id, redirect_uri=None, **kwargs):
    #     super(PublicClientApplication, self).__init__(client_id, **kwargs)
    #     self.redirect_uri = redirect_uri or self.OUT_OF_BAND

    def acquire_token(
            self,
            scope,
            # additional_scope=None,  # See also get_authorization_request_url()
            login_hint=None,
            ui_options=None,
            # user=None,  # TBD: It exists in MSAL-dotnet but not in MSAL-Android
            policy='',
            authority=None,  # See get_authorization_request_url()
            extra_query_params=None,
            ):
        # It will handle the TWO round trips of Authorization Code Grant flow.
        raise NotImplemented()

    # TODO: Support Device Code flow


class ConfidentialClientApplication(ClientApplication):  # server-side web app
    def __init__(
            self, client_id, client_credential, user_token_cache=None,
            # redirect_uri=None,  # Experimental: Removed for now.
            #   acquire_token_for_client() doesn't need it
            **kwargs):
        """
        :param client_credential: It can be a string containing client secret,
            or an X509 certificate container in this form:

                {
                    "certificate": "-----BEGIN PRIVATE KEY-----...",
                    "thumbprint": "A1B2C3D4E5F6...",
                }
        """
        super(ConfidentialClientApplication, self).__init__(client_id, **kwargs)
        self.client_credential = client_credential
        self.user_token_cache = user_token_cache
        self.app_token_cache = None  # TODO

    def acquire_token_for_client(self, scope, policy=''):
        return ClientCredentialRequest(
            client_id=self.client_id, client_credential=self.client_credential,
            scope=scope,  # This grant flow requires no scope decoration
            policy=policy, authority=self.authority).run()

    def get_authorization_request_url(
            self,
            scope,
            # additional_scope=None,  # Not yet implemented
            login_hint=None,
            state=None,  # Recommended by OAuth2 for CSRF protection
            policy='',
            redirect_uri=None,
            authority=None,  # By default, it will use self.authority;
                             # Multi-tenant app can use new authority on demand
            extra_query_params=None,  # None or a dictionary
            ):
        """Constructs a URL for you to start a Authorization Code Grant.

        :param scope: Scope refers to the resource that will be used in the
            resulting token's audience.
        :param additional_scope: Additional scope is a concept only in AAD.
            It refers to other resources you might want to prompt to consent
            for in the same interaction, but for which you won't get back a
            token for in this particular operation.
            (Under the hood, we simply merge scope and additional_scope before
            sending them on the wire.)
        :param str state: Recommended by OAuth2 for CSRF protection.
        """
        a = Authority(authority) if authority else self.authority
        grant = oauth2.AuthorizationCodeGrant(
            self.client_id, authorization_endpoint=a.authorization_endpoint)
        return grant.authorization_url(
            redirect_uri=redirect_uri, state=state, login_hint=login_hint,
            scope=decorate_scope(scope, self.client_id, policy),
            policy=policy if policy else None,
            **(extra_query_params or {}))

    def acquire_token_by_authorization_code(
            self,
            code,
            scope,  # Syntactically required. STS accepts empty value though.
            redirect_uri=None,
                # REQUIRED, if the "redirect_uri" parameter was included in the
                # authorization request as described in Section 4.1.1, and their
                # values MUST be identical.
            policy=''
            ):
        """The second half of the Authorization Code Grant.

        :param code: The authorization code returned from Authorization Server.
        :param scope:

            If you requested user consent for multiple resources, here you will
            typically want to provide a subset of what you required in AC.

            OAuth2 was designed mostly for singleton services,
            where tokens are always meant for the same resource and the only
            changes are in the scopes.
            In AAD, tokens can be issued for multiple 3rd parth resources.
            You can ask authorization code for multiple resources,
            but when you redeem it, the token is for only one intended
            recipient, called audience.
            So the developer need to specify a scope so that we can restrict the
            token to be issued for the corresponding audience.
        """
        # If scope is absent on the wire, STS will give you a token associated
        # to the FIRST scope sent during the authorization request.
        # So in theory, you can omit scope here when you were working with only
        # one scope. But, MSAL decorates your scope anyway, so they are never
        # really empty.
        grant = oauth2.AuthorizationCodeGrant(
            self.client_id, token_endpoint=self.authority.token_endpoint)
        return grant.get_token(
            code, redirect_uri=redirect_uri,
            scope=decorate_scope(scope, self.client_id, policy),
            client_secret=self.client_credential,  # TODO: Support certificate
            query={'policy': policy} if policy else None)

    def acquire_token_on_behalf_of(
            self, user_assertion, scope, authority=None, policy=''):
        pass
