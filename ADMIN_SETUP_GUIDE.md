# 管理者用マスタデータ管理機能 セットアップガイド

## 概要

このガイドでは、盆栽管理システムの管理者用マスタデータ管理機能の設定と使用方法について説明します。

## 機能一覧

管理者は以下のマスタデータを管理できます：

1. **農薬マスタ** - 農薬の基本情報（名前、タイプ、散布間隔、有効成分等）
2. **害虫・病気マスタ** - 害虫・病気の情報（名前、タイプ、発生季節等）
3. **農薬効果マスタ** - 農薩と対象害虫・病気の効果関係（1-5段階評価）
4. **樹種別害虫・病気マスタ** - 樹種ごとの害虫・病気発生リスク
5. **樹種別NG薬剤マスタ** - 樹種に対する禁止・警告薬剤

## セットアップ手順

### 1. データベースの初期化

```bash
cd flask-bonsai
flask init-db
flask init-master-data
```

### 2. 管理者ユーザーの作成

```bash
python create_admin_user.py
```

デフォルトの管理者アカウント：
- ユーザー名: `admin`
- パスワード: `admin123`

**⚠️ 本番環境では必ずパスワードを変更してください**

### 3. マスタデータの投入

```bash
python migrate_master_data.py
```

### 4. APIの動作確認

```bash
python test_admin_api.py
```

## APIエンドポイント

### 基本URL
```
/api/admin/master
```

### 主要エンドポイント

#### 概要取得
```
GET /api/admin/master/summary?user_id={admin_user_id}
```

#### 農薬マスタ
```
GET    /api/admin/master/pesticides?user_id={admin_user_id}
POST   /api/admin/master/pesticides
PUT    /api/admin/master/pesticides/{id}
DELETE /api/admin/master/pesticides/{id}
```

#### 害虫・病気マスタ
```
GET    /api/admin/master/pest-diseases?user_id={admin_user_id}
POST   /api/admin/master/pest-diseases
DELETE /api/admin/master/pest-diseases/{id}
```

#### 農薬効果マスタ
```
GET    /api/admin/master/pesticide-effectiveness?user_id={admin_user_id}
POST   /api/admin/master/pesticide-effectiveness
DELETE /api/admin/master/pesticide-effectiveness/{id}
```

## フロントエンド使用方法

### 1. 管理者としてログイン

1. ユーザー名: `admin`、パスワード: `admin123` でログイン
2. ダッシュボードのサイドメニューに「🛠️ マスタ管理」が表示される
3. ユーザー名横に「管理者」バッジが表示される

### 2. マスタデータの管理

#### 農薬マスタの管理
- **閲覧**: 農薬マスタタブで既存の農薬一覧を確認
- **追加**: 「農薬追加」ボタンから新しい農薬を登録
- **削除**: 各行の「削除」ボタンで農薬を削除

#### 害虫・病気マスタの管理
- **閲覧**: 害虫・病気マスタタブで既存データを確認
- **追加**: 「害虫・病気追加」ボタンから新規登録
- **削除**: 関連データがない場合のみ削除可能

#### 農薬効果マスタの管理
- **閲覧**: 農薬効果マスタタブで農薩と対象の効果関係を確認
- **追加**: 「効果関係追加」ボタンで新しい効果関係を設定
- **削除**: 既存の効果関係を削除

### 3. データ安全性

- 関連データが存在する場合、マスタデータの削除は自動的に拒否されます
- 管理者権限のないユーザーはマスタ管理ページにアクセスできません
- すべての操作は管理者権限の確認後に実行されます

## データベーススキーマ

### pesticide_master
```sql
- id: INTEGER (Primary Key)
- name: TEXT (農薩名)
- type: TEXT ('insecticide'/'fungicide')
- interval_days: INTEGER (散布間隔)
- active_ingredient: TEXT (有効成分)
- description: TEXT (説明)
```

### pest_disease_master
```sql
- id: INTEGER (Primary Key)
- name: TEXT (名前)
- type: TEXT ('pest'/'disease')
- description: TEXT (説明)
- season: TEXT (発生季節)
```

### pesticide_effectiveness
```sql
- id: INTEGER (Primary Key)
- pesticide_id: INTEGER (農薩ID)
- pest_disease_id: INTEGER (害虫・病気ID)
- effectiveness_level: INTEGER (効果レベル 1-5)
- notes: TEXT (備考)
```

### species_pest_disease
```sql
- id: INTEGER (Primary Key)
- species_id: INTEGER (樹種ID)
- pest_disease_id: INTEGER (害虫・病気ID)
- occurrence_probability: INTEGER (発生確率 1-5)
- season: TEXT (季節)
- notes: TEXT (備考)
```

### species_prohibited_pesticides
```sql
- id: INTEGER (Primary Key)
- species_id: INTEGER (樹種ID)
- pesticide_id: INTEGER (農薩ID)
- severity: TEXT ('warning'/'prohibited')
- reason: TEXT (理由)
- notes: TEXT (備考)
```

## トラブルシューティング

### よくある問題

1. **管理者メニューが表示されない**
   - ユーザーのroleが'admin'に設定されているか確認
   - ブラウザキャッシュをクリアして再ログイン

2. **APIエラー (403 Forbidden)**
   - ユーザーIDが正しく渡されているか確認
   - 管理者権限があるか確認

3. **データ削除ができない**
   - 関連データが存在する可能性を確認
   - まず関連データを削除してから再試行

4. **新しいデータが追加できない**
   - 必須フィールドがすべて入力されているか確認
   - 重複する名前がないか確認

### ログ確認

```bash
# Flaskアプリケーションのログを確認
tail -f flask-bonsai/logs/app.log

# SQLiteデータベースの直接確認
sqlite3 flask-bonsai/instance/bonsai_users.db
.tables
.schema pesticide_master
```

## セキュリティ注意事項

1. **パスワード管理**
   - デフォルトの管理者パスワードは必ず変更
   - 強力なパスワードを使用

2. **権限管理**
   - 管理者権限は必要最小限のユーザーのみに付与
   - 定期的な権限見直し

3. **データバックアップ**
   - 重要なマスタデータは定期的にバックアップ
   - データ変更前には必ずバックアップを取得

## サポート

問題が発生した場合は、以下の情報を含めてお問い合わせください：

- エラーメッセージ
- 実行した操作
- ブラウザとバージョン
- 実行環境（OS、Pythonバージョン等） 