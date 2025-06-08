#!/usr/bin/env python3
"""
マスタデータの確認用スクリプト
"""

from app import create_app
from app.db import get_db

app = create_app()

with app.app_context():
    db = get_db()
    
    # マスタデータの確認
    print('=== 農薬マスタ ===')
    pesticides = db.execute('SELECT * FROM pesticide_master').fetchall()
    for p in pesticides:
        print(f'{p["name"]} ({p["type"]}): {p["interval_days"]}日間隔')
    
    print('\n=== 害虫・病気マスタ ===')
    pests = db.execute('SELECT * FROM pest_disease_master').fetchall()
    for p in pests:
        print(f'{p["name"]} ({p["type"]}): {p["season"]}')
    
    print('\n=== 樹種別リスク（黒松:ID=1）===')
    risks = db.execute('''
        SELECT spd.*, pdm.name as pest_name 
        FROM species_pest_disease spd 
        JOIN pest_disease_master pdm ON spd.pest_disease_id = pdm.id 
        WHERE spd.species_id = 1
        ORDER BY spd.occurrence_probability DESC
    ''').fetchall()
    for r in risks:
        print(f'{r["pest_name"]}: リスク{r["occurrence_probability"]} ({r["season"]})')
    
    print('\n=== 農薬効果（オルトラン）===')
    effectiveness = db.execute('''
        SELECT pe.*, pm.name as pesticide_name, pdm.name as target_name
        FROM pesticide_effectiveness pe
        JOIN pesticide_master pm ON pe.pesticide_id = pm.id
        JOIN pest_disease_master pdm ON pe.pest_disease_id = pdm.id
        WHERE pm.name = 'オルトラン'
        ORDER BY pe.effectiveness_level DESC
    ''').fetchall()
    for e in effectiveness:
        print(f'{e["target_name"]}: 効果レベル{e["effectiveness_level"]}')
    
    print('\n=== 樹種別NG薬剤 ===')
    prohibited = db.execute('''
        SELECT spp.*, pm.name as pesticide_name
        FROM species_prohibited_pesticides spp
        JOIN pesticide_master pm ON spp.pesticide_id = pm.id
        ORDER BY spp.species_id
    ''').fetchall()
    for p in prohibited:
        print(f'樹種ID{p["species_id"]}: {p["pesticide_name"]} ({p["severity"]}) - {p["reason"]}')
    
    print('\nマスタデータ確認完了') 