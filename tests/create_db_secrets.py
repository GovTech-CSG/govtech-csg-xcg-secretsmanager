import json
import os

import boto3

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-1"

# When Django initialises, it tries to initialise the database backends.
# For that to happen without error, we need to have created the fake secrets
# for MySQL beforehand. By placing this code at the module level, we achieve
# that effect. Note that these require the Moto standalone server to be running.
BOTO3_CLIENT = boto3.client("secretsmanager", endpoint_url="http://localhost:5000")
CREDENTIALS = {
    "mysql-creds": {
        "engine": "mysql",
        "host": "localhost",
        "username": os.environ["MYSQL_USERNAME"],
        "password": os.environ["MYSQL_PASSWORD"],
        "dbname": "mysql_secretsmanager_test",
        "port": "3306",
    },
    "postgresql-creds": {
        "engine": "postgres",
        "host": "localhost",
        "username": os.environ["POSTGRESQL_USERNAME"],
        "password": os.environ["POSTGRESQL_PASSWORD"],
        "dbname": "postgresql_secretsmanager_test",
        "port": "5432",
    },
}

response = BOTO3_CLIENT.list_secrets()
if not response["SecretList"]:
    for secret_name in ("mysql-creds", "postgresql-creds"):
        BOTO3_CLIENT.create_secret(
            Name=secret_name, SecretString=json.dumps(CREDENTIALS[secret_name])
        )
