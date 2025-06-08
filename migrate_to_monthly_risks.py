#!/usr/bin/env python3
"""
害虫・病気リスクを季節ベースから月ベースに変更するマイグレーションスクリプト
"""

import sqlite3
import os
from app import create_app

def migrate_to_monthly_risks():
    """害虫・病気リスクテーブルを季節ベースから月ベースに変更"""
    app = create_app()
    
    with app.app_context():
        db_path = app.config['DATABASE']
        
        if not os.path.exists(db_path):
            print(f"データベースファイル {db_path} が見つかりません")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            print("=== 月ベースリスク管理への移行開始 ===")
            
            # 1. pest_disease_masterテーブルの変更
            print("1. pest_disease_masterテーブルを更新中...")
            
            # 新しいカラムを追加
            cursor.execute("ALTER TABLE pest_disease_master ADD COLUMN start_month INTEGER")
            cursor.execute("ALTER TABLE pest_disease_master ADD COLUMN end_month INTEGER")
            
            # 既存の季節データを月データに変換
            season_to_months = {
                '春': (3, 5),
                '夏': (6, 8), 
                '秋': (9, 11),
                '冬': (12, 2),  # 12月から2月（年をまたぐ）
                '梅雨': (6, 6),
                '通年': (1, 12)
            }
            
            for season, (start_month, end_month) in season_to_months.items():
                cursor.execute("""
                    UPDATE pest_disease_master 
                    SET start_month = ?, end_month = ?
                    WHERE season = ?
                """, (start_month, end_month, season))
            
            print(f"   - pest_disease_master: {cursor.rowcount}件を更新")
            
            # 2. species_pest_diseaseテーブルの変更
            print("2. species_pest_diseaseテーブルを更新中...")
            
            # 新しいカラムを追加
            cursor.execute("ALTER TABLE species_pest_disease ADD COLUMN start_month INTEGER")
            cursor.execute("ALTER TABLE species_pest_disease ADD COLUMN end_month INTEGER")
            
            # 既存の季節データを月データに変換
            for season, (start_month, end_month) in season_to_months.items():
                cursor.execute("""
                    UPDATE species_pest_disease 
                    SET start_month = ?, end_month = ?
                    WHERE season = ?
                """, (start_month, end_month, season))
            
            print(f"   - species_pest_disease: {cursor.rowcount}件を更新")
            
            # 3. 変換結果の確認
            print("3. 変換結果を確認中...")
            cursor.execute("""
                SELECT season, start_month, end_month, COUNT(*) as count
                FROM pest_disease_master 
                GROUP BY season, start_month, end_month
                ORDER BY start_month
            """)
            
            print("   pest_disease_master変換結果:")
            for row in cursor.fetchall():
                season, start_month, end_month, count = row
                print(f"     {season} → {start_month}月-{end_month}月 ({count}件)")
            
            cursor.execute("""
                SELECT season, start_month, end_month, COUNT(*) as count
                FROM species_pest_disease 
                GROUP BY season, start_month, end_month
                ORDER BY start_month
            """)
            
            print("   species_pest_disease変換結果:")
            for row in cursor.fetchall():
                season, start_month, end_month, count = row
                print(f"     {season} → {start_month}月-{end_month}月 ({count}件)")
            
            # 4. 新しいサンプルデータを追加（月ベースでより細かく設定）
            print("4. 月ベース拡張データを追加中...")
            
            # より細かい月設定のサンプルデータ
            extended_monthly_data = [
                # アブラムシは春から秋まで
                ('アブラムシ', 4, 10),
                # ハダニは夏の高温期
                ('ハダニ', 7, 9),
                # カイガラムシは一年中だが特に春と秋
                ('カイガラムシ', 1, 12),
                # うどんこ病は春と秋の湿度が高い時期
                ('うどんこ病', 4, 6),
                ('うどんこ病', 9, 11),
                # 黒星病は梅雨時期中心
                ('黒星病', 5, 7),
            ]
            
            # 害虫・病気IDを取得して追加データを挿入
            cursor.execute("SELECT id, name FROM pest_disease_master")
            pest_disease_map = dict(cursor.fetchall())
            
            # 樹種IDも取得
            cursor.execute("SELECT id, name FROM species_master LIMIT 3")  # 主要樹種のみ
            species_list = cursor.fetchall()
            
            added_count = 0
            for pest_disease_name, start_month, end_month in extended_monthly_data:
                if pest_disease_name in pest_disease_map.values():
                    pest_disease_id = next(k for k, v in pest_disease_map.items() if v == pest_disease_name)
                    
                    for species_id, species_name in species_list:
                        # 重複チェック
                        cursor.execute("""
                            SELECT COUNT(*) FROM species_pest_disease 
                            WHERE species_id = ? AND pest_disease_id = ? 
                            AND start_month = ? AND end_month = ?
                        """, (species_id, pest_disease_id, start_month, end_month))
                        
                        if cursor.fetchone()[0] == 0:
                            cursor.execute("""
                                INSERT INTO species_pest_disease 
                                (species_id, pest_disease_id, occurrence_probability, start_month, end_month, notes)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (species_id, pest_disease_id, 3, start_month, end_month, f"{pest_disease_name}の月別リスク"))
                            added_count += 1
            
            print(f"   - 月ベース拡張データ: {added_count}件追加")
            
            conn.commit()
            print("=== マイグレーション完了 ===")
            print("注意: seasonカラムは互換性のため残していますが、新しいAPIではstart_month/end_monthを使用します")
            
        except Exception as e:
            conn.rollback()
            print(f"マイグレーションエラー: {e}")
            raise
        finally:
            conn.close()

if __name__ == "__main__":
    migrate_to_monthly_risks() 