from flask import Blueprint, jsonify, current_app, request
from flask_cors import cross_origin
from ..db import get_db
from datetime import datetime, timedelta
import calendar

bp = Blueprint('recommend', __name__, url_prefix='/api/pesticides')

def get_current_season():
    """現在の季節を取得（互換性のため残存）"""
    month = datetime.now().month
    if month in [3, 4, 5]:
        return "春"
    elif month in [6, 7, 8]:
        return "夏"
    elif month in [9, 10, 11]:
        return "秋"
    else:
        return "冬"

def is_month_in_range(target_month, start_month, end_month):
    """指定月が月範囲内にあるかチェック（年をまたぐ場合も対応）"""
    if start_month <= end_month:
        # 通常の範囲（例: 3月-6月）
        return start_month <= target_month <= end_month
    else:
        # 年をまたぐ範囲（例: 12月-2月）
        return target_month >= start_month or target_month <= end_month

def get_monthly_risks_for_month(db, species_id, target_month):
    """指定月の樹種別害虫・病気リスクを取得（月ベース）"""
    # 月ベースデータを優先、なければ季節ベースをフォールバック
    query = '''
        SELECT spd.*, pdm.name as pest_disease_name, pdm.type as pest_disease_type, 
               pdm.start_month, pdm.end_month, pdm.season as pest_disease_season,
               pdm.description as pest_disease_description
        FROM species_pest_disease spd
        JOIN pest_disease_master pdm ON spd.pest_disease_id = pdm.id
        WHERE spd.species_id = ?
        ORDER BY spd.occurrence_probability DESC, pdm.type DESC
    '''
    
    all_risks = db.execute(query, (species_id,)).fetchall()
    filtered_risks = []
    
    for risk in all_risks:
        risk_dict = dict(risk)
        
        # まず月ベースデータをチェック
        if risk_dict['start_month'] and risk_dict['end_month']:
            # species_pest_diseaseテーブルの月データ優先
            spd_start = risk_dict.get('start_month')
            spd_end = risk_dict.get('end_month')
            if spd_start and spd_end and is_month_in_range(target_month, spd_start, spd_end):
                filtered_risks.append(risk_dict)
                continue
        
        # pest_disease_masterの月データをチェック
        if risk_dict.get('start_month') and risk_dict.get('end_month'):
            if is_month_in_range(target_month, risk_dict['start_month'], risk_dict['end_month']):
                filtered_risks.append(risk_dict)
                continue
        
        # フォールバック: 季節ベースデータをチェック
        season = risk_dict.get('pest_disease_season') or risk_dict.get('season')
        if season:
            current_season = get_month_season(target_month)
            if (season == "通年" or 
                season == current_season or
                (season == "梅雨" and target_month == 6)):
                filtered_risks.append(risk_dict)
    
    return filtered_risks

def get_month_season(month):
    """指定された月の季節を取得（互換性のため残存）"""
    if month in [3, 4, 5]:
        return "春"
    elif month in [6, 7, 8]:
        return "夏"
    elif month in [9, 10, 11]:
        return "秋"
    else:
        return "冬"

def get_seasonal_risks_for_month(db, species_id, target_month):
    """指定月の樹種別害虫・病気リスクを取得（月ベースに移行）"""
    return get_monthly_risks_for_month(db, species_id, target_month)

def get_season_for_matching(season):
    """季節マッチング用の季節判定（互換性のため残存）"""
    current = get_current_season()
    
    # 梅雨は夏に含める
    if season == "梅雨" and current == "夏":
        return True
    elif season == "通年":
        return True
    elif season == current:
        return True
    else:
        return False

def get_species_pest_disease_risks(db, species_id):
    """樹種別の害虫・病気リスクを取得（月ベース対応）"""
    query = '''
        SELECT spd.*, pdm.name as pest_disease_name, pdm.type as pest_disease_type, 
               pdm.season as pest_disease_season, pdm.start_month, pdm.end_month
        FROM species_pest_disease spd
        JOIN pest_disease_master pdm ON spd.pest_disease_id = pdm.id
        WHERE spd.species_id = ?
        ORDER BY spd.occurrence_probability DESC
    '''
    
    risks = db.execute(query, (species_id,)).fetchall()
    return [dict(risk) for risk in risks]

