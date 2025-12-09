#!/usr/bin/env python3
"""Check database tables and availability"""
import sqlite3

conn = sqlite3.connect('medhub_dev.db')
c = conn.cursor()

# List tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print("Tables:", [t[0] for t in tables])

# Check availability table
for t in tables:
    if 'avail' in t[0].lower():
        print(f"\nChecking {t[0]}:")
        c.execute(f"SELECT * FROM {t[0]} LIMIT 5")
        rows = c.fetchall()
        for r in rows:
            print(r)

conn.close()
