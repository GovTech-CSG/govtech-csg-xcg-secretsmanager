#!/bin/bash

unset AWS_ENDPOINT_URL AWS_ENDPOINT_URL_SECRETS_MANAGER
moto_server > /dev/null 2>&1 &
export AWS_ENDPOINT_URL_SECRETS_MANAGER=http://localhost:5000
python3 create_db_secrets.py

echo -e "Migrating mysql_test database\n"
python3 manage.py migrate --database mysql_test
MYSQL_RETVAL=$?
echo -e "\nMigrating postgresql_test database\n"
python3 manage.py migrate --database postgresql_test
POSTGRESQL_RETVAL=$?

pkill moto_server
rm -f moto_recording
unset AWS_ENDPOINT_URL_SECRETS_MANAGER

if [[ $MYSQL_RETVAL -gt 0 || $POSTGRESQL_RETVAL > 0 ]]
then
    exit 1
fi
