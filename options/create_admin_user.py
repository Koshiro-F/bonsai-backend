#!/usr/bin/env python3
"""
管理者ユーザーを作成するスクリプト
"""

from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db = get_db()
    
    # 既存の管理者をチェック
    existing_admin = db.execute('SELECT * FROM users WHERE role = "admin"').fetchone()
    
    if existing_admin:
        print(f'管理者ユーザーが既に存在します: {existing_admin["username"]}')
    else:
        # 管理者ユーザーを作成
        admin_username = "admin"
        admin_password = "admin123"  # 本番環境では強力なパスワードを使用
        
        db.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', (admin_username, generate_password_hash(admin_password), "admin"))
        db.commit()
        
        print(f'管理者ユーザーを作成しました: {admin_username}')
        print(f'パスワード: {admin_password}')
    
    # 通常ユーザーのロールを設定（既存ユーザー用）
    users_without_role = db.execute('SELECT * FROM users WHERE role IS NULL OR role = ""').fetchall()
    
    for user in users_without_role:
        db.execute('UPDATE users SET role = "user" WHERE id = ?', (user['id'],))
    
    if users_without_role:
        db.commit()
        print(f'{len(users_without_role)}人の既存ユーザーに通常ユーザーロールを設定しました')
    
    print('管理者ユーザー設定完了') 