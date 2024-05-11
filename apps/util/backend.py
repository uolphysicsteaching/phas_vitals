"""Subclass the standard django_auth_adfs backend for ourt purposes."""

# Python imports
import logging

# Django imports
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

# external imports
from django_auth_adfs import signals
from django_auth_adfs.backend import AdfsAuthCodeBackend
from django_auth_adfs.config import provider_config, settings

logger = logging.getLogger("django_auth_adfs")


class LeedsAdfsBaseBackend(AdfsAuthCodeBackend):
    """Subclass of AdfsAuthCodeBackend to customise user creation."""

    def process_access_token(self, access_token, adfs_response=None):
        """Check the user is ok by getting the Account object."""
        if not access_token:
            raise PermissionDenied

        logger.debug("Received access token: %s", access_token)
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
        logger.debug(f"Call to process_user_groups with {claims}")
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
            logger.error("User claim's doesn't have the claim '%s' in his claims: %s" % (username_claim, claims))
            raise PermissionDenied

        # The username claim we're getting back is aq full email address, but we just want the userid part
        username = claims[username_claim].split("@")[0].strip()
        userdata = {usermodel.USERNAME_FIELD: username}

        try:
            user = usermodel.objects.get(**userdata)
        except usermodel.DoesNotExist:  # No on the fly user creation here
            logger.debug(f"User '{username}' doesn't exist and creating users is disabled.")
            raise PermissionDenied
        if not user.password:
            user.set_unusable_password()
        return user

    # https://github.com/snok/django-auth-adfs/issues/241
    def update_user_attributes(self, user, claims, claim_mapping=None):
        """Stub method that eventually should do an ldap lookup."""
        logger.debug(f"Update requested for {user} with {claims}")
        return
        # At the moment I don't have outgoing msgraph.com I think
        url = "https://graph.microsoft.com/beta/me"

        obo_access_token = self.get_obo_access_token(self.access_token)
        logger.debug(f"Got on-behalf-of token {obo_access_token}")

        headers = {"Authorization": "Bearer {}".format(obo_access_token)}
        response = provider_config.session.get(url, headers=headers, timeout=30, verify=False)

        if response.status_code in [400, 401]:
            logger.error("MS Graph server returned an error: %s", response.json()["message"])
            raise PermissionDenied

        if response.status_code != 200:
            logger.error("Unexpected MS Graph response: %s", response.content.decode())
            raise PermissionDenied

        payload = response.json()
        logger.debug(f"Response to me {payload}")

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
