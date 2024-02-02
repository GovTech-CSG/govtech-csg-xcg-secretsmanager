"""
@Author: Liu Peng (I2R), Yin Yide (GovTech CSG)
@Description: Secrets Manager and Cache Secrets Manager clients.
Copyright (c) 2023 by Institute for Infocomm Research (I2R) and GovTech CSG, All Rights Reserved.
"""

import boto3
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
from botocore.exceptions import BotoCoreError, ClientError


class SecretsManager:
    """Wrapper class around the AWS Secrets Manager client from boto3."""

    def __init__(
        self,
        region_name: str = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        profile_name: str = None,
    ):
        try:
            self._session = boto3.session.Session(
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                profile_name=profile_name,
            )
            self._client = self._session.client("secretsmanager")
        except BotoCoreError as err:
            # NOTE: Refer to link below for description of all the Botocore static exceptions
            # https://github.com/boto/botocore/blob/develop/botocore/exceptions.py
            #
            # We raise from None to disable exception chaining:
            # https://docs.python.org/3/tutorial/errors.html#exception-chaining
            raise ConfigurationError(
                f"Configuration error when initializing XCG {self.__class__.__name__}: {err}"
            ) from None

        if self._session.get_credentials() is None:
            raise ConfigurationError(
                f"Could not find AWS credentials when initializing XCG {self.__class__.__name__}"
            ) from None

    @classmethod
    def init_from_config_dict(cls, config_dict: dict):
        # We provide this class method as a convenience
        # method for the middleware and DB backends, who
        # rely on similar methods of configuration (i.e.
        # using a dict containing config values).
        return cls(
            region_name=config_dict.get("region_name"),
            aws_access_key_id=config_dict.get("aws_access_key_id"),
            aws_secret_access_key=config_dict.get("aws_secret_access_key"),
            aws_session_token=config_dict.get("aws_session_token"),
            profile_name=config_dict.get("profile_name"),
        )

    def get_secret_string(self, secret_name: str, version_stage: str = None):
        """Returns a secret string for a given AWS Secrets Manager secret.

        Args:
            secret_name: String that identifies the secret to be retrieved. This can be the secret's
                full ARN, the secret's partial ARN (e.g. 'secretname-nutBrk'), or the secret's human
                readable name. The recommendation is to use the full ARN if using ARN at all.
            version_stage: String that identifies the staging label of the secret value to be retrieved.
                Possible values are "AWSPREVIOUS", "AWSCURRENT", and "AWSPENDING". Default is "AWSCURRENT".

        Returns:
            A string representing the value of the specified secret. Note that this could be in the
            format of a JSON string if the secret was defined as key-value pairs, or it could just
            be a normal string if the secret was defined in plaintext. See examples below:

            JSON string: '{"secret_name":"secret_value"}'
            Normal string: 'secret_value'

        Raises:
            SecretRetrievalError: Raised if any errors occur while attempting to retrieve the secret
                from AWS Secrets Manager.
        """
        try:
            response = self._client.get_secret_value(
                SecretId=secret_name,
                VersionStage=version_stage if version_stage else "AWSCURRENT",
            )
        except ClientError as err:
            code = err.response["Error"]["Code"]
            msg = err.response["Error"]["Message"]
            raise SecretRetrievalError(
                f'Error occurred while retrieving secret "{secret_name}": {code} - {msg}'
            ) from None

        if "SecretString" not in response:
            raise SecretRetrievalError(
                f"Unable to obtain secret string for {secret_name}"
            )

        return response["SecretString"]

    def get_previous_secret_string(self, secret_name: str):
        return self.get_secret_string(secret_name, version_stage="AWSPREVIOUS")


class CacheSecretsManager(SecretsManager):
    """Wrapper class around the AWS Secrets Manager client from boto3."""

    def __init__(self, refresh_interval: int = 3600, **kwargs):
        super().__init__(**kwargs)
        self._configure_secret_cache(refresh_interval)

    def _configure_secret_cache(self, refresh_interval):
        # Note: This hidden method is not meant to be called by client code
        # as it will reset the existing cache, which may not be the intended effect.
        secret_cache_config = SecretCacheConfig(
            secret_refresh_interval=refresh_interval
        )
        self._secret_cache = SecretCache(
            config=secret_cache_config, client=self._client
        )

    @classmethod
    def init_from_config_dict(cls, config_dict: dict):
        cache_secrets_manager = super().init_from_config_dict(config_dict)
        cache_secrets_manager._configure_secret_cache(
            config_dict.get("refresh_interval", 3600)
        )
        return cache_secrets_manager

    def get_secret_string(
        self, secret_name: str, version_stage: str = None, force_refresh: bool = False
    ):
        """Returns a (cached) secret string for a given AWS Secrets Manager secret.

        Args:
            secret_name: String that identifies the secret to be retrieved. This can be the secret's
                full ARN, the secret's partial ARN (e.g. 'secretname-nutBrk'), or the secret's human
                readable name. The recommendation is to use the full ARN if using ARN at all.
            version_stage: String that identifies the staging label of the secret value to be retrieved.
                Possible values are "AWSPREVIOUS", "AWSCURRENT", and "AWSPENDING". Default is "AWSCURRENT".
            force_refresh: Boolean value that indicates whether or not to force a refresh before the
                regular refresh interval.

        Returns:
            A string representing the value of the specified secret. Note that this could be in the
            format of a JSON string if the secret was defined as key-value pairs, or it could just
            be a normal string if the secret was defined in plaintext. See examples below:

            JSON string: '{"secret_name":"secret_value"}'
            Normal string: 'secret_value'

        Raises:
            SecretRetrievalError: Raised if any errors occur while attempting to retrieve the secret
                from AWS Secrets Manager.
        """
        try:
            if force_refresh:
                self._refresh_now(secret_name)

            secret_string = self._secret_cache.get_secret_string(
                secret_name,
                version_stage=version_stage
                if version_stage is not None
                else "AWSCURRENT",
            )
        except ClientError as err:
            code = err.response["Error"]["Code"]
            msg = err.response["Error"]["Message"]
            raise SecretRetrievalError(
                f'Error occurred while retrieving/refreshing secret "{secret_name}": {code} - {msg}'
            ) from None

        # We handle this case because the underlying caching library can return None.
        # We raise an exception in this situation in order to be consistent with
        # the behaviour of the SecretsManager class.
        if secret_string is None:
            raise SecretRetrievalError(
                f"Unable to obtain secret string for {secret_name}"
            )

        return secret_string

    def get_previous_secret_string(self, secret_name: str, force_refresh: bool = False):
        return self.get_secret_string(
            secret_name, version_stage="AWSPREVIOUS", force_refresh=force_refresh
        )

    def _refresh_now(self, secret_name: str):
        # NOTE: When a secret name is refreshed, the underlying SecretCache refreshes
        # the value for all versions, not just AWSCURRENT. i.e. If I invoke
        # sm.get_secret_string(name, version_stage='AWSCURRENT', force_refresh=True),
        # the value of 'AWSPREVIOUS' will be refreshed in our cache as well.
        secret_cache_item = self._secret_cache._get_cached_secret(secret_name)
        secret_cache_item._refresh_needed = True
        secret_cache_item._execute_refresh()


class ConfigurationError(Exception):
    """Raised if there are any configuration errors when initializing a client."""


class SecretRetrievalError(Exception):
    """Raised when an error occurs while retrieving secret value from AWS Secrets Manager."""
