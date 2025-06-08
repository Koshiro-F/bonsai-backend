from app import create_app
from app.db import get_db
import sqlite3

app = create_app()

def update_db():
    with app.app_context():
        db = get_db()
        
        # bonsaiテーブルの構造を確認
        try:
            columns = db.execute("PRAGMA table_info(bonsai)").fetchall()
            column_names = [column['name'] for column in columns]
            
            # species_idカラムがまだなければ追加
            if 'species_id' not in column_names:
                db.execute("ALTER TABLE bonsai ADD COLUMN species_id INTEGER")
                print("盆栽テーブルにspecies_idカラムを追加しました。")
            else:
                print("species_idカラムはすでに存在します。")
            
            db.commit()
            print("データベース更新が完了しました。")
        except sqlite3.Error as e:
            print(f"エラーが発生しました: {e}")
            db.rollback()

if __name__ == '__main__':
    update_db() 