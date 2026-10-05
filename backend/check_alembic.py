import sqlite3
conn = sqlite3.connect('test_alembic.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('Tables created by Alembic migration:')
for t in tables:
    print(' -', t[0])
conn.close()
