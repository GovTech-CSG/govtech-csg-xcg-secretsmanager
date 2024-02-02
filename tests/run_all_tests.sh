#!/bin/bash

# Unset these environment variables to start from a clean slate.
unset AWS_ENDPOINT_URL AWS_ENDPOINT_URL_SECRETS_MANAGER

# First run the tests for the SecretsManager and CacheSecretsManager clients.
echo -e "Running tests for SecretsManager and CacheSecretsManager clients\n"
python3 manage.py test testapp.tests.test_clients --noinput

# Next run the tests for the MySQL and PostgreSQL database backends, as well as the secrets refresh middleware.
echo -e "\nRunning tests for database backends and secrets refresh middleware\n"

# These tests require the moto server to be running first, and for the DB secrets to be created
# before tests are run so that Django initialization does not fail.
moto_server > /dev/null 2>&1 &
export AWS_ENDPOINT_URL_SECRETS_MANAGER=http://localhost:5000
python3 create_db_secrets.py
python3 manage.py test testapp.tests.test_db_backends_and_middleware --noinput
TESTS_RET_VAL=$?

# Clean up by shutting down the moto server and removing the recording file.
pkill moto_server
rm -f moto_recording
unset AWS_ENDPOINT_URL_SECRETS_MANAGER
if [ $TESTS_RET_VAL -gt 0 ]
then
    exit 1
else
    exit 0
fi
