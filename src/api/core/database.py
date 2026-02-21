import os
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "root"),
    "database": os.getenv("DB_NAME", "horse_race_db"),
    "charset": "utf8mb4"
}

# 起動時にプールを作成
try:
    db_pool = MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **DB_CONFIG
    )
except Exception as e:
    # 開発環境ローカル実行対応用フォールバック
    DB_CONFIG["host"] = "localhost"
    db_pool = MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        **DB_CONFIG
    )

def get_db_connection():
    """コネクションプールからDBコネクションを取得して返す"""
    return db_pool.get_connection()
