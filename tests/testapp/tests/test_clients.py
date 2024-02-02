import json
import os
import unittest

import boto3
from moto import mock_secretsmanager
from parameterized import parameterized_class

from govtech_csg_xcg.secretsmanager.clients import (
    CacheSecretsManager,
    SecretRetrievalError,
    SecretsManager,
)

# Set up dummy AWS credentials to prevent accidental mutation of real infrastructure
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@parameterized_class(
    "client_attr_name",
    [
        ("sm",),
        ("cache_sm",),
    ],
)
@mock_secretsmanager
class TestSecretsRetrieval(unittest.TestCase):
    """Test case for both the SecretsManager and CacheSecretsManager class.

    This test case focuses on basic secrets retrieval functionality that is common
    to both classes. The tests below have been parameterized so as to minimize duplication.
    """

    def setUp(self):
        # Create a secret and update its value to create current and previous versions.
        self.boto3_client = boto3.client("secretsmanager")
        response = self.boto3_client.create_secret(
            Name="test-secret",
            SecretString=json.dumps({"value": "previous-test-secret-string"}),
        )
        self.boto3_client.put_secret_value(
            SecretId=response["ARN"],
            SecretString=json.dumps({"value": "test-secret-string"}),
        )

        # Instantiate one of each client type for testing.
        # We will use the parameterized arguments 'sm' and 'cache_sm' to refer to these clients.
        self.sm = SecretsManager()
        self.cache_sm = CacheSecretsManager()

    def test_get_secret_string_returns_correct_string(self):
        client = self.__dict__[self.client_attr_name]
        secret_string = json.loads(client.get_secret_string("test-secret"))["value"]
        self.assertEqual(secret_string, "test-secret-string")

    def test_get_previous_secret_string_returns_correct_string(self):
        client = self.__dict__[self.client_attr_name]
        secret_string = json.loads(client.get_previous_secret_string("test-secret"))[
            "value"
        ]
        self.assertEqual(secret_string, "previous-test-secret-string")

    def test_get_secret_string_raises_exception_if_not_found(self):
        client = self.__dict__[self.client_attr_name]
        with self.assertRaises(SecretRetrievalError):
            client.get_secret_string("non-existent-secret")

    def test_get_previous_secret_string_raises_exception_if_not_found(self):
        client = self.__dict__[self.client_attr_name]
        with self.assertRaises(SecretRetrievalError):
            client.get_previous_secret_string("non-existent-secret")

    def test_get_previous_secret_string_raises_exception_if_no_previous_version(self):
        self.boto3_client.create_secret(
            Name="test-secret-with-no-previous-version",
            SecretString=json.dumps({"value": "test-secret-string"}),
        )

        client = self.__dict__[self.client_attr_name]
        with self.assertRaises(SecretRetrievalError):
            client.get_previous_secret_string("test-secret-with-no-previous-version")

    def test_get_secret_string_raises_exception_if_not_string(self):
        self.boto3_client.create_secret(
            Name="test-binary-secret",
            SecretBinary=b"test-secret-bytes",
        )

        client = self.__dict__[self.client_attr_name]
        with self.assertRaises(SecretRetrievalError):
            client.get_secret_string("test-binary-secret")

    def test_get_previous_secret_string_raises_exception_if_not_string(self):
        response = self.boto3_client.create_secret(
            Name="test-binary-secret",
            SecretBinary=b"previous-test-secret-bytes",
        )
        self.boto3_client.put_secret_value(
            SecretId=response["ARN"],
            SecretString="test-secret-string",
        )

        client = self.__dict__[self.client_attr_name]
        with self.assertRaises(SecretRetrievalError):
            client.get_previous_secret_string("test-binary-secret")


@mock_secretsmanager
class TestSecretsCaching(unittest.TestCase):
    """Test case for the caching functionality of the CacheSecretsManager class.

    This test case focuses on the caching capabilities of CacheSecretsManager.
    Basic secrets retrieval functionality is included in the TestSecretsRetrieval test case above.
    """

    def setUp(self):
        # Create a secret and update its value to create current and previous versions.
        self.boto3_client = boto3.client("secretsmanager")
        response = self.boto3_client.create_secret(
            Name="test-secret",
            SecretString=json.dumps({"value": "test-secret-string-1"}),
        )
        self.secret_arn = response["ARN"]
        self.boto3_client.put_secret_value(
            SecretId=self.secret_arn,
            SecretString=json.dumps({"value": "test-secret-string-2"}),
        )

        self.cache_sm = CacheSecretsManager(refresh_interval=3600)

    def test_get_secret_string_caches_value(self):
        secret_string_before_update = self.cache_sm.get_secret_string("test-secret")
        self.boto3_client.put_secret_value(
            SecretId=self.secret_arn,
            SecretString=json.dumps({"value": "test-secret-string-3"}),
        )
        secret_string_after_update = self.cache_sm.get_secret_string("test-secret")

        self.assertEqual(secret_string_before_update, secret_string_after_update)
        self.assertEqual(
            secret_string_after_update, json.dumps({"value": "test-secret-string-2"})
        )

    def test_get_previous_secret_string_caches_value(self):
        secret_string_before_update = self.cache_sm.get_previous_secret_string(
            "test-secret"
        )
        self.boto3_client.put_secret_value(
            SecretId=self.secret_arn,
            SecretString=json.dumps({"value": "test-secret-string-3"}),
        )
        secret_string_after_update = self.cache_sm.get_previous_secret_string(
            "test-secret"
        )

        self.assertEqual(secret_string_before_update, secret_string_after_update)
        self.assertEqual(
            secret_string_after_update, json.dumps({"value": "test-secret-string-1"})
        )

    def test_get_secret_string_with_force_refresh_updates_cache(self):
        secret_string_before_update = self.cache_sm.get_secret_string("test-secret")
        self.boto3_client.put_secret_value(
            SecretId=self.secret_arn,
            SecretString=json.dumps({"value": "test-secret-string-3"}),
        )
        secret_string_after_update = self.cache_sm.get_secret_string(
            "test-secret", force_refresh=True
        )

        self.assertEqual(
            secret_string_before_update, json.dumps({"value": "test-secret-string-2"})
        )
        self.assertEqual(
            secret_string_after_update, json.dumps({"value": "test-secret-string-3"})
        )

    def test_get_previous_secret_string_with_force_refresh_updates_cache(self):
        secret_string_before_update = self.cache_sm.get_previous_secret_string(
            "test-secret"
        )
        self.boto3_client.put_secret_value(
            SecretId=self.secret_arn,
            SecretString=json.dumps({"value": "test-secret-string-3"}),
        )
        secret_string_after_update = self.cache_sm.get_previous_secret_string(
            "test-secret", force_refresh=True
        )

        self.assertEqual(
            secret_string_before_update, json.dumps({"value": "test-secret-string-1"})
        )
        self.assertEqual(
            secret_string_after_update, json.dumps({"value": "test-secret-string-2"})
        )
