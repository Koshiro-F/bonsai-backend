#!/usr/bin/env python3
"""
既存の農薬推奨データをマスタテーブルに移行するスクリプト
"""

import sqlite3
import os
from datetime import datetime

def get_db_connection():
    """データベース接続を取得"""
    db_path = os.path.join('instance', 'bonsai_users.db')
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_master_data():
    """マスタデータの移行処理"""
    
    # 農薬効果データ（農薬と対象害虫・病気の関係）
    pesticide_effectiveness_data = [
        # オルトラン
        ('オルトラン', 'アブラムシ', 5),
        ('オルトラン', 'アザミウマ', 4),
        ('オルトラン', 'カイガラムシ', 3),
        
        # スミチオン
        ('スミチオン', 'アブラムシ', 5),
        ('スミチオン', 'ハダニ', 4),
        ('スミチオン', 'アザミウマ', 5),
        
        # マラソン
        ('マラソン', 'アブラムシ', 4),
        ('マラソン', 'ハダニ', 3),
        ('マラソン', 'カイガラムシ', 4),
        
        # ベニカ
        ('ベニカ', 'アブラムシ', 5),
        ('ベニカ', 'アザミウマ', 4),
        ('ベニカ', 'ハダニ', 3),
        
        # カダン
        ('カダン', 'アブラムシ', 4),
        ('カダン', 'カイガラムシ', 5),
        ('カダン', 'アザミウマ', 3),
        
        # トップジンM
        ('トップジンM', 'うどんこ病', 5),
        ('トップジンM', '黒星病', 4),
        ('トップジンM', '炭疽病', 4),
        
        # ダコニール
        ('ダコニール', '黒星病', 5),
        ('ダコニール', '炭疽病', 5),
        ('ダコニール', 'すす病', 3),
        
        # 石灰硫黄合剤
        ('石灰硫黄合剤', 'うどんこ病', 4),
        ('石灰硫黄合剤', 'すす病', 5),
        ('石灰硫黄合剤', 'カイガラムシ', 3),
    ]
    
    # 樹種別害虫・病気データ
    species_pest_disease_data = [
        # 黒松 (ID: 1)
        (1, 'アブラムシ', 4, '春'),
        (1, 'ハダニ', 3, '夏'),
        (1, 'カイガラムシ', 5, '通年'),
        (1, 'うどんこ病', 2, '春'),
        (1, '黒星病', 3, '梅雨'),
        
        # 五葉松 (ID: 2)
        (2, 'アブラムシ', 4, '春'),
        (2, 'ハダニ', 4, '夏'),
        (2, 'カイガラムシ', 3, '通年'),
        (2, '黒星病', 4, '梅雨'),
        
        # 真柏 (ID: 3)
        (3, 'アブラムシ', 5, '通年'),
        (3, 'ハダニ', 3, '夏'),
        (3, 'カイガラムシ', 4, '通年'),
        (3, 'うどんこ病', 3, '梅雨'),
        
        # 杜松 (ID: 4)
        (4, 'アブラムシ', 5, '通年'),
        (4, 'ハダニ', 3, '夏'),
        (4, 'カイガラムシ', 4, '通年'),
        (4, 'うどんこ病', 3, '梅雨'),
        
        # 赤松 (ID: 5)
        (5, 'アブラムシ', 4, '春'),
        (5, 'ハダニ', 3, '夏'),
        (5, 'カイガラムシ', 5, '通年'),
        (5, '黒星病', 3, '梅雨'),
        
        # 信州梅 (ID: 6)
        (6, 'アブラムシ', 5, '通年'),
        (6, 'アザミウマ', 4, '春'),
        (6, 'うどんこ病', 4, '梅雨'),
        (6, '黒星病', 3, '梅雨'),
        
        # 小葉性ケヤキ (ID: 7)
        (7, 'アブラムシ', 5, '通年'),
        (7, 'ハダニ', 3, '夏'),
        (7, 'うどんこ病', 3, '梅雨'),
        
        # カエデ (ID: 8)
        (8, 'アブラムシ', 5, '通年'),
        (8, 'ハダニ', 3, '夏'),
        (8, 'うどんこ病', 3, '梅雨'),
        
        # シナ百日紅 (ID: 9)
        (9, 'アブラムシ', 5, '通年'),
        (9, 'アザミウマ', 4, '夏'),
        (9, 'うどんこ病', 4, '梅雨'),
        
        # イロハモミジ (ID: 10)
        (10, 'アブラムシ', 5, '通年'),
        (10, 'ハダニ', 3, '夏'),
        (10, 'うどんこ病', 3, '梅雨'),
        
        # 長寿梅 (ID: 11)
        (11, 'アブラムシ', 5, '通年'),
        (11, 'アザミウマ', 4, '春'),
        (11, 'うどんこ病', 4, '梅雨'),
    ]
    
    # 樹種別NG薬剤データ（例：特定の樹種に対する注意が必要な薬剤）
    species_prohibited_pesticides_data = [
        # 梅系は石灰硫黄合剤に注意（銅イオン系薬剤）
        (6, '石灰硫黄合剤', 'warning', '花期前後の使用は避ける'),
        (11, '石灰硫黄合剤', 'warning', '花期前後の使用は避ける'),
        
        # 針葉樹系は一部薬剤で薬害のリスク
        (1, 'ダコニール', 'warning', '高温期の使用は薬害リスクあり'),
        (2, 'ダコニール', 'warning', '高温期の使用は薬害リスクあり'),
        (5, 'ダコニール', 'warning', '高温期の使用は薬害リスクあり'),
    ]
    
    conn = get_db_connection()
    
    try:
        # 農薬効果データの投入
        print("農薬効果データを投入中...")
        for pesticide_name, pest_disease_name, effectiveness in pesticide_effectiveness_data:
            # 農薬IDを取得
            pesticide_row = conn.execute(
                'SELECT id FROM pesticide_master WHERE name = ?', 
                (pesticide_name,)
            ).fetchone()
            
            # 害虫・病気IDを取得
            pest_disease_row = conn.execute(
                'SELECT id FROM pest_disease_master WHERE name = ?', 
                (pest_disease_name,)
            ).fetchone()
            
            if pesticide_row and pest_disease_row:
                conn.execute('''
                    INSERT OR REPLACE INTO pesticide_effectiveness 
                    (pesticide_id, pest_disease_id, effectiveness_level)
                    VALUES (?, ?, ?)
                ''', (pesticide_row['id'], pest_disease_row['id'], effectiveness))
        
        # 樹種別害虫・病気データの投入
        print("樹種別害虫・病気データを投入中...")
        for species_id, pest_disease_name, probability, season in species_pest_disease_data:
            # 害虫・病気IDを取得
            pest_disease_row = conn.execute(
                'SELECT id FROM pest_disease_master WHERE name = ?', 
                (pest_disease_name,)
            ).fetchone()
            
            if pest_disease_row:
                conn.execute('''
                    INSERT OR REPLACE INTO species_pest_disease 
                    (species_id, pest_disease_id, occurrence_probability, season)
                    VALUES (?, ?, ?, ?)
                ''', (species_id, pest_disease_row['id'], probability, season))
        
        # 樹種別NG薬剤データの投入
        print("樹種別NG薬剤データを投入中...")
        for species_id, pesticide_name, severity, reason in species_prohibited_pesticides_data:
            # 農薬IDを取得
            pesticide_row = conn.execute(
                'SELECT id FROM pesticide_master WHERE name = ?', 
                (pesticide_name,)
            ).fetchone()
            
            if pesticide_row:
                conn.execute('''
                    INSERT OR REPLACE INTO species_prohibited_pesticides 
                    (species_id, pesticide_id, severity, reason)
                    VALUES (?, ?, ?, ?)
                ''', (species_id, pesticide_row['id'], severity, reason))
        
        conn.commit()
        print("マスタデータの移行が完了しました。")
        
    except Exception as e:
        conn.rollback()
        print(f"エラーが発生しました: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_master_data() 