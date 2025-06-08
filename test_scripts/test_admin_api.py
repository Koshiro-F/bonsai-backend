#!/usr/bin/env python3
"""
管理者APIの動作テスト用スクリプト
"""

import requests
import json

API_BASE_URL = 'http://localhost:6000'

def test_admin_api():
    """管理者APIの基本動作をテスト"""
    
    print('=== 管理者API動作テスト ===')
    
    # テスト用の管理者ユーザーID（存在すると仮定）
    admin_user_id = 1
    
    try:
        # 1. マスタデータの概要を取得
        print('\n--- マスタデータ概要取得 ---')
        summary_url = f'{API_BASE_URL}/api/admin/master/summary?user_id={admin_user_id}'
        response = requests.get(summary_url)
        
        if response.status_code == 200:
            summary = response.json()
            print('✅ 概要取得成功:')
            for key, value in summary.items():
                print(f'  {key}: {value}')
        else:
            print(f'❌ 概要取得失敗: {response.status_code}')
            print(response.text)
            
        # 2. 農薬マスタ取得
        print('\n--- 農薬マスタ取得 ---')
        pesticides_url = f'{API_BASE_URL}/api/admin/master/pesticides?user_id={admin_user_id}'
        response = requests.get(pesticides_url)
        
        if response.status_code == 200:
            pesticides = response.json()
            print(f'✅ 農薬マスタ取得成功: {len(pesticides)}件')
            for pesticide in pesticides[:3]:  # 最初の3件を表示
                print(f'  {pesticide["name"]} ({pesticide["type"]})')
        else:
            print(f'❌ 農薬マスタ取得失敗: {response.status_code}')
            print(response.text)
            
        # 3. 害虫・病気マスタ取得
        print('\n--- 害虫・病気マスタ取得 ---')
        pest_diseases_url = f'{API_BASE_URL}/api/admin/master/pest-diseases?user_id={admin_user_id}'
        response = requests.get(pest_diseases_url)
        
        if response.status_code == 200:
            pest_diseases = response.json()
            print(f'✅ 害虫・病気マスタ取得成功: {len(pest_diseases)}件')
            for pest_disease in pest_diseases[:3]:  # 最初の3件を表示
                print(f'  {pest_disease["name"]} ({pest_disease["type"]})')
        else:
            print(f'❌ 害虫・病気マスタ取得失敗: {response.status_code}')
            print(response.text)
            
        # 4. 農薬効果マスタ取得
        print('\n--- 農薬効果マスタ取得 ---')
        effectiveness_url = f'{API_BASE_URL}/api/admin/master/pesticide-effectiveness?user_id={admin_user_id}'
        response = requests.get(effectiveness_url)
        
        if response.status_code == 200:
            effectiveness = response.json()
            print(f'✅ 農薬効果マスタ取得成功: {len(effectiveness)}件')
            for effect in effectiveness[:3]:  # 最初の3件を表示
                print(f'  {effect["pesticide_name"]} → {effect["pest_disease_name"]} (効果レベル: {effect["effectiveness_level"]})')
        else:
            print(f'❌ 農薬効果マスタ取得失敗: {response.status_code}')
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f'❌ API接続エラー: {e}')
        print('Flaskサーバーが起動しているか確認してください')
        
    except Exception as e:
        print(f'❌ 予期しないエラー: {e}')

def test_admin_add_pesticide():
    """農薬追加のテスト"""
    print('\n=== 農薬追加テスト ===')
    
    admin_user_id = 1
    
    # テスト用の新しい農薬データ
    new_pesticide = {
        "user_id": admin_user_id,
        "name": "テスト農薬2",
        "type": "insecticide",
        "interval_days": 10,
        "active_ingredient": "テスト成分",
        "description": "APIテスト用農薬"
    }
    
    try:
        add_url = f'{API_BASE_URL}/api/admin/master/pesticides'
        response = requests.post(add_url, json=new_pesticide)
        
        if response.status_code == 201:
            result = response.json()
            print(f'✅ 農薬追加成功: {result["message"]}')
        else:
            print(f'❌ 農薬追加失敗: {response.status_code}')
            print(response.text)
            
    except Exception as e:
        print(f'❌ 農薬追加エラー: {e}')

def test_non_admin_access():
    """非管理者ユーザーのアクセステスト"""
    print('\n=== 非管理者ユーザーアクセステスト ===')
    
    # 非管理者ユーザーID（存在すると仮定）
    regular_user_id = 2
    
    try:
        summary_url = f'{API_BASE_URL}/api/admin/master/summary?user_id={regular_user_id}'
        response = requests.get(summary_url)
        
        if response.status_code == 403:
            print('✅ 権限チェック正常: 非管理者のアクセスを正しく拒否')
        elif response.status_code == 401:
            print('✅ 認証チェック正常: 未認証ユーザーのアクセスを正しく拒否')
        else:
            print(f'⚠️ 予期しないレスポンス: {response.status_code}')
            print(response.text)
            
    except Exception as e:
        print(f'❌ アクセステストエラー: {e}')

if __name__ == "__main__":
    test_admin_api()
    test_admin_add_pesticide()
    test_non_admin_access()
    print('\n=== テスト完了 ===') 