from config.settings import *  # noqa: F401,F403

# 本机验收测试用 SQLite（CI/生产使用 PostgreSQL，行锁 FOR UPDATE 语义在 PG 生效）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
