from flask import Blueprint, request, jsonify, current_app, send_from_directory
from ..db import get_db
import os
import time
import sqlite3
from werkzeug.utils import secure_filename
import uuid

bp = Blueprint('bonsai', __name__, url_prefix='/api/bonsai')

# 許可する拡張子のリスト
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/species', methods=['GET'])
def get_species_list():
    """盆栽の樹種リストをデータベースから取得するエンドポイント"""
    db = get_db(current_app)
    try:
        species = db.execute('SELECT id, name, scientific_name FROM species_master ORDER BY category, name').fetchall()
        # 辞書形式に変換して返す
        species_list = []
        for s in species:
            species_list.append({
                "id": s['id'],
                "name": s['name'],
                "scientific_name": s['scientific_name']
            })
        return jsonify(species_list)
    except Exception as e:
        # エラーが発生した場合は空のリストを返す
        return jsonify([])

@bp.route('', methods=['GET'])
def get_bonsai():
    db = get_db(current_app)
    # クエリパラメータからuser_idを取得
    user_id = request.args.get('user_id')
    
    if user_id:
        # 特定ユーザーの盆栽のみを取得
        bonsai = db.execute('SELECT * FROM bonsai WHERE user_id = ?', (user_id,)).fetchall()
    else:
        # すべての盆栽を取得（管理者用）
        bonsai = db.execute('SELECT * FROM bonsai').fetchall()
    
    # 盆栽の画像情報を取得
    result = []
    for b in bonsai:
        b_dict = dict(b)
        # 最新の画像を取得
        image = db.execute('SELECT * FROM bonsai_images WHERE bonsai_id = ? ORDER BY created_at DESC LIMIT 1', 
                        (b['id'],)).fetchone()
        b_dict['has_image'] = bool(image)
        if image:
            b_dict['image_id'] = image['id']
        result.append(b_dict)
    
    return jsonify(result)

@bp.route('/user/<int:user_id>', methods=['GET'])
def get_user_bonsai(user_id):
    """特定ユーザーの盆栽のみを取得するエンドポイント"""
    db = get_db(current_app)
    bonsai = db.execute('SELECT * FROM bonsai WHERE user_id = ?', (user_id,)).fetchall()
    
    # 盆栽の画像情報を取得
    result = []
    for b in bonsai:
        b_dict = dict(b)
        # 最新の画像を取得
        image = db.execute('SELECT * FROM bonsai_images WHERE bonsai_id = ? ORDER BY created_at DESC LIMIT 1', 
                        (b['id'],)).fetchone()
        b_dict['has_image'] = bool(image)
        if image:
            b_dict['image_id'] = image['id']
        result.append(b_dict)
    
    return jsonify(result)

@bp.route('', methods=['POST'])
def add_bonsai():
    data = request.json
    db = get_db(current_app)
    
    # user_idが提供されているか確認
    if 'user_id' not in data or not data['user_id']:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    # 樹種IDが提供されていない場合はエラーを返す
    if 'species_id' not in data:
        return jsonify({"error": "樹種IDが必要です"}), 400
    
    # 樹種IDが有効かデータベースでチェック
    species_id = data['species_id']
    species = db.execute('SELECT name FROM species_master WHERE id = ?', (species_id,)).fetchone()
    if not species:
        return jsonify({"error": "無効な樹種IDです"}), 400
    
    species_name = species['name']
    
    db.execute(
        'INSERT INTO bonsai (user_id, name, species_id, species, notes) VALUES (?, ?, ?, ?, ?)',
        (data['user_id'], data['name'], species_id, species_name, data.get('notes', ''))
    )
    db.commit()
    
    # 新しく追加された盆栽のIDを取得
    new_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    
    return jsonify({
        "message": "盆栽を登録しました", 
        "id": new_id
    })

@bp.route('/<int:bonsai_id>', methods=['GET'])
def get_bonsai_by_id(bonsai_id):
    """IDによる盆栽の取得"""
    db = get_db(current_app)
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (bonsai_id,)).fetchone()
    
    if not bonsai:
        return jsonify({"error": "盆栽が見つかりません"}), 404
    
    # 盆栽の画像情報を取得
    b_dict = dict(bonsai)
    image = db.execute('SELECT * FROM bonsai_images WHERE bonsai_id = ? ORDER BY created_at DESC LIMIT 1', 
                    (bonsai_id,)).fetchone()
    b_dict['has_image'] = bool(image)
    if image:
        b_dict['image_id'] = image['id']
    
    return jsonify(b_dict)

