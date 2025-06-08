import sqlite3
import bcrypt
import getpass
import os

def create_admin_user():
    print("=" * 50)
    print("管理者アカウント作成ユーティリティ")
    print("=" * 50)
    print("\n既存のユーザーを管理者に昇格させることも、新しい管理者を作成することもできます。")
    
    # データベースファイルのパス
    db_file = 'bonsai_users.db'
    
    # データベースが存在しない場合は作成
    if not os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS bonsai (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        species TEXT,
        notes TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pesticide_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bonsai_id INTEGER,
        pesticide_name TEXT,
        usage_date DATE,
        dosage TEXT,
        notes TEXT,
        FOREIGN KEY(bonsai_id) REFERENCES bonsai(id)
        )''')
        conn.commit()
        conn.close()
        print("データベースを新規作成しました。")
    
    # データベースに接続
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 既存の管理者を確認
    cursor.execute("SELECT id, username FROM users WHERE role = 'admin'")
    admin_users = cursor.fetchall()
    
    if admin_users:
        print("\n現在の管理者アカウント:")
        for admin in admin_users:
            print(f" - {admin['username']} (ID: {admin['id']})")
    else:
        print("\n現在、管理者アカウントは登録されていません。")
    
    # アクション選択
    print("\n操作を選択してください:")
    print("1: 新しい管理者アカウントを作成")
    print("2: 既存のユーザーを管理者に昇格")
    print("0: 終了")
    
    choice = input("選択 (0-2): ")
    
    if choice == "1":
        # 新しい管理者アカウントを作成
        username = input("\nユーザー名 (3文字以上): ")
        if len(username) < 3:
            print("エラー: ユーザー名は3文字以上必要です。")
            return
        
        password = getpass.getpass("パスワード (6文字以上): ")
        if len(password) < 6:
            print("エラー: パスワードは6文字以上必要です。")
            return
        
        password_confirm = getpass.getpass("パスワード (確認): ")
        if password != password_confirm:
            print("エラー: パスワードが一致しません。")
            return
        
        # パスワードハッシュ化
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        try:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                         (username, hashed_pw, 'admin'))
            conn.commit()
            print(f"\n管理者アカウント '{username}' を作成しました。")
        except sqlite3.IntegrityError:
            print(f"\nエラー: ユーザー名 '{username}' は既に使用されています。")
            
    elif choice == "2":
        # 既存ユーザーを昇格
        cursor.execute("SELECT id, username, role FROM users WHERE role != 'admin' ORDER BY username")
        regular_users = cursor.fetchall()
        
        if not regular_users:
            print("\nエラー: 昇格できる一般ユーザーがいません。")
            return
        
        print("\n昇格可能なユーザー:")
        for i, user in enumerate(regular_users, 1):
            print(f"{i}: {user['username']} (現在の権限: {user['role']})")
        
        try:
            user_idx = int(input("\n昇格するユーザーの番号を選択: ")) - 1
            if user_idx < 0 or user_idx >= len(regular_users):
                print("エラー: 無効な選択です。")
                return
                
            user_id = regular_users[user_idx]['id']
            username = regular_users[user_idx]['username']
            
            cursor.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            conn.commit()
            print(f"\nユーザー '{username}' を管理者に昇格しました。")
            
        except ValueError:
            print("エラー: 数字を入力してください。")
    
    elif choice == "0":
        print("\n終了します。")
    else:
        print("\nエラー: 無効な選択です。")
    
    # 最終的なユーザー一覧を表示
    cursor.execute("SELECT id, username, role FROM users ORDER BY id")
    all_users = cursor.fetchall()
    
    if all_users:
        print("\n現在のユーザー一覧:")
        print("-" * 40)
        print(f"{'ID':<5} {'ユーザー名':<15} {'権限':<10}")
        print("-" * 40)
        for user in all_users:
            print(f"{user['id']:<5} {user['username']:<15} {user['role']:<10}")
        print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    create_admin_user() 