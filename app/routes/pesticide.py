from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from ..db import get_db
from .recommend import get_current_season

bp = Blueprint('pesticide', __name__, url_prefix='/api/pesticides')

# 定義済みの農薬リスト（必要に応じて拡張）
PESTICIDE_LIST = [
    {"id": 1, "name": "オルトラン", "description": "浸透移行性の殺虫剤", "default_dosage": "1g/L", "type": "殺虫剤"},
    {"id": 2, "name": "スミチオン", "description": "有機リン系殺虫剤", "default_dosage": "2ml/L", "type": "殺虫剤"},
    {"id": 3, "name": "ベニカ", "description": "殺虫殺菌剤", "default_dosage": "3ml/L", "type": "殺虫殺菌剤"},
    {"id": 4, "name": "マラソン", "description": "有機リン系殺虫剤", "default_dosage": "2ml/L", "type": "殺虫剤"},
    {"id": 5, "name": "カダン", "description": "浸透移行性の殺虫剤", "default_dosage": "5ml/L", "type": "殺虫剤"},
    {"id": 6, "name": "トップジンM", "description": "殺菌剤", "default_dosage": "1g/L", "type": "殺菌剤"},
    {"id": 7, "name": "石灰硫黄合剤", "description": "殺菌・殺虫剤", "default_dosage": "20ml/L", "type": "殺菌殺虫剤"},
    {"id": 8, "name": "ダコニール", "description": "殺菌剤", "default_dosage": "2ml/L", "type": "殺菌剤"},
    {"id": 9, "name": "バロック", "description": "殺虫剤", "default_dosage": "1ml/L", "type": "殺虫剤"},
    {"id": 10, "name": "ダニ太郎", "description": "殺虫剤", "default_dosage": "1ml/L", "type": "殺虫剤"},
]

@bp.route('/list', methods=['GET'])
def get_pesticide_list():
    """登録されている農薬のリストを取得"""
    return jsonify(PESTICIDE_LIST)

@bp.route('/recommended', methods=['GET'])
def get_recommended_pesticides():
    """推奨農薬のリストを取得（マスタテーブルから）"""
    db = get_db(current_app)
    
    # マスタテーブルから推奨農薬を取得
    pesticides = db.execute('''
        SELECT name, interval_days, type, description, active_ingredient
        FROM pesticide_master 
        ORDER BY type, interval_days ASC
    ''').fetchall()
    
    recommended = []
    for pesticide in pesticides:
        # PESTICIDE_LISTから該当する農薬の詳細情報を検索（フォールバック用）
        pesticide_details = next((p for p in PESTICIDE_LIST if p["name"] == pesticide["name"]), None)
    
        if pesticide_details:
            recommended.append({
                **pesticide_details,
                "interval_days": pesticide["interval_days"],
                "pesticide_type": pesticide["type"],
                "active_ingredient": pesticide["active_ingredient"]
            })
        else:
            # マスタテーブルからの情報のみで構成
            recommended.append({
                "name": pesticide["name"],
                "description": pesticide["description"] or "農薬",
                "default_dosage": "使用量は製品ラベルを参照",
                "type": pesticide["type"],
                "interval_days": pesticide["interval_days"],
                "pesticide_type": pesticide["type"],
                "active_ingredient": pesticide["active_ingredient"]
            })
    
    return jsonify(recommended)

@bp.route('/recommended/species/<int:species_id>', methods=['GET'])
@cross_origin(origins=['https://bonsai.modur4.com', 'http://localhost:6173', 'http://localhost:6000'], 
              allow_headers=['Content-Type', 'Authorization'], 
              methods=['GET', 'OPTIONS'])
def get_species_recommended_pesticides(species_id):
    """特定の樹種に推奨される農薬の詳細リストを取得（マスタテーブルベース）"""
    db = get_db(current_app)
    
    # 樹種の害虫・病気リスクを取得
    species_risks = db.execute('''
        SELECT spd.*, pdm.name as pest_disease_name, pdm.type as pest_disease_type
        FROM species_pest_disease spd
        JOIN pest_disease_master pdm ON spd.pest_disease_id = pdm.id
        WHERE spd.species_id = ?
        ORDER BY spd.occurrence_probability DESC
    ''', (species_id,)).fetchall()
    
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
    
    if target_pest_disease_ids:
        placeholders = ','.join(['?'] * len(target_pest_disease_ids))
        pesticides = db.execute(f'''
            SELECT pe.*, pm.name as pesticide_name, pm.type as pesticide_type, 
                   pm.interval_days, pm.active_ingredient, pm.description,
                   AVG(pe.effectiveness_level) as avg_effectiveness
            FROM pesticide_effectiveness pe
            JOIN pesticide_master pm ON pe.pesticide_id = pm.id
            WHERE pe.pest_disease_id IN ({placeholders})
            GROUP BY pe.pesticide_id
            ORDER BY avg_effectiveness DESC, pm.interval_days ASC
        ''', target_pest_disease_ids).fetchall()
        
        # タイプ別に分類
        detailed_primary = []
        detailed_fungicides = []
        
        for pesticide in pesticides:
            # PESTICIDE_LISTから追加の詳細情報を取得
            details = next((p for p in PESTICIDE_LIST if p["name"] == pesticide["pesticide_name"]), None)
            
            pesticide_info = {
                "name": pesticide["pesticide_name"],
                "interval_days": pesticide["interval_days"],
                "effectiveness": round(pesticide["avg_effectiveness"], 1),
                "active_ingredient": pesticide["active_ingredient"],
                "description": pesticide["description"] or (details["description"] if details else ""),
                "default_dosage": details["default_dosage"] if details else "使用量は製品ラベルを参照",
                "type": pesticide["pesticide_type"]
            }
            
            if pesticide["pesticide_type"] == "insecticide":
                detailed_primary.append(pesticide_info)
            elif pesticide["pesticide_type"] == "fungicide":
                detailed_fungicides.append(pesticide_info)
    else:
        detailed_primary = []
        detailed_fungicides = []
    
    return jsonify({
        "species_id": species_id,
        "primary_pesticides": detailed_primary[:5],  # 上位5つ
        "fungicides": detailed_fungicides[:5],  # 上位5つ
        "species_risks": [dict(risk) for risk in species_risks],
        "current_season": get_current_season()
    })

