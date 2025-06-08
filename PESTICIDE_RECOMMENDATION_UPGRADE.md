# 盆栽農薬推奨システム v2.0 アップグレード

## 概要
従来の単純な日数判定から、樹種別・季節別・履歴分析に基づく高度な農薬推奨システムにアップグレードしました。

## 主な改善点

### 1. 樹種別農薬マッピング
- 11種類の樹種それぞれに最適な農薬を定義
- 各樹種の特性に応じた殺虫剤・殺菌剤の組み合わせ
- 優先順位と季節適合性を考慮

**対応樹種:**
- 松類: 黒松、五葉松、赤松
- 針葉樹: 真柏、杜松
- 花物: 信州梅、長寿梅
- 雑木: ケヤキ、カエデ、イロハモミジ
- その他: シナ百日紅

### 2. 季節適合性判定
- 春夏秋冬の季節に応じた適切な農薬選択
- 梅雨期・開花期など特定時期の専用推奨
- 現在の季節と農薬の適用時期のマッチング

**季節カテゴリ:**
- 通年: いつでも使用可能
- 春夏: 成長期向け
- 夏秋: 害虫活動期
- 梅雨: 湿度対策
- 冬: 休眠期対策
- 開花前後: 花物専用

### 3. 農薬ローテーション管理
- 同一農薬の連続使用を避ける
- 抵抗性発達の防止
- 使用頻度の監視（90日間で3回まで）

### 4. 履歴分析機能
- 過去90日間の使用履歴を分析
- 殺虫剤・殺菌剤のバランス管理
- 最適な散布タイミングの判定

### 5. インテリジェント推奨
- 複数要素を総合した推奨判定
- 信頼度レベルの提供
- 詳細な推奨理由の説明

## 新規API エンドポイント

### 既存エンドポイント（改良済み）
```
GET /api/pesticides/recommendation/{bonsai_id}?user_id={user_id}
```
**改良点:**
- 樹種別推奨
- 季節適合性判定
- 履歴分析結果
- 信頼度とアドバイス

**レスポンス例:**
```json
{
  "recommendation": "ベニカ",
  "reason": "定期散布推奨（通年期・ローテーション考慮）",
  "interval_days": 7,
  "days_since_last": 8,
  "season_advice": "現在は冬です。",
  "confidence": "高",
  "analysis": {
    "total_applications": 3,
    "pesticide_frequency": {"オルトラン": 2, "ベニカ": 1},
    "last_pesticide_type": "insecticide"
  }
}
```

### 新規エンドポイント

#### 1. 樹種別推奨農薬取得
```
GET /api/pesticides/recommended/species/{species_id}
```

#### 2. API情報取得
```
GET /api/pesticides/api-info
```

#### 3. 推奨テスト・シミュレーション
```
GET /api/pesticides/test-recommendation/{species_id}
```

#### 4. 樹種別農薬情報
```
GET /api/pesticides/species/{species_id}/pesticides
```

## 技術的改善

### コード構造
- `SPECIES_PESTICIDE_MAPPING`: 樹種別農薬データベース
- `get_current_season()`: 季節判定機能
- `analyze_pesticide_history()`: 履歴分析機能
- `get_intelligent_recommendation()`: 統合推奨エンジン

### 推奨ロジック
1. 樹種IDから適用可能農薬を取得
2. 現在の季節との適合性をチェック
3. 使用履歴から連続使用を回避
4. 殺菌剤の必要性を独立判定
5. 最終的な推奨農薬を決定

### データ品質向上
- 農薬タイプの分類（殺虫剤、殺菌剤、殺虫殺菌剤）
- 詳細な用法・用量情報
- 科学的根拠に基づく推奨間隔

## テスト・検証

### テストスクリプト
`test_improved_recommendations.py` を使用して以下をテスト:
- API機能の動作確認
- 樹種別推奨の正確性
- 季節適合性の検証
- エラーハンドリング

### 実行方法
```bash
# 1. Flaskアプリ起動
python app.py

# 2. テスト実行
python test_improved_recommendations.py
```

## フロントエンドでの活用

### 表示すべき新情報
- 推奨理由の詳細表示
- 信頼度レベル
- 季節アドバイス
- 使用履歴サマリー

### 推奨UI改善
```javascript
// 推奨結果の表示例
const RecommendationDisplay = ({ recommendation }) => (
  <div className="recommendation-card">
    <h3>推奨農薬: {recommendation.recommendation}</h3>
    <p className="reason">{recommendation.reason}</p>
    <p className="season">{recommendation.season_advice}</p>
    <div className="confidence">
      信頼度: {recommendation.confidence}
    </div>
    {recommendation.analysis && (
      <div className="analysis">
        <p>過去90日の使用回数: {recommendation.analysis.total_applications}</p>
      </div>
    )}
  </div>
);
```

## 今後の拡張予定

### 1. 機械学習統合
- 使用データからのパターン学習
- 個別盆栽の特性考慮
- 効果測定データの活用

### 2. 外部要因対応
- 天気予報との連携
- 地域別害虫発生予報
- 季節変動の細分化

### 3. 通知機能
- 散布タイミングのプッシュ通知
- 在庫切れアラート
- 季節変更時の注意喚起

## まとめ
このアップグレードにより、盆栽愛好家により科学的で個別最適化された農薬推奨を提供できるようになりました。樹種の特性、季節の変化、使用履歴を総合的に考慮することで、より効果的で安全な盆栽管理をサポートします。 