@bp.route('/<int:bonsai_id>/image', methods=['POST'])
def upload_bonsai_image(bonsai_id):
    """盆栽の画像をアップロードするエンドポイント"""
    # ユーザーIDをクエリパラメータから取得
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    db = get_db(current_app)
    
    # 盆栽の存在確認と所有者チェック
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ? AND user_id = ?', 
                      (bonsai_id, user_id)).fetchone()
    if not bonsai:
        return jsonify({"error": "盆栽が見つからないか、アクセス権限がありません"}), 404
    
    # ファイルの確認
    if 'image' not in request.files:
        return jsonify({"error": "画像ファイルが必要です"}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "ファイルが選択されていません"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "許可されていないファイル形式です"}), 400
    
    # ファイル名の安全化と一意性の確保
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    
    # アップロードディレクトリの確保
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # ファイルの保存
    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)
    
    # データベースに画像情報を保存
    try:
        db.execute(
            'INSERT INTO bonsai_images (bonsai_id, user_id, filename, original_filename) VALUES (?, ?, ?, ?)',
            (bonsai_id, user_id, unique_filename, original_filename)
        )
        db.commit()
        image_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        return jsonify({
            "success": True,
            "message": "画像がアップロードされました",
            "image_id": image_id
        }), 200
    except sqlite3.Error as e:
        # エラーが発生した場合、ファイルを削除して失敗を返す
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500

@bp.route('/image/<int:image_id>', methods=['GET'])
def get_bonsai_image(image_id):
    """画像IDから画像を取得するエンドポイント"""
    db = get_db(current_app)
    
    # 画像情報の取得
    image = db.execute('SELECT * FROM bonsai_images WHERE id = ?', (image_id,)).fetchone()
    if not image:
        return jsonify({"error": "画像が見つかりません"}), 404
    
    # ユーザー権限確認（オプション）
    user_id = request.args.get('user_id')
    if user_id and int(user_id) != image['user_id']:
        # 簡易チェック。本番環境ではより堅牢な認証が必要
        bonsai = db.execute('SELECT * FROM bonsai WHERE id = ?', (image['bonsai_id'],)).fetchone()
        if bonsai['user_id'] != int(user_id):
            return jsonify({"error": "アクセス権限がありません"}), 403
    
    # アップロードディレクトリからファイルを送信
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    
    return send_from_directory(upload_dir, image['filename'])

@bp.route('/image/<int:image_id>', methods=['DELETE'])
def delete_bonsai_image(image_id):
    """画像を削除するエンドポイント"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    db = get_db(current_app)
    
    # 画像情報の取得
    image = db.execute('SELECT * FROM bonsai_images WHERE id = ?', (image_id,)).fetchone()
    if not image:
        return jsonify({"error": "画像が見つかりません"}), 404
    
    # 所有者確認
    if image['user_id'] != int(user_id):
        return jsonify({"error": "アクセス権限がありません"}), 403
    
    # ファイルの削除
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    file_path = os.path.join(upload_dir, image['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # データベースからの削除
    db.execute('DELETE FROM bonsai_images WHERE id = ?', (image_id,))
    db.commit()
    
    return jsonify({"success": True, "message": "画像が削除されました"}), 200

@bp.route('/<int:bonsai_id>', methods=['DELETE'])
def delete_bonsai(bonsai_id):
    """盆栽を削除するエンドポイント（関連する画像や記録も一緒に削除）"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    db = get_db(current_app)
    
    # 盆栽の存在確認と所有者チェック
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ? AND user_id = ?', 
                      (bonsai_id, user_id)).fetchone()
    if not bonsai:
        return jsonify({"error": "盆栽が見つからないか、削除権限がありません"}), 404
    
    try:
        # 関連する画像ファイルを取得して削除
        images = db.execute('SELECT * FROM bonsai_images WHERE bonsai_id = ?', 
                          (bonsai_id,)).fetchall()
        
        upload_dir = os.path.join(current_app.instance_path, 'uploads')
        for image in images:
            file_path = os.path.join(upload_dir, image['filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # データベースから関連データを削除（カスケード削除）
        # 1. 画像記録を削除
        db.execute('DELETE FROM bonsai_images WHERE bonsai_id = ?', (bonsai_id,))
        
        # 2. 農薬記録を削除
        db.execute('DELETE FROM pesticide_logs WHERE bonsai_id = ?', (bonsai_id,))
        
        # 3. 盆栽本体を削除
        db.execute('DELETE FROM bonsai WHERE id = ?', (bonsai_id,))
        
        db.commit()
        
        return jsonify({
            "success": True,
            "message": "盆栽と関連するデータを削除しました",
            "deleted_bonsai_id": bonsai_id
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"削除中にエラーが発生しました: {str(e)}"}), 500

@bp.route('/<int:bonsai_id>/images', methods=['GET'])
def get_bonsai_images(bonsai_id):
    """特定の盆栽の全画像を取得するエンドポイント"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "ユーザーIDが必要です"}), 400
    
    db = get_db(current_app)
    
    # 盆栽の存在確認と所有者チェック
    bonsai = db.execute('SELECT * FROM bonsai WHERE id = ? AND user_id = ?', 
                      (bonsai_id, user_id)).fetchone()
    if not bonsai:
        return jsonify({"error": "盆栽が見つからないか、アクセス権限がありません"}), 404
    
    # 盆栽の全画像を取得（新しいものから順番）
    images = db.execute(
        'SELECT * FROM bonsai_images WHERE bonsai_id = ? ORDER BY created_at DESC', 
        (bonsai_id,)
    ).fetchall()
    
    # 辞書形式に変換
    result = []
    for image in images:
        image_dict = dict(image)
        result.append(image_dict)
    
    return jsonify({
        "bonsai_id": bonsai_id,
        "bonsai_name": bonsai['name'],
        "images": result
    })
