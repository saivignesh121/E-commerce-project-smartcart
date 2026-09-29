import time
from pathlib import Path

import mysql.connector
from mysql.connector import Error

import config


MAX_RETRIES = 12
RETRY_DELAY_SECONDS = 5


def connect_with_retry():
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return mysql.connector.connect(
                host=config.DB_HOST,
                port=config.DB_PORT,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
            )
        except Error as exc:
            last_error = exc
            print(f"Database connection attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    raise last_error


def initialize_database():
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")

    connection = connect_with_retry()
    cursor = connection.cursor()

    try:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        connection.commit()
        print("SmartCart MySQL tables are ready.")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    initialize_database()
