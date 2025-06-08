#!/usr/bin/env python3
"""
盆栽農薬推奨システム v2.0 テストスクリプト
樹種別・季節別・履歴分析に基づく推奨システムのテスト
"""

import requests
import json
from datetime import datetime

# FlaskアプリケーションのベースURL（必要に応じて変更）
BASE_URL = "http://localhost:5000"

def test_api_info():
    """APIの情報を取得してテスト"""
    print("=== API情報テスト ===")
    try:
        response = requests.get(f"{BASE_URL}/api/pesticides/api-info")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API情報取得成功")
            print(f"タイトル: {data['title']}")
            print(f"現在の季節: {data['current_season']}")
            print(f"サポート樹種数: {len(data['supported_species'])}")
            return True
        else:
            print(f"❌ API情報取得失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API情報テストエラー: {e}")
        return False

def test_species_pesticides(species_id=1):
    """樹種別農薬情報のテスト"""
    print(f"\n=== 樹種別農薬情報テスト (樹種ID: {species_id}) ===")
    try:
        response = requests.get(f"{BASE_URL}/api/pesticides/recommended/species/{species_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 樹種別農薬情報取得成功")
            print(f"樹種ID: {data['species_id']}")
            print(f"主要農薬数: {len(data['primary_pesticides'])}")
            print(f"殺菌剤数: {len(data['fungicides'])}")
            print(f"現在の季節: {data['current_season']}")
            
            if data['primary_pesticides']:
                print(f"推奨主要農薬: {data['primary_pesticides'][0]['name']}")
            return True
        else:
            print(f"❌ 樹種別農薬情報取得失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 樹種別農薬情報テストエラー: {e}")
        return False

def test_recommendation_simulation(species_id=3):
    """推奨シミュレーションのテスト"""
    print(f"\n=== 推奨シミュレーションテスト (樹種ID: {species_id}) ===")
    try:
        response = requests.get(f"{BASE_URL}/api/pesticides/test-recommendation/{species_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 推奨シミュレーション成功")
            print(f"樹種ID: {data['species_id']}")
            print(f"現在の季節: {data['current_season']}")
            print(f"季節適合推奨数: {data['recommendation_count']}")
            
            if data['seasonal_recommendations']:
                for i, rec in enumerate(data['seasonal_recommendations'][:3]):
                    print(f"  {i+1}. {rec['name']} ({rec['season']}, 間隔: {rec['interval_days']}日)")
            return True
        else:
            print(f"❌ 推奨シミュレーション失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 推奨シミュレーションテストエラー: {e}")
        return False

def test_pesticide_list():
    """農薬リストのテスト"""
    print(f"\n=== 農薬リストテスト ===")
    try:
        response = requests.get(f"{BASE_URL}/api/pesticides/list")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 農薬リスト取得成功")
            print(f"登録農薬数: {len(data)}")
            
            # タイプ別集計
            types = {}
            for pesticide in data:
                pest_type = pesticide.get('type', '不明')
                types[pest_type] = types.get(pest_type, 0) + 1
            
            print("農薬タイプ別集計:")
            for pest_type, count in types.items():
                print(f"  {pest_type}: {count}種類")
            return True
        else:
            print(f"❌ 農薬リスト取得失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 農薬リストテストエラー: {e}")
        return False

def test_bonsai_species():
    """盆栽樹種リストのテスト"""
    print(f"\n=== 盆栽樹種リストテスト ===")
    try:
        response = requests.get(f"{BASE_URL}/api/bonsai/species")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 樹種リスト取得成功")
            print(f"登録樹種数: {len(data)}")
            
            # 最初の5種類を表示
            print("登録樹種（最初の5種類）:")
            for species in data[:5]:
                print(f"  ID:{species['id']} {species['name']} ({species['scientific_name']})")
            return True
        else:
            print(f"❌ 樹種リスト取得失敗: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 樹種リストテストエラー: {e}")
        return False

def run_all_tests():
    """全テストを実行"""
    print("🧪 盆栽農薬推奨システム v2.0 テスト開始")
    print(f"テスト実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests = [
        ("API情報", test_api_info),
        ("農薬リスト", test_pesticide_list),
        ("樹種リスト", test_bonsai_species),
        ("樹種別農薬情報", lambda: test_species_pesticides(1)),  # 黒松
        ("真柏農薬情報", lambda: test_species_pesticides(3)),     # 真柏
        ("推奨シミュレーション", lambda: test_recommendation_simulation(3))  # 真柏
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 50)
    print("📊 テスト結果サマリー")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n合計: {passed}/{total} テスト通過")
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
    else:
        print("⚠️  一部のテストが失敗しました。Flaskアプリケーションが起動していることを確認してください。")

if __name__ == "__main__":
    print("使用方法:")
    print("1. Flaskアプリケーションを起動: python app.py")
    print("2. 別のターミナルでテスト実行: python test_improved_recommendations.py")
    print()
    
    input("Enterキーを押してテストを開始してください...")
    run_all_tests() 