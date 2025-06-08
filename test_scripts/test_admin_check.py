#!/usr/bin/env python3
"""
管理者権限チェックのテスト用スクリプト
"""

import requests

API_BASE_URL = 'http://localhost:6000'

def test_admin_check():
    """管理者権限チェックの動作をテスト"""
    
    print('=== 管理者権限チェックテスト ===')
    
    # テスト用ユーザーID
    test_cases = [
        {"user_id": 1, "expected": "管理者", "description": "管理者ユーザー"},
        {"user_id": 2, "expected": "一般ユーザー", "description": "一般ユーザー"},
        {"user_id": 999, "expected": "存在しないユーザー", "description": "存在しないユーザー"}
    ]
    
    for case in test_cases:
        print(f'\n--- {case["description"]}（ID: {case["user_id"]}）のテスト ---')
        
        try:
            # is-adminエンドポイントをテスト
            url = f'{API_BASE_URL}/api/user/is-admin/{case["user_id"]}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    is_admin = data.get('is_admin', False)
                    if is_admin:
                        print(f'✅ 管理者として認識されました')
                    else:
                        print(f'✅ 一般ユーザーとして認識されました')
                else:
                    print(f'❌ APIエラー: {data.get("message", "不明なエラー")}')
            else:
                print(f'❌ HTTPエラー: {response.status_code}')
                print(response.text)
                
            # ユーザー情報も取得してみる
            user_url = f'{API_BASE_URL}/api/user/{case["user_id"]}'
            user_response = requests.get(user_url)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                if user_data.get('success'):
                    user_info = user_data.get('user', {})
                    print(f'   ユーザー情報: {user_info.get("username", "不明")} ({user_info.get("role", "不明")})')
                else:
                    print(f'   ユーザー情報取得失敗: {user_data.get("message", "不明なエラー")}')
            else:
                print(f'   ユーザー情報取得失敗: HTTP {user_response.status_code}')
                
        except requests.exceptions.RequestException as e:
            print(f'❌ 接続エラー: {e}')
        except Exception as e:
            print(f'❌ 予期しないエラー: {e}')

if __name__ == "__main__":
    test_admin_check()
    print('\n=== テスト完了 ===') 