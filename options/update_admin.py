from app import create_app
from app.db import get_db

app = create_app()
with app.app_context():
    db = get_db()
    
    try:
        # adminユーザーを検索
        admin = db.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()
        
        if admin:
            # 管理者権限を付与
            db.execute("UPDATE users SET role = ? WHERE username = ?", ("admin", "admin"))
            db.commit()
            print("adminユーザーに管理者権限を付与しました")
        else:
            print("adminユーザーが見つかりません")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        
    # 確認
    users = db.execute("SELECT id, username, role FROM users").fetchall()
    print("\n現在のユーザー一覧:")
    for user in users:
        print(f"ID: {user['id']}, ユーザー名: {user['username']}, 権限: {user['role']}") 