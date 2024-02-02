"""
@Author: Liu Peng (I2R), Yin Yide (GovTech CSG)
@Description: Class that represents database credentials stored in AWS Secrets Manager.
Copyright (c) 2023 by Institute for Infocomm Research (I2R) and GovTech CSG, All Rights Reserved.
"""

import json

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

from govtech_csg_xcg.secretsmanager.clients import (
    CacheSecretsManager,
    ConfigurationError,
    SecretRetrievalError,
)


class DatabaseCredentials:
    """Class that represents DB credentials retrieved from AWS Secrets Manager."""

    def __init__(self, config_dict):
        secret_arn = config_dict.get("secret_arn")
        if not secret_arn:
            raise ImproperlyConfigured(
                'Missing key "secret_arn" in database configuration'
            )
        self.secret_arn = secret_arn

        try:
            self.cache_secrets_manager = CacheSecretsManager.init_from_config_dict(
                config_dict
            )
        except ConfigurationError as err:
            raise ImproperlyConfigured(
                f"Missing or invalid database configuration value(s): {err}"
            ) from None

    def fill_settings_dict(self, settings_dict, default_port, force_refresh=False):
        try:
            secret_json = self.cache_secrets_manager.get_secret_string(
                self.secret_arn, force_refresh=force_refresh
            )
            secret_dict = json.loads(secret_json)
        except SecretRetrievalError as err:
            raise DatabaseError(
                f"Could not retrieve values of database connection parameters from Secrets Manager: {err}"
            ) from None

        settings_dict["USER"] = secret_dict["username"]
        settings_dict["PASSWORD"] = secret_dict["password"]
        settings_dict["HOST"] = secret_dict["host"]
        settings_dict["PORT"] = (
            int(secret_dict["port"]) if "port" in secret_dict else default_port
        )
        settings_dict["NAME"] = secret_dict.get("dbname")


class ConnectionError(Exception):
    """Raised when the database backend is unable to get a new connection."""
