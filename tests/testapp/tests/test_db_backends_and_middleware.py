import json
import logging
import os
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import boto3
import requests
from django.conf import settings
from django.db import close_old_connections
from django.test import Client
from parameterized import parameterized_class

# Set up dummy AWS credentials to prevent accidental mutation of real infrastructure
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-1"

SESSION = requests.Session()


def start_moto_recording():
    """Start the moto recorder service, which records API calls to the mock AWS API server."""
    SESSION.post("http://localhost:5000/moto-api/recorder/reset-recording")
    SESSION.post("http://localhost:5000/moto-api/recorder/start-recording")


def stop_moto_recording():
    """Stop the moto recorder service and return the log in text form."""
    SESSION.post("http://localhost:5000/moto-api/recorder/stop-recording")
    return SESSION.get(
        "http://localhost:5000/moto-api/recorder/download-recording"
    ).text


@parameterized_class(
    [
        {"engine": "mysql"},
        {"engine": "postgresql"},
    ]
)
class TestDatabaseBackends(unittest.TestCase):
    """Test case for both the MySQL and PostgreSQL database backends."""

    def setUp(self):
        self.db_alias = f"{self.engine}_test"
        self.client = Client()
        self.requests_session = requests.Session()

        # Make an initial request to ensure initial secret retrieval has occurred
        self.client.get(f"/{self.engine}/")
        # Close old connections so that the next DB query will have to
        # establish a new connection by calling get_connection_params
        # Normally this would happen automatically, but Django's test
        # runner purposely doesn't close existing connections (maybe for performance?).
        close_old_connections()

    def test_backend_allows_database_access(self):
        response = self.client.get(f"/{self.engine}/")
        self.assertEqual(response.status_code, 200)

    def test_backend_uses_cached_credentials_before_refresh_interval(self):
        start_moto_recording()
        response = self.client.get(f"/{self.engine}/")
        raw_log_str = stop_moto_recording()

        self.assertEqual(response.status_code, 200)
        # We are asserting that no AWS API calls were made to the moto server.
        # This should be the case if cached credentials were used
        self.assertEqual(raw_log_str, "")

    def test_backend_retrieves_new_creds_after_refresh_interval(self):
        # Make an initial request to ensure initial secret retrieval has occurred
        response = self.client.get(f"/{self.engine}/")
        # Close old connections so that the next DB query will have to
        # establish a new connection by calling get_connection_params
        # Normally this would happen automatically, but Django's test
        # runner purposely doesn't close existing connections (maybe for performance?).
        close_old_connections()

        # Make a second request and mock the time so that it looks like time to refresh.
        # We use moto's recorder feature to record the requests made to the AWS API.
        start_moto_recording()
        with patch(
            "aws_secretsmanager_caching.cache.items.datetime", autospec=True
        ) as mock_datetime:
            mock_datetime.utcnow = Mock(
                return_value=datetime.utcnow()
                + timedelta(seconds=settings.TEST_REFRESH_INTERVAL)
            )
            response = self.client.get(f"/{self.engine}/")
        raw_log_str = stop_moto_recording()

        self.assertEqual(response.status_code, 200)
        # We are asserting that AWS API calls were made to the moto server.
        # This should be the case if credentials were refreshed.
        self.assertNotEqual(raw_log_str, "")


# Disable informational logging to prevent cluttered test logs.
logging.getLogger("secretsmanager").setLevel(logging.ERROR)


class TestSecretKeyRefreshMiddleware(unittest.TestCase):
    """Test case for govtech_csg_xcg.secretsmanager.middleware.SecretKeyRefreshMiddleware."""

    @classmethod
    def setUpClass(cls):
        boto3_client = boto3.client(
            "secretsmanager", endpoint_url="http://localhost:5000"
        )
        boto3_client.create_secret(
            Name="test-django-secret-key",
            SecretString=json.dumps({"DJANGO_SECRET_KEY": settings.NEW_SECRET_KEY}),
        )

    @classmethod
    def tearDownClass(cls):
        boto3_client = boto3.client(
            "secretsmanager", endpoint_url="http://localhost:5000"
        )
        boto3_client.delete_secret(
            SecretId="test-django-secret-key", ForceDeleteWithoutRecovery=True
        )

    def setUp(self):
        self.client = Client()
        # Reset the secret key settings so that we start on a clean slate.
        settings.SECRET_KEY = settings.OLD_SECRET_KEY
        settings.SECRET_KEY_FALLBACKS = []

    def test_no_refresh_before_interval(self):
        response = self.client.get("/get_secret_key/")
        self.assertEqual(response.content.decode("utf-8"), settings.OLD_SECRET_KEY)

    def test_refresh_happens_after_interval(self):
        start_moto_recording()
        with patch(
            "govtech_csg_xcg.secretsmanager.middleware.time", autospec=True
        ) as mock_time:
            mock_time.time = Mock(
                side_effect=[time.time(), time.time() + settings.TEST_REFRESH_INTERVAL]
            )
            response = self.client.get("/get_secret_key/")
        raw_log_str = stop_moto_recording()

        self.assertNotEqual(raw_log_str, "")
        self.assertEqual(response.content.decode("utf-8"), settings.NEW_SECRET_KEY)

    def test_secret_key_fallbacks_is_populated_after_refresh(self):
        with patch(
            "govtech_csg_xcg.secretsmanager.middleware.time", autospec=True
        ) as mock_time:
            mock_time.time = Mock(
                side_effect=[time.time(), time.time() + settings.TEST_REFRESH_INTERVAL]
            )
            self.client.get("/get_secret_key/")

        self.assertTrue(hasattr(settings, "SECRET_KEY_FALLBACKS"))
        self.assertEqual(len(settings.SECRET_KEY_FALLBACKS), 1)
        self.assertEqual(settings.SECRET_KEY_FALLBACKS[0], settings.OLD_SECRET_KEY)