@bp.route('/<int:bonsai_id>', methods=['GET'])
def get_logs(bonsai_id):
    db = get_db(current_app)
    
    # まず、この盆栽が存在するか、そして誰のものかを確認
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    if not bonsai:
        return jsonify({"error": "指定された盆栽が見つかりません"}), 404
    
    # リクエストにユーザーIDが含まれていれば、所有権をチェック
    user_id = request.args.get('user_id')
    if user_id and int(user_id) != bonsai['user_id']:
        return jsonify({"error": "この盆栽の記録にアクセスする権限がありません"}), 403
    
    logs = db.execute(
        'SELECT * FROM pesticide_logs WHERE bonsai_id = ? ORDER BY date DESC',
        (bonsai_id,)
    ).fetchall()
    
    # フロントエンドと一致するようにデータを整形
    logs_list = []
    for log in logs:
        log_dict = dict(log)
        # date フィールドはそのまま残す（フロントエンドでlog.dateを使用）
        # amountがある場合はdosageもセット（互換性のため）
        if 'amount' in log_dict and log_dict['amount']:
            log_dict['dosage'] = log_dict['amount']
        logs_list.append(log_dict)
    
    return jsonify(logs_list)


@bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_logs(user_id):
    """特定ユーザーのすべての盆栽の農薬記録を取得"""
    db = get_db(current_app)
    
    # ユーザーの盆栽IDを取得
    bonsai_ids = db.execute(
        'SELECT id FROM bonsai WHERE user_id = ?', 
        (user_id,)
    ).fetchall()
    
    if not bonsai_ids:
        return jsonify([])
    
    # リストに変換
    bonsai_id_list = [b['id'] for b in bonsai_ids]
    
    # IN句を使用してクエリを構築
    placeholders = ','.join(['?'] * len(bonsai_id_list))
    logs = db.execute(
        f'''
        SELECT pl.*, b.name as bonsai_name
        FROM pesticide_logs pl
        JOIN bonsai b ON pl.bonsai_id = b.id
        WHERE pl.bonsai_id IN ({placeholders})
        ORDER BY pl.date DESC
        ''',
        bonsai_id_list
    ).fetchall()
    
    # フロントエンドと一致するようにデータを整形
    logs_list = []
    for log in logs:
        log_dict = dict(log)
        # 全記録表示ではusage_dateフィールドを追加（フロントエンドの期待に合わせる）
        log_dict['usage_date'] = log_dict['date']
        # amountがある場合はdosageもセット（互換性のため）
        if 'amount' in log_dict and log_dict['amount']:
            log_dict['dosage'] = log_dict['amount']
        logs_list.append(log_dict)
    
    return jsonify(logs_list)

@bp.route('/<int:bonsai_id>', methods=['POST'])
def add_log(bonsai_id):
    data = request.json
    db = get_db(current_app)
    
    # まず、この盆栽が存在するか、そして誰のものかを確認
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    if not bonsai:
        return jsonify({"error": "指定された盆栽が見つかりません"}), 404
    
    # リクエストにユーザーIDが含まれていれば、所有権をチェック
    user_id = request.args.get('user_id')
    if user_id and int(user_id) != bonsai['user_id']:
        return jsonify({"error": "この盆栽に記録を追加する権限がありません"}), 403
    
    db.execute('''
        INSERT INTO pesticide_logs (bonsai_id, user_id, pesticide_name, date, amount, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (bonsai_id, bonsai['user_id'], data['pesticide_name'], data['usage_date'], data.get('dosage', ''), data.get('notes', '')))
    db.commit()
    
    # 新しく追加された記録のIDを取得
    new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    
    return jsonify({
        "message": "農薬記録を追加しました",
        "id": new_id
    })

@bp.route('/log/<int:log_id>', methods=['DELETE'])
def remove_log(log_id):
    """農薬記録を削除するエンドポイント"""
    db = get_db(current_app)
    
    # まず、この記録が存在するかを確認
    log = db.execute('SELECT * FROM pesticide_logs WHERE id = ?', (log_id,)).fetchone()
    if not log:
        return jsonify({"error": "指定された記録が見つかりません"}), 404
    
    # 記録に関連する盆栽の所有者を確認
    bonsai_id = log['bonsai_id']
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    
    # リクエストにユーザーIDが含まれていれば、所有権をチェック
    user_id = request.args.get('user_id')
    if user_id and int(user_id) != bonsai['user_id']:
        return jsonify({"error": "この記録を削除する権限がありません"}), 403
    
    # 記録を削除
    db.execute('DELETE FROM pesticide_logs WHERE id = ?', (log_id,))
    db.commit()
    
    return jsonify({
        "message": "農薬記録を削除しました",
        "id": log_id
    })