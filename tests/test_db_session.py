"""Las conexiones pasan por el pooler de Supabase en modo transacción.

asyncpg numera los prepared statements por conexión (__asyncpg_stmt_1__, …), y dos
conexiones que comparten backend en el pooler chocaban con
DuplicatePreparedStatementError. Cada statement debe llevar un nombre único.
"""
import re

from app.db.session import _CONNECT_ARGS


def test_nombres_de_prepared_statements_unicos():
    nombre = _CONNECT_ARGS["prepared_statement_name_func"]
    nombres = {nombre() for _ in range(1000)}

    assert len(nombres) == 1000
    for n in nombres:
        assert re.fullmatch(r"__asyncpg_[0-9a-f-]{36}__", n)
        assert not n.startswith("__asyncpg_stmt_")


def test_caches_de_statements_desactivadas():
    assert _CONNECT_ARGS["statement_cache_size"] == 0
    assert _CONNECT_ARGS["prepared_statement_cache_size"] == 0
