import ssl

from sqlalchemy.ext.asyncio import create_async_engine

from app.db import _connect_args, normalize_database_url

AIVEN = "mysql://avnadmin:s3cret@mysql-edu-proj.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED"


def test_aiven_url_uses_async_driver_and_keeps_credentials():
    url, ssl_mode = normalize_database_url(AIVEN)
    assert url.drivername == "mysql+aiomysql"
    assert (url.username, url.password, url.host, url.port, url.database) == (
        "avnadmin", "s3cret", "mysql-edu-proj.aivencloud.com", 12345, "defaultdb"
    )
    assert ssl_mode == "REQUIRED"
    assert "ssl-mode" not in url.query and url.query["charset"] == "utf8mb4"


def test_aiven_url_creates_engine_without_mysqldb():
    url, ssl_mode = normalize_database_url(AIVEN)
    engine = create_async_engine(url, connect_args=_connect_args(url, ssl_mode))
    assert engine.dialect.driver == "aiomysql"


def test_ssl_mode_required_without_ca_encrypts_without_verifying():
    url, ssl_mode = normalize_database_url(AIVEN)
    context = _connect_args(url, ssl_mode)["ssl"]
    assert isinstance(context, ssl.SSLContext) and context.verify_mode == ssl.CERT_NONE


def test_already_async_url_and_sqlite_are_unchanged():
    url, ssl_mode = normalize_database_url("mysql+aiomysql://u:p@localhost:3306/edu?charset=utf8mb4")
    assert url.drivername == "mysql+aiomysql" and ssl_mode is None
    assert _connect_args(url, ssl_mode) == {}
    url, ssl_mode = normalize_database_url("sqlite+aiosqlite:///./dev.db")
    assert url.drivername == "sqlite+aiosqlite" and ssl_mode is None
