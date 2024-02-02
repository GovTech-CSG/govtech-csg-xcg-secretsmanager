# govtech-csg-xcg-secretsmanager

This package belongs to the **eXtended Code Guardrails (XCG)** project, which consists of a series of packages that harden the Django web framework to prevent common web application vulnerabilities.

Specifically, the Secrets Manager package provides AWS Secrets Manager support for Django secret key as well as database backends (MySQL and PostgreSQL).

*Do note that the README in this repository is intentionally limited in scope and is catered towards developers. For detailed instructions on installation, usage, and community guidelines, please refer to the published documentation at https://xcg.tech.gov.sg.*

## Security-related matters

For instructions on how to **report a vulnerability**, refer to the [official documentation website](https://xcg.tech.gov.sg/community/vulnerabilities).

Additionally, **enable email alerts for security issues by "watching" this repository**. The "watch" button can be found near the top right corner of this repo's home page, and there are various options for configuring notification volume. To receive security alerts, either enable notifications for **"All Activity"** or **"Custom -> Security alerts"**.

## Installing development dependencies

Before building or testing the package, or committing changes, install the development dependencies into a virtual environment:

```sh
# In the project root directory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Building

The package can be built using [`build`](https://pypa-build.readthedocs.io/en/latest/) as the build frontend and [`setuptools`](https://setuptools.pypa.io/en/latest/) as the build backend.

Run the build command below:

```sh
# In the project root directory
python -m build .
```

This creates a directory named `dist/`, which should contain 2 files:

1. A `.whl` (wheel) file, which is a [binary distribution format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/) for Python packages
2. A `.tar.gz` file, which is a [source distribution format](https://packaging.python.org/en/latest/specifications/source-distribution-format/) for Python packages

To view the source files included in the source distribution, use the `tar` utility as follows:

```sh
tar --list -f dist/<filename>.tar.gz
```

To install the package directly from either distribution files:

```sh
pip install <name_of_distribution_file>
```

## Testing

### Prerequisites

To run the tests for database backends, you have to first install MySQL and PostgreSQL on your development machine. Refer to the official documentation for installation instructions. Take note that your services should be running locally using their default ports (3306 for MySQL and 5432 for PostgreSQL).

Having installed and started the database services, create a test user and a test database in each as targets for the test application. You can use the commands below for reference:

**MySQL**
```sql
CREATE USER 'secretsmanager_test'@'localhost' IDENTIFIED BY 'Password123!';
GRANT ALL PRIVILEGES ON *.* TO 'secretsmanager_test'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
CREATE DATABASE mysql_secretsmanager_test CHARACTER SET utf8;
```

**PostgreSQL**
```sql
CREATE USER secretsmanager_test WITH PASSWORD 'Password123!';
ALTER USER secretsmanager_test WITH SUPERUSER;
CREATE DATABASE postgresql_secretsmanager_test ENCODING 'UTF8';
```

### Running the tests

Before running the tests, you should have already created a virtual environment and installed all the development dependencies. If not, please follow the [instructions above](#installing-development-dependencies) to install them.

With the development dependencies installed, perform an editable install of the Secrets Manager package itself:

```sh
# Note: This command should be run from the project's root directory.
pip install -e .
```

Export the credentials for both database services as environment variables. This is required by the `create_db_secrets.py` script to create mock AWS Secrets Manager secrets for the Django application to use.

```sh
export MYSQL_USERNAME=<your_username>
export MYSQL_PASSWORD=<your_password>
export POSTGRESQL_USERNAME=<your_username>
export POSTGRESQL_PASSWORD=<your_password>
```

Change to the `tests` directory and run the stored database migrations for both configured databases (`mysql_test` and `postgresql_test`) using the helper script `migrate_all_databases.sh`.

```sh
cd tests/
/bin/bash migrate_all_databases.sh
```

Finally, staying within the `tests` directory, run unit tests using the helper script `run_all_tests.sh`.

```sh
/bin/bash run_all_tests.sh
```

## Running pre-commit hooks

*Note: This section is only relevant if you intend to contribute code*

This project uses the [`pre-commit` tool](https://pre-commit.com) to run Git pre-commit hooks for linting and code quality checks. The `pre-commit` tool itself should have been installed along with the [development dependencies](#installing-development-dependencies). After cloning the repository **for the first time**, run the command below to "install" the Git hooks:

```sh
pre-commit install
```

The command above creates a file `.git/hooks/pre-commit`, which defines the shell commands to run before any Git commit is created.

Subsequently, any invocation of `git commit` will trigger the commands, rejecting the commit if there are linting errors. Issues should be automatically fixed, but you will need to re-stage the changes before attempting the commit again.

For a list of hooks run by `pre-commit`, see its [configuration file](.pre-commit-config.yaml).
