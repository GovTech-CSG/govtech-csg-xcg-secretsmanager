"""
@Author: Liu Peng (I2R), Yin Yide (GovTech CSG)
@Description: Middlware class for automatic refreshing of Django secret key from AWS Secrets Manager.
Copyright (c) 2023 by Institute for Infocomm Research (I2R) and GovTech CSG, All Rights Reserved.
"""

import json
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.deprecation import MiddlewareMixin

from govtech_csg_xcg.secretsmanager import logger
from govtech_csg_xcg.secretsmanager.clients import (
    ConfigurationError,
    SecretRetrievalError,
    SecretsManager,
)


class SecretKeyRefreshMiddleware(MiddlewareMixin):
    """Middleware that periodically updates Django's secret key from AWS Secrets Manager."""

    def __init__(self, get_response):
        super().__init__(get_response)

        # First validate the required config values.
        config_dict = getattr(settings, "XCG_DJANGO_SECRET_KEY_REFRESH_CONFIG", None)
        if config_dict is None or not isinstance(config_dict, dict):
            raise ImproperlyConfigured(
                "Invalid or missing config for XCG SecretKeyRefreshMiddleware"
            )

        # Get the value of secret_arn and remove the key as it will not be needed anymore.
        secret_arn = config_dict.get("secret_arn")
        if not secret_arn:
            raise ImproperlyConfigured(
                '"secret_arn" is required to configure XCG SecretKeyRefreshMiddleware'
            )
        self.secret_arn = secret_arn

        # Get the value of secret_keyname and remove the key as it will not be needed anymore.
        secret_keyname = config_dict.get("secret_keyname")
        if not secret_keyname:
            secret_keyname = "DJANGO_SECRET_KEY"  # Set default keyname if not include the 'secret_keyname' configuration value

        self.secret_keyname = secret_keyname

        try:
            self.secrets_manager = SecretsManager.init_from_config_dict(config_dict)
        except ConfigurationError as err:
            raise ImproperlyConfigured(
                f"Error configuring SecretsManager for XCG secret key refresh middleware: {err}"
            ) from None

        self.refresh_interval = config_dict.get("refresh_interval", 3600)
        self.last_refreshed_time = time.time()

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        return response

    def process_request(self, request):
        current_time = time.time()
        if current_time - self.last_refreshed_time >= self.refresh_interval:
            # We set this early so as to fail transparently and not
            # cause repeated attempts at retrieving the secret if an
            # error is encountered.
            self.last_refreshed_time = current_time
            logger.info("Attempting to refresh Django secret key")
            try:
                secret_string = self.secrets_manager.get_secret_string(self.secret_arn)
                retrieved_secret_key = json.loads(secret_string)[self.secret_keyname]
            # We log and suppress the error here rather than propagate
            # upwards so as to not show the user a 5XX HTTP error if
            # this fails, since secret key refresh is not critical
            # to the functionality of the application. However, we
            # still log the error so that devs can be alerted.
            except SecretRetrievalError as err:
                logger.error(
                    f"Unable to retrieve Django secret key from Secrets Manager: {err}"
                )
                return
            except json.JSONDecodeError:
                logger.error(
                    "Unable to load Secrets Manager secret string as Python dict"
                )
                return
            except KeyError:
                logger.error(
                    "Unable to find DJANGO_SECRET_KEY in Secrets Manager secret dict"
                )
                return
            else:
                logger.info("Retrieved Django secret key from Secrets Manager")

            if retrieved_secret_key != settings.SECRET_KEY:
                logger.info("Django secret key changed, attempting to rotate")
                # In the case where the secret key in Secrets Manager is changed,
                # we need to gracefully rotate out the current key by placing it
                # into settings.SECRET_KEY_FALLBACKS. This feature is only supported
                # for Django 4.1 and later, and users don't need to explicitly
                # initialise it with an empty list. See link below:
                # https://docs.djangoproject.com/en/4.1/ref/settings/#secret-key-fallbacks
                if hasattr(settings, "SECRET_KEY_FALLBACKS"):
                    # We only allow for one fallback key at a time.
                    # This is to prevent accumulation of many fallback
                    # keys over time, which will affect performance since
                    # each key has to be tried one by one.
                    settings.SECRET_KEY_FALLBACKS = [settings.SECRET_KEY]
                    logger.info(
                        "Added old Django secret key to settings.SECRET_KEY_FALLBACKS"
                    )
                else:
                    logger.warning(
                        "settings.SECRET_KEY_FALLBACKS does not exist; "
                        "Proceeding with rotation without fallback"
                    )

                settings.SECRET_KEY = retrieved_secret_key
                logger.info("Changed to new Django secret key from Secrets Manager")
            else:
                logger.info("Django secret key not changed, no rotation needed")
