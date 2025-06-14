import sqlite3
import os
import click
from flask import current_app, g
from flask.cli import with_appcontext

def get_db(app=None):
    if app is None:
        app = current_app
    
    if 'db' not in g:
        g.db = sqlite3.connect(
            os.path.join(app.instance_path, app.config['DATABASE']),
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
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

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_master_data():
    """マスタデータの初期化（月ベース）"""
    db = get_db()
    
    # 既存データの重複チェック
    existing_pesticides = db.execute('SELECT COUNT(*) as count FROM pesticide_master').fetchone()
    if existing_pesticides['count'] > 0:
        click.echo('Master data already exists. Skipping initialization.')
        return
    
    # 樹種マスタデータの投入
    species = [
        ('黒松', 'Pinus thunbergii', '針葉樹', '耐寒性に優れた代表的な盆栽樹種', '日当たりと風通しを好む'),
        ('赤松', 'Pinus densiflora', '針葉樹', '優美な樹形が特徴的な松', '乾燥気味に管理'),
        ('五葉松', 'Pinus parviflora', '針葉樹', '短い五本針が美しい高級樹種', '水はけを良くする'),
        ('真柏', 'Juniperus chinensis', '針葉樹', '造形しやすく初心者にも人気', '強健で育てやすい'),
        ('欅', 'Zelkova serrata', '広葉樹', 'ほうき立ちの美しい樹形', '水を好む'),
        ('楓', 'Acer palmatum', '広葉樹', '紅葉の美しさで人気', '半日陰を好む'),
        ('梅', 'Prunus mume', '花木', '早春の花が美しい', '花後の剪定が重要'),
        ('桜', 'Prunus × yedoensis', '花木', '春の代表的な花木', '病気に注意'),
        ('カリン', 'Chaenomeles sinensis', '果樹', '実成りが楽しめる', '日当たりを好む'),
        ('金柑', 'Citrus japonica', '果樹', '小さな果実が可愛い', '寒さに注意'),
        ('ガジュマル', 'Ficus microcarpa', 'その他', '気根が特徴的な観葉植物', '温暖な環境を好む')
    ]
    
    for species_data in species:
        db.execute('''
            INSERT INTO species_master (name, scientific_name, category, description, care_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', species_data)
    
    # 農薬マスタデータの投入
    pesticides = [
        ('オルトラン', 'insecticide', 14, 'アセフェート', '汎用殺虫剤'),
        ('スミチオン', 'insecticide', 10, 'フェニトロチオン', '速効性殺虫剤'),
        ('マラソン', 'insecticide', 12, 'マラチオン', '広範囲殺虫剤'),
        ('ベニカ', 'insecticide', 7, 'クロチアニジン', '浸透移行性殺虫剤'),
        ('カダン', 'insecticide', 15, 'イミダクロプリド', '持続性殺虫剤'),
        ('トップジンM', 'fungicide', 21, 'チオファネートメチル', '系統殺菌剤'),
        ('ダコニール', 'fungicide', 18, 'クロロタロニル', '保護殺菌剤'),
        ('石灰硫黄合剤', 'fungicide', 30, '多硫化カルシウム', '冬季殺菌剤')
    ]
    
    for pesticide in pesticides:
        db.execute('''
            INSERT INTO pesticide_master (name, type, interval_days, active_ingredient, description)
            VALUES (?, ?, ?, ?, ?)
        ''', pesticide)
    
    # 害虫・病気マスタデータの投入（月ベース）
    pest_diseases = [
        ('アブラムシ', 'pest', 'アブラムシ科の害虫', 4, 10),  # 4月-10月
        ('ハダニ', 'pest', 'ハダニ科の害虫', 6, 9),           # 6月-9月
        ('カイガラムシ', 'pest', 'カイガラムシ科の害虫', 1, 12),  # 通年
        ('アザミウマ', 'pest', 'アザミウマ科の害虫', 3, 6),      # 3月-6月
        ('うどんこ病', 'disease', '糸状菌による病気', 4, 6),     # 4月-6月
        ('黒星病', 'disease', '糸状菌による病気', 5, 7),        # 5月-7月（梅雨）
        ('炭疽病', 'disease', '糸状菌による病気', 6, 8),        # 6月-8月
        ('すす病', 'disease', '糸状菌による病気', 1, 12)        # 通年
    ]
    
    for name, pest_type, description, start_month, end_month in pest_diseases:
        db.execute('''
            INSERT INTO pest_disease_master (name, type, description, start_month, end_month)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, pest_type, description, start_month, end_month))
    
    db.commit()
    click.echo('Master data initialized successfully with monthly ranges.')

@click.command('init-master-data')
@with_appcontext
def init_master_data_command():
    """Initialize master data for pesticide recommendation system."""
    init_master_data()

@click.command('migrate-to-monthly')
@with_appcontext
def migrate_to_monthly_command():
    """Migrate existing seasonal data to monthly ranges."""
    from migrate_to_monthly_risks import migrate_to_monthly_risks
    migrate_to_monthly_risks()
