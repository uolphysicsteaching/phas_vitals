"""Subclass the standard django_auth_adfs backend for ourt purposes."""

# Python imports
import hashlib
import hmac
import logging
import os
from collections.abc import Mapping
from json import JSONDecodeError

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.utils.encoding import force_bytes

# external imports
import jsondatetime as json
import requests
from django_auth_adfs import signals
from django_auth_adfs.backend import AdfsAuthCodeBackend
from django_auth_adfs.config import provider_config, settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

# app imports
from phas_vitals import celery_app

# app imports
from .models import APIKey

update_account = celery_app.signature("accounts.tasks.update_user_from_graph")
logger = logging.getLogger("django_auth_adfs")
logger_drf = logging.getLogger("drf_authentication")


class LeedsAdfsBaseBackend(AdfsAuthCodeBackend):
    """Subclass of AdfsAuthCodeBackend to customise user creation."""

    def process_access_token(self, access_token, adfs_response=None):
        """Check the user is ok by getting the Account object."""
        if not access_token:
            raise PermissionDenied

        claims = self.validate_access_token(access_token)
        if not claims:
            raise PermissionDenied
        if claims.get("tid") != settings.TENANT_ID:  # Definitely block guest access
            logger.info("Guest user denied")
            raise PermissionDenied

        self.access_token = access_token
        self.claims = claims

        groups = self.process_user_groups(claims, access_token)
        user = self.create_user(claims)
        self.update_user_attributes(user, claims)
        self.update_user_groups(user, groups)
        self.update_user_flags(user, claims, groups)

        signals.post_authenticate.send(sender=self, user=user, claims=claims, adfs_response=adfs_response)

        user.full_clean()
        user.save()
        return user

    def process_user_groups(self, claims, access_token):
        """Check the user groups are in the claim or pulls them from MS Graph if applicable.

        Args:
            claims (dict): claims from the access token
            access_token (str): Used to make an OBO authentication request if
            groups must be obtained from Microsoft Graph

        Returns:
            groups (list): Groups the user is a member of, taken from the access token or MS Graph
        """
        groups = []
        logger.debug("Call to process_user_groups")
        return groups

    def create_user(self, claims):
        """Create the user if it doesn't exist yet.

        Args:
            claims (dict): claims from the access token

        Returns:
            django.contrib.auth.models.User: A Django user
        """
        # Get the lookup detils for the user
        username_claim = settings.USERNAME_CLAIM
        usermodel = get_user_model()
        if not claims.get(username_claim):
            logger.error(f"User claim's doesn't have the claim '{username_claim}' in his claims: {claims}")
            raise PermissionDenied

        # The username claim we're getting back is aq full email address, but we just want the userid part
        username = claims[username_claim].split("@")[0].strip()
        userdata = {usermodel.USERNAME_FIELD: username}

        try:
            user = usermodel.objects.get(**userdata)
            if not user.is_active:
                raise PermissionDenied
        except (usermodel.DoesNotExist, PermissionDenied):  # No on the fly user creation here
            logger.debug(f"User '{username}' doesn't exist or is inactive and creating users is disabled.")
            raise PermissionDenied
        if not user.password:
            user.set_unusable_password()
        return user

    # https://github.com/snok/django-auth-adfs/issues/241
    def update_user_attributes(self, user, claims, claim_mapping=None):
        """Update the user account with task that calls MS Graph.

        Parameters:
            user : Account
                Account object of user logging in.
            claims : dict
                Oauth2 claims about the user account.
            claim_mapping : dict,None, optional
                Optional mapping of claim values to user attributes. The default is None.

        Obtains the correct on-behalf-of token and then hands to Celery taks in the accounts app that
        actually talks to the MS Graph API to update the user account object.
        """
        obo_access_token = self.get_obo_access_token(self.access_token)
        logger.debug(f"Calling account.update_user_from_graph task with {user.pk} - {user.username}")
        update_account.delay(user.pk, obo_access_token)
        logger.debug("User update taks dispatched")

    def update_user_groups(self, user, claim_groups):
        """Stub method that eventually should do ldap lookup."""
        logger.debug(f"Groups update requested for {user} with {claim_groups}")

    def update_user_flags(self, user, claims, claim_groups):
        """Stub to update User flag that eventually should be an ldap lookup."""
        logger.debug(f"User flags update requested for {user} with {claim_groups}")

    def get_group_memberships_from_ms_graph(self, obo_access_token):
        """Look up a users group membership from the MS Graph API.

        Args:
            obo_access_token (str): Access token obtained from the OBO authorization endpoint

        Returns:
            claim_groups (list): List of the users group memberships
        """
        graph_url = "https://{}/v1.0/me/transitiveMemberOf/microsoft.graph.group".format(
            provider_config.msgraph_endpoint
        )
        headers = {"Authorization": "Bearer {}".format(obo_access_token)}
        response = provider_config.session.get(graph_url, headers=headers, timeout=settings.TIMEOUT)
        # 200 = valid token received
        # 400 = 'something' is wrong in our request
        if response.status_code in [400, 401]:
            logger.error("MS Graph server returned an error: %s", response.json()["message"])
            raise PermissionDenied

        if response.status_code != 200:
            logger.error("Unexpected MS Graph response: %s", response.content.decode())
            raise PermissionDenied

        claim_groups = []
        for group_data in response.json()["value"]:
            if group_data["displayName"] is None:
                logger.error(
                    "The application does not have the required permission to read user groups from "
                    "MS Graph (GroupMember.Read.All)"
                )
                raise PermissionDenied

            claim_groups.append(group_data["displayName"])
        return claim_groups


