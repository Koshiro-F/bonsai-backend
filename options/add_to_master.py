from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash

def add_to_pesticide_master(name, type, interval_days, active_ingredient, description):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 農薬が既に存在するか確認
        existing_pesticide = db.execute(
            'SELECT * FROM pesticide_master WHERE name = ?', (name,)
        ).fetchone()
        
        if existing_pesticide:
            print(f"農薬 '{name}' は既に存在します。")
            return
        
        # 新しい農薬を作成
        db.execute(
            'INSERT INTO pesticide_master (name, type, interval_days, active_ingredient, description) VALUES (?, ?, ?, ?, ?)',
            (name, type, interval_days, active_ingredient, description)
        )
        db.commit()
        
        print(f"農薬 '{name}' が追加されました。")

def add_to_pest_disease_master(name, type, description, season):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 病害が既に存在するか確認
        existing_pest_disease = db.execute(
            'SELECT * FROM pest_disease_master WHERE name = ?', (name,)
        ).fetchone()
        
        if existing_pest_disease:
            print(f"病害 '{name}' は既に存在します。")
            return

        # 新しい病害を作成
        db.execute(
            'INSERT INTO pest_disease_master (name, type, description, season) VALUES (?, ?, ?, ?)',
            (name, type, description, season)
        )
        db.commit()
        
        print(f"病害 '{name}' が追加されました。")

def add_to_pesticide_effectiveness_master(pesticide_id, pest_disease_id, effectiveness_level, notes):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 効果が既に存在するか確認
        existing_pesticide_effectiveness = db.execute(
            'SELECT * FROM pesticide_effectiveness_master WHERE pesticide_id = ? AND pest_disease_id = ?',
            (pesticide_id, pest_disease_id)
        ).fetchone()
        
        if existing_pesticide_effectiveness:
            print(f"農薬 '{pesticide_id}' と病害 '{pest_disease_id}' の効果は既に存在します。")
            return
        
        # 新しい効果を作成
        db.execute(
            'INSERT INTO pesticide_effectiveness_master (pesticide_id, pest_disease_id, effectiveness_level, notes) VALUES (?, ?, ?, ?)',
            (pesticide_id, pest_disease_id, effectiveness_level, notes)
        )
        db.commit()

        print(f"農薬 '{pesticide_id}' と病害 '{pest_disease_id}' の効果が追加されました。")

def add_to_species_pest_disease_master(species_id, pest_disease_id, occurrence_probability, season, notes):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 病害が既に存在するか確認
        existing_species_pest_disease = db.execute(
            'SELECT * FROM species_pest_disease_master WHERE species_id = ? AND pest_disease_id = ?',
            (species_id, pest_disease_id)
        ).fetchone()
        
        if existing_species_pest_disease:
            print(f"樹種 '{species_id}' と病害 '{pest_disease_id}' の関連は既に存在します。")
            return

        # 新しい関連を作成
        db.execute(
            'INSERT INTO species_pest_disease_master (species_id, pest_disease_id, occurrence_probability, season, notes) VALUES (?, ?, ?, ?, ?)',
            (species_id, pest_disease_id, occurrence_probability, season, notes)
        )
        db.commit()

        print(f"樹種 '{species_id}' と病害 '{pest_disease_id}' の関連が追加されました。")

def add_to_species_prohibited_pesticides_master(species_id, pesticide_id, reason, severity, notes):
    app = create_app()
    with app.app_context():
        db = get_db()
        
        # 禁止農薬が既に存在するか確認
        existing_species_prohibited_pesticide = db.execute(
            'SELECT * FROM species_prohibited_pesticides_master WHERE species_id = ? AND pesticide_id = ?',
            (species_id, pesticide_id)
        ).fetchone()

        if existing_species_prohibited_pesticide:
            print(f"樹種 '{species_id}' と農薬 '{pesticide_id}' の禁止は既に存在します。")
            return

        # 新しい禁止を作成
        db.execute(
            'INSERT INTO species_prohibited_pesticides_master (species_id, pesticide_id, reason, severity, notes) VALUES (?, ?, ?, ?, ?)',
            (species_id, pesticide_id, reason, severity, notes)
        )
        db.commit()

        print(f"樹種 '{species_id}' と農薬 '{pesticide_id}' の禁止が追加されました。")


if __name__ == '__main__':
    mode = input("モードを選択してください: 1. 農薬追加 2. 病害追加 3. 効果追加 4. 樹種病害関連追加 5. 樹種禁止農薬追加")
    if mode == "1":
        name = input("農薬名を入力してください: ")
        type = input("農薬タイプを入力してください: ")
        interval_days = input("散布間隔を入力してください: ")
        active_ingredient = input("有効成分を入力してください: ")
        description = input("説明を入力してください: ")
        add_to_pesticide_master(name, type, interval_days, active_ingredient, description) 
    elif mode == "2":
        name = input("病害名を入力してください: ")
        type = input("病害タイプを入力してください: ")
        description = input("説明を入力してください: ")
        season = input("季節を入力してください: ")
        add_to_pest_disease_master(name, type, description, season) 
    elif mode == "3":
        pesticide_id = input("農薬IDを入力してください: ")
        pest_disease_id = input("病害IDを入力してください: ")
        effectiveness_level = input("効果レベルを入力してください: ")
        notes = input("備考を入力してください: ")
        add_to_pesticide_effectiveness_master(pesticide_id, pest_disease_id, effectiveness_level, notes) 
    elif mode == "4":
        species_id = input("樹種IDを入力してください: ")
        pest_disease_id = input("病害IDを入力してください: ")
        occurrence_probability = input("発生確率を入力してください: ")
        season = input("季節を入力してください: ")
        notes = input("備考を入力してください: ")
        add_to_species_pest_disease_master(species_id, pest_disease_id, occurrence_probability, season, notes) 
    elif mode == "5":
        species_id = input("樹種IDを入力してください: ")
        pesticide_id = input("農薬IDを入力してください: ")
        reason = input("理由を入力してください: ")
        severity = input("重症度を入力してください: ")
        notes = input("備考を入力してください: ")
        add_to_species_prohibited_pesticides_master(species_id, pesticide_id, reason, severity, notes) 