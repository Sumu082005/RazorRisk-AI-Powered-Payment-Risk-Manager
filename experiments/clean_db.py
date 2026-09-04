import sqlite3

conn = sqlite3.connect('storage/audit.db')
cursor = conn.cursor()

cursor.execute('DELETE FROM audit_logs')
cursor.execute('DELETE FROM webhook_events')
conn.commit()

cursor.execute('SELECT COUNT(*) FROM audit_logs')
print('audit_logs count:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM webhook_events')
print('webhook_events count:', cursor.fetchone()[0])

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables in DB:', [r[0] for r in cursor.fetchall()])

cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
print('Indexes in DB:', [r[0] for r in cursor.fetchall()])

conn.close()
