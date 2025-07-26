from flask import Blueprint, request, jsonify, current_app
from ..db import get_db

bp = Blueprint('work_log', __name__, url_prefix='/api/work-logs')

# 作業種別のリスト
WORK_TYPES = [
    '剪定',
    '植え替え', 
    '針金掛け',
    '針金外し',
    '水やり',
    '肥料',
    '植え替え準備',
    'その他'
]

@bp.route('/work-types', methods=['GET'])
def get_work_types():
    """作業種別のリストを取得"""
    return jsonify(WORK_TYPES)

@bp.route('/<int:bonsai_id>', methods=['GET'])
def get_work_logs(bonsai_id):
    """指定された盆栽の作業記録を取得"""
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
        'SELECT * FROM work_logs WHERE bonsai_id = ? ORDER BY date DESC',
        (bonsai_id,)
    ).fetchall()
    
    # データを整形
    logs_list = []
    for log in logs:
        log_dict = dict(log)
        logs_list.append(log_dict)
    
    return jsonify(logs_list)

@bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_work_logs(user_id):
    """特定ユーザーのすべての盆栽の作業記録を取得"""
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
        SELECT wl.*, b.name as bonsai_name
        FROM work_logs wl
        JOIN bonsai b ON wl.bonsai_id = b.id
        WHERE wl.bonsai_id IN ({placeholders})
        ORDER BY wl.date DESC
        ''',
        bonsai_id_list
    ).fetchall()
    
    # データを整形
    logs_list = []
    for log in logs:
        log_dict = dict(log)
        logs_list.append(log_dict)
    
    return jsonify(logs_list)

@bp.route('/<int:bonsai_id>', methods=['POST'])
def add_work_log(bonsai_id):
    """作業記録を追加"""
    data = request.get_json()
    db = get_db(current_app)
    
    # 必要なフィールドの確認
    if not data or not data.get('date') or not data.get('work_type'):
        return jsonify({"error": "日付と作業種別は必須です"}), 400
    
    # 作業種別の検証
    if data['work_type'] not in WORK_TYPES:
        return jsonify({"error": "無効な作業種別です"}), 400
    
    # 盆栽の存在確認と所有権チェック
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    if not bonsai:
        return jsonify({"error": "指定された盆栽が見つかりません"}), 404
    
    user_id = data.get('user_id')
    if not user_id or int(user_id) != bonsai['user_id']:
        return jsonify({"error": "この盆栽に記録を追加する権限がありません"}), 403
    
    try:
        # 作業記録をデータベースに追加
        cursor = db.execute('''
            INSERT INTO work_logs (bonsai_id, user_id, date, work_type, description, notes, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            bonsai_id,
            user_id,
            data['date'],
            data['work_type'],
            data.get('description', ''),
            data.get('notes', ''),
            data.get('duration')
        ))
        
        db.commit()
        
        # 追加された記録のIDを取得
        new_log_id = cursor.lastrowid
        
        # 追加された記録を取得して返す
        new_log = db.execute('SELECT * FROM work_logs WHERE id = ?', (new_log_id,)).fetchone()
        
        return jsonify({
            "success": True,
            "message": "作業記録が追加されました",
            "log": dict(new_log)
        }), 201
        
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"作業記録追加エラー: {str(e)}")
        return jsonify({"error": "作業記録の追加に失敗しました"}), 500

@bp.route('/log/<int:log_id>', methods=['DELETE'])
def remove_work_log(log_id):
    """作業記録を削除"""
    db = get_db(current_app)
    
    # 記録の存在確認
    log = db.execute('SELECT * FROM work_logs WHERE id = ?', (log_id,)).fetchone()
    if not log:
        return jsonify({"error": "指定された作業記録が見つかりません"}), 404
    
    # ユーザーIDの確認（リクエストから取得）
    user_id = request.args.get('user_id')
    if not user_id or int(user_id) != log['user_id']:
        return jsonify({"error": "この作業記録を削除する権限がありません"}), 403
    
    try:
        # 記録を削除
        db.execute('DELETE FROM work_logs WHERE id = ?', (log_id,))
        db.commit()
        
        return jsonify({
            "success": True,
            "message": "作業記録が削除されました"
        }), 200
        
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"作業記録削除エラー: {str(e)}")
        return jsonify({"error": "作業記録の削除に失敗しました"}), 500 