def get_effective_pesticides(db, pest_disease_ids, current_season):
    """指定された害虫・病気に効果的な農薬を取得"""
    if not pest_disease_ids:
        return []
    
    placeholders = ','.join(['?'] * len(pest_disease_ids))
    query = f'''
        SELECT pe.*, pm.name as pesticide_name, pm.type as pesticide_type, 
               pm.interval_days, pm.active_ingredient, pm.description,
               AVG(pe.effectiveness_level) as avg_effectiveness
        FROM pesticide_effectiveness pe
        JOIN pesticide_master pm ON pe.pesticide_id = pm.id
        WHERE pe.pest_disease_id IN ({placeholders})
        GROUP BY pe.pesticide_id
        ORDER BY avg_effectiveness DESC, pm.interval_days ASC
    '''
    
    pesticides = db.execute(query, pest_disease_ids).fetchall()
    return [dict(pesticide) for pesticide in pesticides]

def get_prohibited_pesticides(db, species_id):
    """樹種に対する禁止・警告農薬を取得"""
    query = '''
        SELECT spp.*, pm.name as pesticide_name
        FROM species_prohibited_pesticides spp
        JOIN pesticide_master pm ON spp.pesticide_id = pm.id
        WHERE spp.species_id = ?
    '''
    
    prohibited = db.execute(query, (species_id,)).fetchall()
    return [dict(p) for p in prohibited]

def filter_by_season_and_prohibition(pesticides, species_id, db, current_season):
    """季節と禁止薬剤でフィルタリング"""
    # 禁止薬剤を取得
    prohibited = get_prohibited_pesticides(db, species_id)
    prohibited_names = {p['pesticide_name']: p for p in prohibited}
    
    filtered = []
    for pesticide in pesticides:
        name = pesticide['pesticide_name']
        
        # 禁止薬剤チェック
        if name in prohibited_names:
            prohibition = prohibited_names[name]
            if prohibition['severity'] == 'prohibited':
                continue  # 完全禁止の場合はスキップ
            elif prohibition['severity'] == 'warning':
                # 警告の場合は注意情報を付加
                pesticide['warning'] = prohibition['reason']
        
        filtered.append(pesticide)
    
    return filtered

