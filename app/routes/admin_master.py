from flask import Blueprint, request, jsonify, current_app
from ..db import get_db
from functools import wraps

bp = Blueprint('admin_master', __name__, url_prefix='/api/admin/master')

def admin_required(f):
    """管理者権限が必要なエンドポイントのデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # リクエストメソッドに応じてuser_idを取得
        user_id = None
        
        if request.method in ['GET', 'DELETE']:
            # GET、DELETEはクエリパラメータから取得
            user_id = request.args.get('user_id')
        elif request.method in ['POST', 'PUT']:
            # POST、PUTはJSONボディから取得（フォールバックでクエリパラメータも確認）
            if request.is_json and request.json:
                user_id = request.json.get('user_id')
            # クエリパラメータからも取得を試行
            if not user_id:
                user_id = request.args.get('user_id')
        
        if not user_id:
            current_app.logger.warning(f"Missing user_id in {request.method} request to {request.path}")
            return jsonify({"error": "ユーザーIDが必要です"}), 401
        
        db = get_db(current_app)
        user = db.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user or user['role'] != 'admin':
            current_app.logger.warning(f"Unauthorized access attempt by user_id {user_id}")
            return jsonify({"error": "管理者権限が必要です"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ========== 農薬マスタ管理 ==========

@bp.route('/pesticides', methods=['GET'])
@admin_required
def get_pesticides():
    """農薬マスタの一覧取得"""
    db = get_db(current_app)
    pesticides = db.execute('SELECT * FROM pesticide_master ORDER BY name').fetchall()
    return jsonify([dict(p) for p in pesticides])

@bp.route('/pesticides', methods=['POST'])
@admin_required
def add_pesticide():
    """農薬マスタに新規追加"""
    data = request.json
    db = get_db(current_app)
    
    try:
        db.execute('''
            INSERT INTO pesticide_master (name, type, interval_days, active_ingredient, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['name'], data['type'], data['interval_days'], 
              data.get('active_ingredient', ''), data.get('description', '')))
        db.commit()
        
        return jsonify({"message": "農薬を追加しました", "name": data['name']}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/pesticides/<int:pesticide_id>', methods=['PUT'])
@admin_required
def update_pesticide(pesticide_id):
    """農薬マスタの更新"""
    data = request.json
    db = get_db(current_app)
    
    try:
        db.execute('''
            UPDATE pesticide_master 
            SET name = ?, type = ?, interval_days = ?, active_ingredient = ?, description = ?
            WHERE id = ?
        ''', (data['name'], data['type'], data['interval_days'], 
              data.get('active_ingredient', ''), data.get('description', ''), pesticide_id))
        db.commit()
        
        return jsonify({"message": "農薬を更新しました"})
    except Exception as e:
        return jsonify({"error": f"更新に失敗しました: {str(e)}"}), 400

@bp.route('/pesticides/<int:pesticide_id>', methods=['DELETE'])
@admin_required
def delete_pesticide(pesticide_id):
    """農薬マスタの削除"""
    db = get_db(current_app)
    
    try:
        # 関連データの存在確認
        related_effectiveness = db.execute(
            'SELECT COUNT(*) as count FROM pesticide_effectiveness WHERE pesticide_id = ?',
            (pesticide_id,)
        ).fetchone()
        
        related_prohibited = db.execute(
            'SELECT COUNT(*) as count FROM species_prohibited_pesticides WHERE pesticide_id = ?',
            (pesticide_id,)
        ).fetchone()
        
        if related_effectiveness['count'] > 0 or related_prohibited['count'] > 0:
            return jsonify({"error": "関連データが存在するため削除できません"}), 400
        
        db.execute('DELETE FROM pesticide_master WHERE id = ?', (pesticide_id,))
        db.commit()
        
        return jsonify({"message": "農薬を削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== 害虫・病気マスタ管理 ==========

@bp.route('/pest-diseases', methods=['GET'])
@admin_required
def get_pest_diseases():
    """害虫・病気マスタの一覧取得"""
    db = get_db(current_app)
    pest_diseases = db.execute('SELECT * FROM pest_disease_master ORDER BY type, name').fetchall()
    return jsonify([dict(pd) for pd in pest_diseases])

@bp.route('/pest-diseases', methods=['POST'])
@admin_required
def add_pest_disease():
    """害虫・病気マスタに新規追加（月ベース対応）"""
    data = request.json
    db = get_db(current_app)
    
    try:
        # 月ベースデータを優先、季節データは互換性のため保持
        start_month = data.get('start_month', 1)
        end_month = data.get('end_month', 12)
        season = data.get('season', '通年')  # 互換性のため残す
        
        db.execute('''
            INSERT INTO pest_disease_master (name, type, description, season, start_month, end_month)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['type'], data.get('description', ''), season, start_month, end_month))
        db.commit()
        
        return jsonify({"message": "害虫・病気を追加しました", "name": data['name']}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/pest-diseases/<int:pest_disease_id>', methods=['DELETE'])
@admin_required
def delete_pest_disease(pest_disease_id):
    """害虫・病気マスタの削除"""
    db = get_db(current_app)
    
    try:
        # 関連データの存在確認
        related_effectiveness = db.execute(
            'SELECT COUNT(*) as count FROM pesticide_effectiveness WHERE pest_disease_id = ?',
            (pest_disease_id,)
        ).fetchone()
        
        related_species = db.execute(
            'SELECT COUNT(*) as count FROM species_pest_disease WHERE pest_disease_id = ?',
            (pest_disease_id,)
        ).fetchone()
        
        if related_effectiveness['count'] > 0 or related_species['count'] > 0:
            return jsonify({"error": "関連データが存在するため削除できません"}), 400
        
        db.execute('DELETE FROM pest_disease_master WHERE id = ?', (pest_disease_id,))
        db.commit()
        
        return jsonify({"message": "害虫・病気を削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== 農薬効果マスタ管理 ==========

@bp.route('/pesticide-effectiveness', methods=['GET'])
@admin_required
def get_pesticide_effectiveness():
    """農薬効果マスタの一覧取得"""
    db = get_db(current_app)
    effectiveness = db.execute('''
        SELECT pe.*, pm.name as pesticide_name, pdm.name as pest_disease_name
        FROM pesticide_effectiveness pe
        JOIN pesticide_master pm ON pe.pesticide_id = pm.id
        JOIN pest_disease_master pdm ON pe.pest_disease_id = pdm.id
        ORDER BY pm.name, pdm.name
    ''').fetchall()
    return jsonify([dict(e) for e in effectiveness])

@bp.route('/pesticide-effectiveness', methods=['POST'])
@admin_required
def add_pesticide_effectiveness():
    """農薬効果マスタに新規追加"""
    data = request.json
    db = get_db(current_app)
    
    try:
        db.execute('''
            INSERT OR REPLACE INTO pesticide_effectiveness 
            (pesticide_id, pest_disease_id, effectiveness_level, notes)
            VALUES (?, ?, ?, ?)
        ''', (data['pesticide_id'], data['pest_disease_id'], 
              data['effectiveness_level'], data.get('notes', '')))
        db.commit()
        
        return jsonify({"message": "農薬効果を追加しました"}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/pesticide-effectiveness/<int:effectiveness_id>', methods=['DELETE'])
@admin_required
def delete_pesticide_effectiveness(effectiveness_id):
    """農薬効果マスタの削除"""
    db = get_db(current_app)
    
    try:
        db.execute('DELETE FROM pesticide_effectiveness WHERE id = ?', (effectiveness_id,))
        db.commit()
        
        return jsonify({"message": "農薬効果を削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== 樹種マスタ管理 ==========

@bp.route('/species', methods=['GET'])
@admin_required
def get_species():
    """樹種マスタの一覧取得"""
    db = get_db(current_app)
    species = db.execute('SELECT * FROM species_master ORDER BY name').fetchall()
    return jsonify([dict(s) for s in species])

@bp.route('/species', methods=['POST'])
@admin_required
def add_species():
    """樹種マスタに新規追加"""
    data = request.json
    db = get_db(current_app)
    
    try:
        db.execute('''
            INSERT INTO species_master (name, scientific_name, category, description, care_notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['name'], data.get('scientific_name', ''), data.get('category', '針葉樹'), 
              data.get('description', ''), data.get('care_notes', '')))
        db.commit()
        
        return jsonify({"message": "樹種を追加しました", "name": data['name']}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/species/<int:species_id>', methods=['DELETE'])
@admin_required
def delete_species(species_id):
    """樹種マスタの削除"""
    db = get_db(current_app)
    
    try:
        # 関連データの存在確認
        related_bonsai = db.execute(
            'SELECT COUNT(*) as count FROM bonsai WHERE species_id = ?',
            (species_id,)
        ).fetchone()
        
        related_risks = db.execute(
            'SELECT COUNT(*) as count FROM species_pest_disease WHERE species_id = ?',
            (species_id,)
        ).fetchone()
        
        related_prohibited = db.execute(
            'SELECT COUNT(*) as count FROM species_prohibited_pesticides WHERE species_id = ?',
            (species_id,)
        ).fetchone()
        
        if related_bonsai['count'] > 0 or related_risks['count'] > 0 or related_prohibited['count'] > 0:
            return jsonify({"error": "関連データが存在するため削除できません"}), 400
        
        db.execute('DELETE FROM species_master WHERE id = ?', (species_id,))
        db.commit()
        
        return jsonify({"message": "樹種を削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== 樹種別リスク管理 ==========

@bp.route('/species-pest-diseases', methods=['GET'])
@admin_required
def get_species_pest_diseases():
    """樹種別リスクの一覧取得"""
    db = get_db(current_app)
    species_risks = db.execute('''
        SELECT spd.*, sm.name as species_name, pdm.name as pest_disease_name, pdm.type as pest_disease_type
        FROM species_pest_disease spd
        JOIN species_master sm ON spd.species_id = sm.id
        JOIN pest_disease_master pdm ON spd.pest_disease_id = pdm.id
        ORDER BY sm.name, pdm.name
    ''').fetchall()
    return jsonify([dict(sr) for sr in species_risks])

@bp.route('/species-pest-diseases', methods=['POST'])
@admin_required
def add_species_pest_disease():
    """樹種別リスクに新規追加（月ベース対応）"""
    data = request.json
    db = get_db(current_app)
    
    try:
        # 月ベースデータを優先、季節データは互換性のため保持
        start_month = data.get('start_month', 1)
        end_month = data.get('end_month', 12)
        season = data.get('season', '通年')  # 互換性のため残す
        
        db.execute('''
            INSERT OR REPLACE INTO species_pest_disease 
            (species_id, pest_disease_id, occurrence_probability, season, start_month, end_month, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['species_id'], data['pest_disease_id'], data['occurrence_probability'], 
              season, start_month, end_month, data.get('notes', '')))
        db.commit()
        
        return jsonify({"message": "樹種別リスクを追加しました"}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/species-pest-diseases/<int:species_risk_id>', methods=['DELETE'])
@admin_required
def delete_species_pest_disease(species_risk_id):
    """樹種別リスクの削除"""
    db = get_db(current_app)
    
    try:
        db.execute('DELETE FROM species_pest_disease WHERE id = ?', (species_risk_id,))
        db.commit()
        
        return jsonify({"message": "樹種別リスクを削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== 樹種別NG薬剤管理 ==========

@bp.route('/species-prohibited-pesticides', methods=['GET'])
@admin_required
def get_species_prohibited_pesticides():
    """樹種別NG薬剤の一覧取得"""
    db = get_db(current_app)
    prohibited = db.execute('''
        SELECT spp.*, sm.name as species_name, pm.name as pesticide_name
        FROM species_prohibited_pesticides spp
        JOIN species_master sm ON spp.species_id = sm.id
        JOIN pesticide_master pm ON spp.pesticide_id = pm.id
        ORDER BY sm.name, pm.name
    ''').fetchall()
    return jsonify([dict(p) for p in prohibited])

@bp.route('/species-prohibited-pesticides', methods=['POST'])
@admin_required
def add_species_prohibited_pesticide():
    """樹種別NG薬剤に新規追加"""
    data = request.json
    db = get_db(current_app)
    
    try:
        db.execute('''
            INSERT OR REPLACE INTO species_prohibited_pesticides 
            (species_id, pesticide_id, reason, severity, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['species_id'], data['pesticide_id'], data.get('reason', ''), 
              data.get('severity', 'warning'), data.get('notes', '')))
        db.commit()
        
        return jsonify({"message": "樹種別NG薬剤を追加しました"}), 201
    except Exception as e:
        return jsonify({"error": f"追加に失敗しました: {str(e)}"}), 400

@bp.route('/species-prohibited-pesticides/<int:prohibited_id>', methods=['DELETE'])
@admin_required
def delete_species_prohibited_pesticide(prohibited_id):
    """樹種別NG薬剤の削除"""
    db = get_db(current_app)
    
    try:
        db.execute('DELETE FROM species_prohibited_pesticides WHERE id = ?', (prohibited_id,))
        db.commit()
        
        return jsonify({"message": "樹種別NG薬剤を削除しました"})
    except Exception as e:
        return jsonify({"error": f"削除に失敗しました: {str(e)}"}), 400

# ========== サマリー情報 ==========

@bp.route('/summary', methods=['GET'])
@admin_required
def get_master_summary():
    """マスタデータのサマリー情報を取得"""
    db = get_db(current_app)
    
    summary = {}
    summary['species_count'] = db.execute('SELECT COUNT(*) as count FROM species_master').fetchone()['count']
    summary['pesticides_count'] = db.execute('SELECT COUNT(*) as count FROM pesticide_master').fetchone()['count']
    summary['pest_diseases_count'] = db.execute('SELECT COUNT(*) as count FROM pest_disease_master').fetchone()['count']
    summary['effectiveness_count'] = db.execute('SELECT COUNT(*) as count FROM pesticide_effectiveness').fetchone()['count']
    summary['species_risks_count'] = db.execute('SELECT COUNT(*) as count FROM species_pest_disease').fetchone()['count']
    summary['prohibited_count'] = db.execute('SELECT COUNT(*) as count FROM species_prohibited_pesticides').fetchone()['count']
    
    return jsonify(summary) 