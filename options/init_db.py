import sqlite3
import os
from flask import Flask

app = Flask(__name__, instance_relative_config=True)
app.config['DATABASE'] = 'bonsai_users.db'

# 適切なinstanceディレクトリのパスを設定
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
instance_dir = os.path.join(base_dir, 'instance')
os.makedirs(instance_dir, exist_ok=True)

# データベースパスを構築
db_path = os.path.join(instance_dir, app.config['DATABASE'])
print(f'データベースパス: {db_path}')

# 直接SQLite接続でデータベースを初期化
def init_database():
    db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    
    # 既存のテーブルを作成
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS bonsai (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            species TEXT,
            species_id INTEGER,
            notes TEXT
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS pesticide_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonsai_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            pesticide_name TEXT NOT NULL,
            amount TEXT,
            dosage TEXT,
            notes TEXT,
            water_amount TEXT,
            dilution_ratio TEXT,
            actual_usage_amount TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS bonsai_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonsai_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS work_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonsai_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            work_type TEXT NOT NULL CHECK (work_type IN ('剪定', '植え替え', '針金掛け', '針金外し', '水やり', '肥料', '植え替え準備', 'その他')),
            description TEXT,
            notes TEXT,
            duration INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bonsai_id) REFERENCES bonsai (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 新しいマスタテーブルを作成
    db.execute('''
        CREATE TABLE IF NOT EXISTS species_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            scientific_name TEXT,
            category TEXT CHECK (category IN ('針葉樹', '広葉樹', '花木', '果樹', 'その他')),
            description TEXT,
            care_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS pesticide_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK (type IN ('insecticide', 'fungicide')),
            interval_days INTEGER NOT NULL,
            active_ingredient TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS pest_disease_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('pest', 'disease')),
            description TEXT,
            season TEXT CHECK (season IN ('春', '夏', '秋', '冬', '通年', '梅雨')),
            start_month INTEGER CHECK (start_month BETWEEN 1 AND 12),
            end_month INTEGER CHECK (end_month BETWEEN 1 AND 12),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS pesticide_effectiveness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pesticide_id INTEGER NOT NULL,
            pest_disease_id INTEGER NOT NULL,
            effectiveness_level INTEGER NOT NULL CHECK (effectiveness_level BETWEEN 1 AND 5),
            notes TEXT,
            FOREIGN KEY (pesticide_id) REFERENCES pesticide_master (id),
            FOREIGN KEY (pest_disease_id) REFERENCES pest_disease_master (id)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS species_pest_disease (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            pest_disease_id INTEGER NOT NULL,
            occurrence_probability INTEGER NOT NULL CHECK (occurrence_probability BETWEEN 1 AND 5),
            season TEXT CHECK (season IN ('春', '夏', '秋', '冬', '通年', '梅雨')),
            start_month INTEGER CHECK (start_month BETWEEN 1 AND 12),
            end_month INTEGER CHECK (end_month BETWEEN 1 AND 12),
            notes TEXT,
            FOREIGN KEY (species_id) REFERENCES species_master (id),
            FOREIGN KEY (pest_disease_id) REFERENCES pest_disease_master (id)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS species_prohibited_pesticides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            pesticide_id INTEGER NOT NULL,
            reason TEXT,
            severity TEXT CHECK (severity IN ('warning', 'prohibited')),
            notes TEXT,
            FOREIGN KEY (species_id) REFERENCES species_master (id),
            FOREIGN KEY (pesticide_id) REFERENCES pesticide_master (id)
        )
    ''')
    
    db.commit()
    db.close()

# データベースを初期化
init_database()
print('データベースが更新されました')