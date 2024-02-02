"""
@Author: Liu Peng (I2R), Yin Yide (GovTech CSG)
@Description: Wrapper class around the MySQL database wrapper provided by Django, to enable retrieval of secrets from AWS Secrets Manager.
Copyright (c) 2023 by Institute for Infocomm Research (I2R) and GovTech CSG, All Rights Reserved.
"""

from django.db.backends.mysql import base

from govtech_csg_xcg.secretsmanager.db.common import DatabaseCredentials


class DatabaseWrapper(base.DatabaseWrapper):
    """Wrapper class around the MySQL database wrapper."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sm_config = self.settings_dict.get("AWS_SECRETSMANAGER_CONFIG", {})
        self.db_creds = DatabaseCredentials(sm_config)

    def get_connection_params(self):
        self.db_creds.fill_settings_dict(self.settings_dict, default_port=3306)
        return super().get_connection_params()
