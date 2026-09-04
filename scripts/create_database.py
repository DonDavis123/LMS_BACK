import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def create_database():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database_name = os.getenv("DB_NAME")

    if not all([host, port, user, password, database_name]):
        raise RuntimeError(
            "Database configuration is incomplete. "
            "Check your .env file."
        )

    print(f"Connecting to PostgreSQL at {host}:{port}... - create_database.py:23")

    connection = psycopg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname="postgres",
        autocommit=True,
    )

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database_name,),
            )

            database_exists = cursor.fetchone()

            if database_exists:
                print(
                    f"Database '{database_name}' already exists."
                )
                return

            cursor.execute(
                f'CREATE DATABASE "{database_name}"'
            )

            print(
                f"Database '{database_name}' created successfully."
            )

    finally:
        connection.close()


if __name__ == "__main__":
    create_database()