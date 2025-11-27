#!/usr/bin/env python
"""manage_admin.py
Simple CLI to create/promote an admin user in database.db
Usage:
  python manage_admin.py create --username admin --password secret
  python manage_admin.py promote --username alice
  python manage_admin.py demote --username bob
"""
import argparse
import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_admin(username, password, email=None):
    if email is None:
        email = f"{username}@local"
    hashed = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE username = ?', (username,))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE users SET password = ?, is_admin = 1 WHERE id = ?', (hashed, row['id']))
        print(f"Updated existing user '{username}' and gave admin rights.")
    else:
        cur.execute('INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)', (username, email, hashed, 1))
        print(f"Created admin user '{username}'.")
    conn.commit()
    conn.close()


def promote(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = 1 WHERE username = ?', (username,))
    if cur.rowcount:
        print(f"Promoted '{username}' to admin.")
    else:
        print(f"User '{username}' not found.")
    conn.commit()
    conn.close()


def demote(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = 0 WHERE username = ?', (username,))
    if cur.rowcount:
        print(f"Demoted '{username}'.")
    else:
        print(f"User '{username}' not found.")
    conn.commit()
    conn.close()


def delete(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE username = ?', (username,))
    if cur.rowcount:
        print(f"Deleted user '{username}'.")
    else:
        print(f"User '{username}' not found.")
    conn.commit()
    conn.close()


def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, username, email, is_admin, created_at FROM users ORDER BY id')
    rows = cur.fetchall()
    print('id | username | email | is_admin | created_at')
    for r in rows:
        print(f"{r['id']} | {r['username']} | {r['email']} | {r['is_admin']} | {r['created_at']}")
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')

    p_create = sub.add_parser('create')
    p_create.add_argument('--username', required=True)
    p_create.add_argument('--password', required=True)
    p_create.add_argument('--email', required=False)

    p_promote = sub.add_parser('promote')
    p_promote.add_argument('--username', required=True)

    p_demote = sub.add_parser('demote')
    p_demote.add_argument('--username', required=True)

    p_delete = sub.add_parser('delete')
    p_delete.add_argument('--username', required=True)

    p_list = sub.add_parser('list')

    args = parser.parse_args()

    if args.cmd == 'create':
        create_admin(args.username, args.password, args.email)
    elif args.cmd == 'promote':
        promote(args.username)
    elif args.cmd == 'demote':
        demote(args.username)
    elif args.cmd == 'list':
        list_users()
    elif args.cmd == 'delete':
        delete(args.username)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
