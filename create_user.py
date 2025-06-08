from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash

def create_user(username, password, role):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # ユーザーが既に存在するか確認
        existing_user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if existing_user:
            print(f"ユーザー '{username}' は既に存在します。")
            return
        
        # 新しいユーザーを作成
        db.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), role)
        )
        db.commit()
        
        print(f"ユーザー '{username}' が作成されました。")

if __name__ == '__main__':
    username = 'admin'
    password = 'password'
    role = 'admin'
    create_user(username, password, role) 