class HMACAuthentication(BaseAuthentication):
    """Implements an HMAC signature based token authentication scheme for Django REST Framework."""

    keyword = "HMAC"

    def authenticate(self, request):
        """Check whether the request Authorization header matches the payload."""
        try:
            auth_header = request.headers["Authorization"]
            logger_drf.debug("Got {auth_header=}")
        except KeyError:
            logger_drf.debug(f"No Authorization header {request.headers=}")
        if not auth_header or not auth_header.startswith(self.keyword + " "):
            logger_drf.debug(f"No Authorization header on request to DRF endpoint {request.path}")
            return None  # No attempt to authenticate

        provided_signature = auth_header[len(self.keyword) + 1 :].strip()
        logger_drf.debug(f"{provided_signature=}")
        payload = request.body
        logger_drf.debug(f"{payload=}")

        try:
            payload_data = json.loads(payload)
            logger_drf.debug(f"{payload_data=}")
        except JSONDecodeError:
            logger_drf.warning("Badly encoded json payload for authentication.")
            raise AuthenticationFailed(f"Failed to decode JSON payload for {request}")
        except Exception as e:
            logger_drf.debug(f"Error={e}")

        username = payload_data.get("student")

        # Try all keys
        for key_obj in APIKey.objects.all():
            key_bytes = (
                bytes.fromhex(key_obj.key) if isinstance(key_obj.key, str) and len(key_obj.key) == 128 else key_obj.key
            )
            computed = hmac.new(key_bytes, payload, hashlib.sha256).hexdigest()
            logger_drf.debug(f"{key_obj.key=}")
            logger_drf.debug(f"{provided_signature=}")
            logger_drf.debug(f"{computed=}")
            if hmac.compare_digest(computed, provided_signature):
                if not key_obj.is_active:
                    logger_drf.warning(f"Call made to drf endpoint with in active HMAC key {request}")
                    raise AuthenticationFailed("Deactivated key used for HMAC signature")
                # Authenticated — return a dummy user or associate with key owner
                user = get_user_model().objects.filter(username=username).first()
                logger_drf.debug(f"Authenticated drf endpoint with token for {user}")
                setattr(user, "hmac_authenticated", True)
                return (user or AnonymousUser(), None)

        logger_drf.warning(f"Out of date or unkrnown HMAC key ysed for {request}")

        raise AuthenticationFailed("Invalid HMAC signature")


def send_hmac_signed_request(payload, url=None, secret_key=None, headers=None):
    """Sends a POST request with HMAC authentication.

    Args:
        url (str): The endpoint URL.
        payload (dict): The JSON payload to send.
        secret_key (str): Hex-encoded or raw bytes secret key.
        headers (dict): Optional additional headers.

    Returns:
        requests.Response: The response object.
    """
    if secret_key is None:
        secret_key = os.envuiron.get("PHAS_API_KEY").decode()
    # Serialize payload deterministically
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    # Ensure key is bytes
    key_bytes = bytes.fromhex(secret_key) if isinstance(secret_key, str) and len(secret_key) == 128 else secret_key

    # Compute HMAC signature
    signature = hmac.new(key_bytes, body, hashlib.sha256).hexdigest()

    # Prepare headers
    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": signature,
        "User-Agent": "curl/7.88.1",
        "Accept": "*/*",
    }
    if headers:
        auth_headers.update(headers)

    # Send request
    response = requests.post(url, data=body, headers=auth_headers)
    return response
