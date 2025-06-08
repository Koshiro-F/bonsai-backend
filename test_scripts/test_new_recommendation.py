#!/usr/bin/env python3
"""
新しい推奨システムのテスト用スクリプト
"""

from app import create_app
from app.db import get_db
from app.routes.recommend import get_intelligent_recommendation, get_species_pest_disease_risks

app = create_app()

# テスト用の盆栽データ
test_bonsai = {
    'id': 999,
    'species_id': 1,  # 黒松
    'name': 'テスト黒松'
}

with app.app_context():
    db = get_db()
    
    print('=== 新しい推奨システムのテスト ===')
    print(f'テスト対象: {test_bonsai["name"]} (樹種ID: {test_bonsai["species_id"]})')
    
    # 樹種のリスク分析
    print('\n--- 樹種リスク分析 ---')
    risks = get_species_pest_disease_risks(db, test_bonsai['species_id'])
    for risk in risks:
        print(f'{risk["pest_disease_name"]}: リスク{risk["occurrence_probability"]} ({risk["season"]}, {risk["pest_disease_type"]})')
    
    # 初回推奨（履歴なし）
    print('\n--- 初回推奨 ---')
    recommendation1 = get_intelligent_recommendation(db, test_bonsai, None)
    print(f'推奨農薬: {recommendation1["recommendation"]}')
    print(f'理由: {recommendation1["reason"]}')
    print(f'対象害虫・病気: {recommendation1.get("target_pests", [])}')
    print(f'信頼度: {recommendation1["confidence"]}')
    
    # 模擬的な使用履歴を作成して再推奨
    print('\n--- 履歴ありの推奨 ---')
    mock_latest_log = {
        'date': '2024-12-01',
        'pesticide_name': 'オルトラン'
    }
    
    recommendation2 = get_intelligent_recommendation(db, test_bonsai, mock_latest_log)
    print(f'推奨農薬: {recommendation2["recommendation"]}')
    print(f'理由: {recommendation2["reason"]}')
    if 'target_pests' in recommendation2:
        print(f'対象害虫・病気: {recommendation2["target_pests"]}')
    print(f'信頼度: {recommendation2["confidence"]}')
    
    # 樹種別推奨農薬リスト
    print('\n--- 樹種別推奨農薬リスト ---')
    target_pest_disease_ids = [r['pest_disease_id'] for r in risks]
    if target_pest_disease_ids:
        placeholders = ','.join(['?'] * len(target_pest_disease_ids))
        pesticides = db.execute(f'''
            SELECT pe.*, pm.name as pesticide_name, pm.type as pesticide_type, 
                   pm.interval_days, AVG(pe.effectiveness_level) as avg_effectiveness
            FROM pesticide_effectiveness pe
            JOIN pesticide_master pm ON pe.pesticide_id = pm.id
            WHERE pe.pest_disease_id IN ({placeholders})
            GROUP BY pe.pesticide_id
            ORDER BY avg_effectiveness DESC
        ''', target_pest_disease_ids).fetchall()
        
        for p in pesticides:
            print(f'{p["pesticide_name"]} ({p["pesticide_type"]}): 効果レベル{p["avg_effectiveness"]:.1f}')
    
    print('\nテスト完了') 