from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash

# db.execute('''
#         CREATE TABLE IF NOT EXISTS bonsai_images (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             bonsai_id INTEGER NOT NULL,
#             user_id INTEGER NOT NULL,
#             filename TEXT NOT NULL,
#             original_filename TEXT NOT NULL,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#     ''')

def create_bonsai_images(bonsai_id, user_id, filename, original_filename):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 盆栽画像が既に存在するか確認
        existing_bonsai_image = db.execute(
            'SELECT * FROM bonsai_images WHERE bonsai_id = ? AND user_id = ? AND filename = ? AND original_filename = ?', (bonsai_id, user_id, filename, original_filename)
        ).fetchone()
        
        if existing_bonsai_image:
            print(f"盆栽画像 '{filename}' は既に存在します。")
            return
        
        # 新しいユーザーを作成
        db.execute(
            'INSERT INTO bonsai_images (bonsai_id, user_id, filename, original_filename) VALUES (?, ?, ?, ?)',
            (bonsai_id, user_id, filename, original_filename)
        )
        db.commit()
        
        print(f"盆栽画像 '{filename}' が作成されました。")

if __name__ == '__main__':
    bonsai_id = 1
    user_id = 1
    filename = '96c3e658876848e093ab23cf01be2b76.jpeg'
    original_filename = '96c3e658876848e093ab23cf01be2b76.jpeg'
    create_bonsai_images(bonsai_id, user_id, filename, original_filename) 