"""Small compatibility layer for this ledger's fixed SQL statements only."""
class Connection:
    def __init__(self, url):
        import psycopg
        # A failed remote connection must never silently create an empty local ledger.
        self.db = psycopg.connect(url, connect_timeout=10, sslmode='verify-full')

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.db.commit()
            else:
                self.db.rollback()
        finally:
            self.db.close()

    def executescript(self, script):
        script = script.replace('id INTEGER PRIMARY KEY', 'id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY')
        for statement in script.split(';'):
            if statement.strip():
                self.db.execute(statement)

    def execute(self, sql, params=None):
        if sql == 'BEGIN IMMEDIATE':
            # A transaction-scoped lock serializes the single owner's ledger writes.
            return self.db.execute('SELECT pg_advisory_xact_lock(724191801)')
        sql = sql.replace('?', '%s')
        if sql.startswith('INSERT OR IGNORE INTO'):
            sql = sql.replace('INSERT OR IGNORE INTO', 'INSERT INTO') + ' ON CONFLICT DO NOTHING'
        return self.db.execute(sql, params)