def analyze_pesticide_history(db, bonsai_id, days_back=90):
    """過去の農薬使用履歴を分析"""
    cutoff_date = (datetime.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    history = db.execute(
        'SELECT * FROM pesticide_logs WHERE bonsai_id = ? AND date >= ? ORDER BY date DESC',
        (bonsai_id, cutoff_date)
    ).fetchall()
    
    analysis = {
        "total_applications": len(history),
        "pesticide_frequency": {},
        "last_pesticide_type": None,
        "days_since_fungicide": None,
        "days_since_insecticide": None,
        "recent_pesticides": []
    }
    
    today = datetime.today()
    
    for i, log in enumerate(history):
        pesticide_name = log['pesticide_name']
        log_date = datetime.strptime(log['date'], "%Y-%m-%d")
        days_ago = (today - log_date).days
        
        # 使用頻度をカウント
        if pesticide_name not in analysis["pesticide_frequency"]:
            analysis["pesticide_frequency"][pesticide_name] = 0
        analysis["pesticide_frequency"][pesticide_name] += 1
        
        # 最近使用した農薬リスト（重複を避ける）
        if len(analysis["recent_pesticides"]) < 3 and pesticide_name not in analysis["recent_pesticides"]:
            analysis["recent_pesticides"].append(pesticide_name)
        
        # 農薬タイプを判定
        pesticide_info = db.execute(
            'SELECT type FROM pesticide_master WHERE name = ?',
            (pesticide_name,)
        ).fetchone()
        
        if pesticide_info:
            pesticide_type = pesticide_info['type']
            if analysis["last_pesticide_type"] is None:
                analysis["last_pesticide_type"] = pesticide_type
                if pesticide_type == "fungicide":
                    analysis["days_since_fungicide"] = days_ago
                else:
                    analysis["days_since_insecticide"] = days_ago
    
    return analysis

def apply_rotation_logic(pesticides, history_analysis, latest_log):
    """農薬ローテーションロジックを適用"""
    if not pesticides:
        return None
    
    # 最近使用した農薬を避ける
    recent_pesticides = set(history_analysis.get("recent_pesticides", []))
    
    # 使用頻度を考慮してスコアリング
    scored_pesticides = []
    for pesticide in pesticides:
        name = pesticide['pesticide_name']
        score = pesticide['avg_effectiveness']
        
        # 最近使用した農薬はスコアを下げる
        if name in recent_pesticides:
            score -= 2
        
        # 使用頻度が高い農薬はスコアを下げる
        frequency = history_analysis.get("pesticide_frequency", {}).get(name, 0)
        score -= frequency * 0.5
        
        # 最後に使用した農薬と同じ場合は大幅減点
        if latest_log and latest_log["pesticide_name"] == name:
            score -= 3
        
        pesticide['rotation_score'] = score
        scored_pesticides.append(pesticide)
    
    # スコア順にソート
    scored_pesticides.sort(key=lambda x: x['rotation_score'], reverse=True)
    return scored_pesticides

def get_intelligent_recommendation(db, bonsai, latest_log):
    """マスタテーブルベースのインテリジェントな推奨（月ベース対応、殺虫剤・殺菌剤別）"""
    species_id = bonsai['species_id']
    today = datetime.today()
    current_month = today.month
    current_season = get_current_season()
    
    # 履歴分析
    history_analysis = analyze_pesticide_history(db, bonsai['id'])
    
    # 樹種の害虫・病気リスクを取得（当月）
    monthly_risks = get_monthly_risks_for_month(db, species_id, current_month)
    
    if not monthly_risks:
        # 月データがない場合はフォールバック
        return get_fallback_recommendation_separated(db, current_season, history_analysis, latest_log)
    
    # 害虫リスクと病気リスクを分離
    pest_risks = [r for r in monthly_risks if r['pest_disease_type'] == 'pest']
    disease_risks = [r for r in monthly_risks if r['pest_disease_type'] == 'disease']
    
    # 高リスクの害虫・病気を優先
    high_priority_pest_risks = [r for r in pest_risks if r['occurrence_probability'] >= 4]
    if not high_priority_pest_risks:
        high_priority_pest_risks = pest_risks[:3]  # 上位3つを選択
    
    high_priority_disease_risks = [r for r in disease_risks if r['occurrence_probability'] >= 4]
    if not high_priority_disease_risks:
        high_priority_disease_risks = disease_risks[:3]  # 上位3つを選択
    
    # 散布間隔のチェック
    if latest_log:
        try:
            last_date = datetime.strptime(latest_log["date"], "%Y-%m-%d")
            days_since_last = (today - last_date).days
        except (KeyError, ValueError, TypeError):
            days_since_last = 0
    else:
        days_since_last = 999  # 初回の場合
    
    # 殺虫剤の推奨を取得
    insecticide_recommendation = get_pesticide_type_recommendation(
        db, high_priority_pest_risks, 'insecticide', species_id, 
        current_season, history_analysis, latest_log, days_since_last, current_month
    )
    
    # 殺菌剤の推奨を取得
    fungicide_recommendation = get_pesticide_type_recommendation(
        db, high_priority_disease_risks, 'fungicide', species_id, 
        current_season, history_analysis, latest_log, days_since_last, current_month
    )
    
    return {
        "insecticide": insecticide_recommendation,
        "fungicide": fungicide_recommendation,
        "general_info": {
            "season_advice": f"現在は{current_season}（{current_month}月）です。",
            "analysis": history_analysis,
            "days_since_last": days_since_last
        }
    }

def get_pesticide_type_recommendation(db, target_risks, pesticide_type, species_id, 
                                    current_season, history_analysis, latest_log, 
                                    days_since_last, current_month):
    """指定されたタイプ（殺虫剤・殺菌剤）の推奨を取得"""
    if not target_risks:
        return get_no_risk_recommendation(pesticide_type)
    
    # 対象の害虫・病気IDを抽出
    target_pest_disease_ids = [r['pest_disease_id'] for r in target_risks]
    
    # 効果的な農薬を取得（指定タイプのみ）
    effective_pesticides = get_effective_pesticides_by_type(
        db, target_pest_disease_ids, pesticide_type, current_season
    )
    
    if not effective_pesticides:
        return get_no_pesticide_recommendation(pesticide_type)
    
    # 季節と禁止薬剤でフィルタリング
    filtered_pesticides = filter_by_season_and_prohibition(
        effective_pesticides, species_id, db, current_season
    )
    
    if not filtered_pesticides:
        return get_no_pesticide_recommendation(pesticide_type)
    
    # ローテーションロジックを適用
    final_candidates = apply_rotation_logic(filtered_pesticides, history_analysis, latest_log)
    
    if not final_candidates:
        return get_no_pesticide_recommendation(pesticide_type)
    
    # 推奨農薬を決定
    recommended = final_candidates[0]
    
    # 散布間隔チェック
    if latest_log and days_since_last < recommended['interval_days']:
        return {
            "recommendation": "散布間隔を空けてください",
            "reason": f"前回散布から{days_since_last}日経過（推奨間隔: {recommended['interval_days']}日）",
            "interval_days": recommended['interval_days'],
            "next_application_date": (datetime.strptime(latest_log["date"], "%Y-%m-%d") + 
                                    timedelta(days=recommended['interval_days'])).strftime("%Y-%m-%d"),
            "confidence": "高",
            "pesticide_type": pesticide_type,
            "status": "wait"
        }
    
    # 推奨結果を作成
    result = {
        "recommendation": recommended['pesticide_name'],
        "reason": f"{recommended['pesticide_type']}推奨（対象: {', '.join([r['pest_disease_name'] for r in target_risks[:2]])}）",
        "interval_days": recommended['interval_days'],
        "pesticide_type": recommended['pesticide_type'],
        "effectiveness": round(recommended['avg_effectiveness'], 1),
        "active_ingredient": recommended.get('active_ingredient', ''),
        "confidence": "高",
        "target_pests": [r['pest_disease_name'] for r in target_risks],
        "status": "recommend"
    }
    
    # 警告がある場合は追加
    if 'warning' in recommended:
        result['warning'] = recommended['warning']
    
    return result

def get_effective_pesticides_by_type(db, pest_disease_ids, pesticide_type, current_season):
    """指定されたタイプの農薬に絞って効果的な農薬を取得"""
    if not pest_disease_ids:
        return []
    
    placeholders = ','.join(['?'] * len(pest_disease_ids))
    query = f'''
        SELECT pe.*, pm.name as pesticide_name, pm.type as pesticide_type, 
               pm.interval_days, pm.active_ingredient, pm.description,
               AVG(pe.effectiveness_level) as avg_effectiveness
        FROM pesticide_effectiveness pe
        JOIN pesticide_master pm ON pe.pesticide_id = pm.id
        WHERE pe.pest_disease_id IN ({placeholders}) AND pm.type = ?
        GROUP BY pe.pesticide_id
        ORDER BY avg_effectiveness DESC, pm.interval_days ASC
    '''
    
    pesticides = db.execute(query, pest_disease_ids + [pesticide_type]).fetchall()
    return [dict(pesticide) for pesticide in pesticides]

def get_no_risk_recommendation(pesticide_type):
    """リスクがない場合の推奨"""
    type_name = "殺虫剤" if pesticide_type == "insecticide" else "殺菌剤"
    return {
        "recommendation": f"現在{type_name}は不要です",
        "reason": f"現在の時期に対応する害虫・病気のリスクは低いです",
        "confidence": "高",
        "pesticide_type": pesticide_type,
        "status": "no_need"
    }

def get_no_pesticide_recommendation(pesticide_type):
    """推奨農薬がない場合の推奨"""
    type_name = "殺虫剤" if pesticide_type == "insecticide" else "殺菌剤"
    fallback_name = "オルトラン" if pesticide_type == "insecticide" else "トップジンM"
    
    return {
        "recommendation": fallback_name,
        "reason": f"汎用{type_name}を推奨（データ不足）",
        "interval_days": 14,
        "pesticide_type": pesticide_type,
        "confidence": "低",
        "status": "fallback"
    }

def get_fallback_recommendation_separated(db, current_season, history_analysis, latest_log):
    """フォールバック推奨（殺虫剤・殺菌剤別）"""
    # 汎用的な農薬を取得
    insecticides = db.execute('''
        SELECT * FROM pesticide_master 
        WHERE type = 'insecticide'
        ORDER BY interval_days ASC
        LIMIT 3
    ''').fetchall()
    
    fungicides = db.execute('''
        SELECT * FROM pesticide_master 
        WHERE type = 'fungicide'
        ORDER BY interval_days ASC
        LIMIT 3
    ''').fetchall()
    
    insecticide_rec = None
    fungicide_rec = None
    
    if insecticides:
        recommended = dict(insecticides[0])
        insecticide_rec = {
            "recommendation": recommended['name'],
            "reason": "汎用殺虫剤推奨（マスタデータ不足）",
            "interval_days": recommended['interval_days'],
            "pesticide_type": "insecticide",
            "confidence": "中",
            "status": "fallback"
        }
    else:
        insecticide_rec = get_no_pesticide_recommendation("insecticide")
    
    if fungicides:
        recommended = dict(fungicides[0])
        fungicide_rec = {
            "recommendation": recommended['name'],
            "reason": "汎用殺菌剤推奨（マスタデータ不足）",
            "interval_days": recommended['interval_days'],
            "pesticide_type": "fungicide",
            "confidence": "中",
            "status": "fallback"
        }
    else:
        fungicide_rec = get_no_pesticide_recommendation("fungicide")
    
    return {
        "insecticide": insecticide_rec,
        "fungicide": fungicide_rec,
        "general_info": {
            "season_advice": f"現在は{current_season}です。",
            "analysis": history_analysis
        }
    }

def get_fallback_recommendation(db, current_season, history_analysis, latest_log):
    """フォールバック推奨（後方互換性のため残存）"""
    separated_result = get_fallback_recommendation_separated(db, current_season, history_analysis, latest_log)
    
    # 従来の形式に変換（殺虫剤を優先）
    if separated_result["insecticide"]["status"] != "no_need":
        result = separated_result["insecticide"].copy()
    elif separated_result["fungicide"]["status"] != "no_need":
        result = separated_result["fungicide"].copy()
    else:
        result = {
            "recommendation": "オルトラン",
            "reason": "システムフォールバック",
            "interval_days": 14,
            "confidence": "低"
        }
    
    # 全般情報を追加
    result.update({
        "season_advice": separated_result["general_info"]["season_advice"],
        "analysis": separated_result["general_info"]["analysis"]
    })
    
    return result

@bp.route('/recommendation/<int:bonsai_id>', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def recommend(bonsai_id):
    db = get_db(current_app)
    
    # まず、この盆栽が存在するか、そして誰のものかを確認
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    if not bonsai:
        return jsonify({"error": "指定された盆栽が見つかりません"}), 404
    
    # リクエストにユーザーIDが含まれていれば、所有権をチェック
    user_id = request.args.get('user_id')
    if user_id and int(user_id) != bonsai['user_id']:
        return jsonify({"error": "この盆栽の情報にアクセスする権限がありません"}), 403
    
    # 最新の農薬記録を取得
    latest = db.execute(
        'SELECT * FROM pesticide_logs WHERE bonsai_id = ? ORDER BY date DESC LIMIT 1',
        (bonsai_id,)
    ).fetchone()
    
    # インテリジェントな推奨を取得
    result = get_intelligent_recommendation(db, bonsai, latest)
    
    return jsonify(result)

@bp.route('/recommendations/user/<int:user_id>', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def user_recommendations(user_id):
    """ユーザーのすべての盆栽の農薬推奨情報を取得"""
    db = get_db(current_app)
    
    # ユーザーの盆栽を取得
    bonsai_list = db.execute(
        'SELECT * FROM bonsai WHERE user_id = ?', 
        (user_id,)
    ).fetchall()
    
    if not bonsai_list:
        return jsonify([])
    
    recommendations = []
    
    for bonsai in bonsai_list:
        # 各盆栽について最新の農薬記録を取得
        latest = db.execute(
            'SELECT * FROM pesticide_logs WHERE bonsai_id = ? ORDER BY date DESC LIMIT 1',
            (bonsai['id'],)
        ).fetchone()
        
        # 推奨情報を取得
        recommendation_detail = get_intelligent_recommendation(db, bonsai, latest)
        
        # レスポンス用の情報を整理
        recommendation_info = {
            "bonsai_id": bonsai['id'],
            "bonsai_name": bonsai['name'],
            "species": bonsai['species'],
            "species_id": bonsai['species_id'],
            "recommendation": recommendation_detail.get("recommendation"),
            "reason": recommendation_detail.get("reason"),
            "confidence": recommendation_detail.get("confidence"),
            "days_since_last": recommendation_detail.get("days_since_last"),
            "season_advice": recommendation_detail.get("season_advice")
        }
        
        if "warning" in recommendation_detail:
            recommendation_info["warning"] = recommendation_detail["warning"]
        
        recommendations.append(recommendation_info)
    
    return jsonify(recommendations)

@bp.route('/species/<int:species_id>/pesticides', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def get_species_pesticides(species_id):
    """特定の樹種に推奨される農薬リストを取得"""
    db = get_db(current_app)
    
    # 樹種の害虫・病気リスクを取得
    species_risks = get_species_pest_disease_risks(db, species_id)
    
    if not species_risks:
        return jsonify({
            "species_id": species_id,
            "primary_pesticides": [],
            "fungicides": [],
            "current_season": get_current_season(),
            "message": "この樹種のデータが見つかりません"
        })
    
    # 対象の害虫・病気IDを抽出
    target_pest_disease_ids = [r['pest_disease_id'] for r in species_risks]
    
    # 効果的な農薬を取得
    effective_pesticides = get_effective_pesticides(db, target_pest_disease_ids, get_current_season())
    
    # タイプ別に分類
    primary_pesticides = [p for p in effective_pesticides if p['pesticide_type'] == 'insecticide']
    fungicides = [p for p in effective_pesticides if p['pesticide_type'] == 'fungicide']
    
    # 禁止薬剤情報を取得
    prohibited = get_prohibited_pesticides(db, species_id)
    
    return jsonify({
        "species_id": species_id,
        "primary_pesticides": primary_pesticides[:5],  # 上位5つ
        "fungicides": fungicides[:5],  # 上位5つ
        "prohibited_pesticides": prohibited,
        "species_risks": species_risks,
        "current_season": get_current_season()
    })

@bp.route('/api-info', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def api_info():
    """改善されたAPIの情報と使用例を提供"""
    return jsonify({
        "title": "盆栽農薬推奨システム API v4.0",
        "description": "月ベース管理対応の高度な農薬推奨システム",
        "features": [
            "SQLiteマスタテーブルベース",
            "月別害虫・病気リスク評価",
            "農薬効果レベル判定",
            "樹種別禁止薬剤管理",
            "インテリジェントローテーション",
            "使用履歴分析",
            "月範囲による精密管理"
        ],
        "endpoints": {
            "個別推奨": "/api/pesticides/recommendation/{bonsai_id}?user_id={user_id}",
            "ユーザー全体推奨": "/api/pesticides/recommendations/user/{user_id}",
            "樹種別農薬情報": "/api/pesticides/species/{species_id}/pesticides",
            "月次リスク分析": "/api/pesticides/monthly-risks/{bonsai_id}?user_id={user_id}"
        },
        "current_season": get_current_season()
    })

# 後方互換性のための旧エンドポイント
@bp.route('/test-recommendation/<int:species_id>', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def test_recommendation(species_id):
    """テスト用推奨エンドポイント"""
    db = get_db(current_app)
    current_season = get_current_season()
    
    # サンプル盆栽オブジェクトを作成
    fake_bonsai = {
        'id': 999,
        'species_id': species_id,
        'name': 'テスト盆栽'
    }
    
    recommendation = get_intelligent_recommendation(db, fake_bonsai, None)
    return jsonify(recommendation)

@bp.route('/monthly-risks/<int:bonsai_id>', methods=['GET'])
def get_monthly_risks(bonsai_id):
    """当月・翌月の害虫・病気リスクと推奨農薬を取得（月ベース対応）"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    db = get_db(current_app)
    
    # 盆栽情報と所有者確認
    bonsai = db.execute(
        'SELECT * FROM bonsai WHERE id = ? AND user_id = ?', 
        (bonsai_id, user_id)
    ).fetchone()
    
    if not bonsai:
        return jsonify({"error": "盆栽が見つからないか、アクセス権限がありません"}), 404
    
    today = datetime.now()
    current_month = today.month
    next_month = (current_month % 12) + 1
    
    # 履歴分析
    history_analysis = analyze_pesticide_history(db, bonsai_id, days_back=90)
    
    # 最近の農薬使用記録
    latest_log = db.execute(
        'SELECT * FROM pesticide_logs WHERE bonsai_id = ? ORDER BY date DESC LIMIT 1',
        (bonsai_id,)
    ).fetchone()
    
    # 月次リスクを取得
    monthly_risks = get_monthly_risks_for_month(db, bonsai['species_id'], current_month)
    
    # 効果的な農薬の取得（ローテーション考慮）
    def get_recommendations_for_risks(risks):
        if not risks:
            return []
        
        pest_disease_ids = [risk['pest_disease_id'] for risk in risks]
        effective_pesticides = get_effective_pesticides(db, pest_disease_ids, get_current_season())
        filtered_pesticides = filter_by_season_and_prohibition(
            effective_pesticides, bonsai['species_id'], db, get_current_season()
        )
        
        # ローテーションロジック適用
        rotated_pesticides = apply_rotation_logic(
            filtered_pesticides, history_analysis, 
            dict(latest_log) if latest_log else None
        )
        
        return rotated_pesticides[:5] if rotated_pesticides else []  # 上位5つまで
    
    current_recommendations = get_recommendations_for_risks(monthly_risks)
    
    return jsonify({
        "bonsai": {
            "id": bonsai['id'],
            "name": bonsai['name'],
            "species": bonsai['species'],
            "species_id": bonsai['species_id']
        },
        "current_month": {
            "month": current_month,
            "season": get_month_season(current_month),
            "risks": monthly_risks,
            "recommendations": current_recommendations
        },
        "next_month": {
            "month": next_month,
            "season": get_month_season(next_month),
            "risks": get_monthly_risks_for_month(db, bonsai['species_id'], next_month),
            "recommendations": get_recommendations_for_risks(get_monthly_risks_for_month(db, bonsai['species_id'], next_month))
        },
        "history_analysis": history_analysis,
        "disclaimer": {
            "combination_warning": "この組み合わせは参考であり、科学的な正しさに裏付けされたものではありません。",
            "concentration_warning": "希釈濃度はメーカーの説明書をよく読んで、ご自身で判断してください。"
        }
    })

@bp.route('/enhanced-log', methods=['POST'])
def add_enhanced_log():
    """詳細な農薬使用記録を追加"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    data = request.json
    if not data:
        return jsonify({"error": "データが必要です"}), 400
    
    # 必須フィールドの確認
    required_fields = ['bonsai_id', 'pesticide_name', 'usage_date']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field}が必要です"}), 400
    
    db = get_db(current_app)
    
    # 盆栽の所有者確認
    bonsai = db.execute(
        'SELECT * FROM bonsai WHERE id = ? AND user_id = ?',
        (data['bonsai_id'], user_id)
    ).fetchone()
    
    if not bonsai:
        return jsonify({"error": "盆栽が見つからないか、アクセス権限がありません"}), 404
    
    try:
        # 詳細記録をpesticide_logsテーブルに保存（user_idを追加）
        db.execute('''
            INSERT INTO pesticide_logs 
            (bonsai_id, user_id, pesticide_name, date, dosage, notes, 
             water_amount, dilution_ratio, actual_usage_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['bonsai_id'],
            user_id,  # user_idを追加
            data['pesticide_name'],
            data['usage_date'],
            data.get('dosage', ''),
            data.get('notes', ''),
            data.get('water_amount', ''),
            data.get('dilution_ratio', ''),
            data.get('actual_usage_amount', '')
        ))
        
        db.commit()
        log_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        return jsonify({
            "message": "農薬記録を追加しました",
            "log_id": log_id
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"記録の追加に失敗しました: {str(e)}"}), 500

# @bp.route('/recommendation/<int:bonsai_id>', methods=['GET'])
# def get_recommendation_for_bonsai(bonsai_id):
#     """農薬記録を考慮した推奨農薬情報を取得"""
#     user_id = request.args.get('user_id')
#     if not user_id:
#         return jsonify({"error": "ユーザーIDが必要です"}), 400
    
#     db = get_db(current_app)
    
#     # 盆栽の所有者確認
#     bonsai = db.execute(
#         'SELECT * FROM bonsai WHERE id = ? AND user_id = ?',
#         (bonsai_id, user_id)
#     ).fetchone()
    
#     if not bonsai:
#         return jsonify({"error": "盆栽が見つからないか、アクセス権限がありません"}), 404
    
#     # 現在の月を取得
#     current_month = datetime.now().month
    
#     # 最近の農薬使用記録を取得（過去30日分）
#     recent_logs = db.execute('''
#         SELECT pesticide_name, date, 
#                julianday('now') - julianday(date) as days_ago
#         FROM pesticide_logs 
#         WHERE bonsai_id = ? AND date >= date('now', '-30 days')
#         ORDER BY date DESC
#     ''', (bonsai_id,)).fetchall()
    
#     # 月次リスクを取得
#     monthly_risks = get_monthly_risks_for_month(db, bonsai['species_id'], current_month)
    
#     if not monthly_risks:
#         return jsonify({
#             "recommendation": "特に推奨する農薬はありません",
#             "reason": "現在の時期には特定の害虫・病気のリスクは低いです",
#             "confidence": "中",
#             "warning": "定期的な観察は継続してください"
#         })
    
#     # 最も効果的な農薬を見つける
#     best_pesticide = None
#     best_score = 0
#     target_pests = []
    
#     for risk in monthly_risks:
#         target_pests.append(risk['pest_disease_name'])
        
#         # この害虫・病気に対する推奨農薬を取得
#         recommended_pesticides = db.execute('''
#             SELECT pm.name, pm.type, pm.description, 
#                    avg(pe.effectiveness_level) as avg_effectiveness
#             FROM pesticide_master pm
#             LEFT JOIN pesticide_effectiveness pe ON pm.id = pe.pesticide_id
#             WHERE pe.pest_disease_id = ?
#             GROUP BY pm.id, pm.name, pm.type, pm.description
#             ORDER BY avg_effectiveness DESC
#         ''', (risk['pest_disease_id'],)).fetchall()
        
#         for pesticide in recommended_pesticides:
#             # スコア計算: 効果 * リスクレベル - 最近の使用頻度
#             recent_usage = len([log for log in recent_logs if log['pesticide_name'] == pesticide['name']])
#             freshness_penalty = recent_usage * 0.2  # 最近使った農薬はスコアダウン
            
#             score = (pesticide['avg_effectiveness'] or 3) * risk['occurrence_probability'] - freshness_penalty
            
#             if score > best_score:
#                 best_score = score
#                 best_pesticide = pesticide
    
#     if not best_pesticide:
#         return jsonify({
#             "recommendation": "汎用農薬を使用してください",
#             "reason": "具体的な推奨農薬データがありません",
#             "confidence": "低",
#             "warning": "専門家にご相談ください"
#         })
    
#     # 信頼度の計算
#     confidence = "高" if best_score > 8 else "中" if best_score > 5 else "低"
    
#     # 最後の散布からの日数
#     last_pesticide_log = recent_logs[0] if recent_logs else None
#     days_since_last = int(last_pesticide_log['days_ago']) if last_pesticide_log else None
    
#     # 散布間隔の推奨
#     interval_days = 7 if best_pesticide['type'] == 'insecticide' else 10
    
#     # 次回推奨日
#     next_application_date = None
#     if last_pesticide_log:
#         next_date = datetime.now() + timedelta(days=interval_days - int(last_pesticide_log['days_ago']))
#         if next_date > datetime.now():
#             next_application_date = next_date.strftime('%Y-%m-%d')
#     else:
#         next_application_date = datetime.now().strftime('%Y-%m-%d')
    
#     # 警告メッセージ
#     warning = None
#     if days_since_last is not None and days_since_last < 3:
#         warning = f"前回散布から{days_since_last}日しか経過していません。間隔を空けてください。"
#     elif len(set(log['pesticide_name'] for log in recent_logs[:3])) == 1:
#         warning = "同じ農薬を連続使用しています。薬剤抵抗性を避けるため、異なる系統の農薬も検討してください。"
    
#     return jsonify({
#         "recommendation": best_pesticide['name'],
#         "pesticide_type": best_pesticide['type'],
#         "reason": f"現在の時期の主要リスク（{', '.join(target_pests[:2])}）に効果的です",
#         "confidence": confidence,
#         "effectiveness": best_pesticide['avg_effectiveness'] or 3,
#         "target_pests": target_pests[:3],
#         "days_since_last": days_since_last,
#         "interval_days": interval_days,
#         "next_application_date": next_application_date,
#         "warning": warning
#     })
