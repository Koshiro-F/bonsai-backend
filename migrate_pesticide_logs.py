#!/usr/bin/env python3
"""
農薬ログテーブルに詳細フィールドを追加するマイグレーションスクリプト
"""

import sqlite3
import os
from app import create_app

def migrate_pesticide_logs():
    """pesticide_logsテーブルに新しいカラムを追加"""
    app = create_app()
    
    with app.app_context():
        db_path = app.config['DATABASE']
        
        if not os.path.exists(db_path):
            print(f"データベースファイル {db_path} が見つかりません")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 既存カラムの確認
        cursor.execute("PRAGMA table_info(pesticide_logs)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"既存カラム: {columns}")
        
        # 新しいカラムを追加
        new_columns = [
            ('dosage', 'TEXT'),  # 既存のamountフィールドと統合用
            ('water_amount', 'TEXT'),  # 水の分量
            ('dilution_ratio', 'TEXT'),  # 希釈濃度
            ('actual_usage_amount', 'TEXT')  # 実際の使用量
        ]
        
        for col_name, col_type in new_columns:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE pesticide_logs ADD COLUMN {col_name} {col_type}")
                    print(f"カラム {col_name} を追加しました")
                except sqlite3.Error as e:
                    print(f"カラム {col_name} の追加でエラー: {e}")
        
        # 既存のamountフィールドをdosageにコピー（データが存在する場合）
        cursor.execute("SELECT COUNT(*) FROM pesticide_logs WHERE amount IS NOT NULL AND amount != ''")
        amount_count = cursor.fetchone()[0]
        
        if amount_count > 0:
            cursor.execute("UPDATE pesticide_logs SET dosage = amount WHERE dosage IS NULL OR dosage = ''")
            print(f"{amount_count}件のamountデータをdosageにコピーしました")
        
        conn.commit()
        conn.close()
        print("マイグレーション完了")

if __name__ == "__main__":
    migrate_pesticide_logs() 