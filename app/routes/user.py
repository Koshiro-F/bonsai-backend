from flask import Blueprint, request, jsonify, current_app, session, make_response
from flask_cors import cross_origin
from ..db import get_db, init_db
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

bp = Blueprint('user', __name__, url_prefix='/api/user')

@bp.route('/login', methods=['POST', 'OPTIONS'])
def api_login():
    # OPTIONSリクエストに対応
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
        
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db()
    cur = conn.execute("SELECT password_hash, id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()

    if row and check_password_hash(row[0], password):
        session['user'] = username  # セッションにユーザー名を保存
        response = jsonify({"success": True, "user": username, "id": row[1]})
        # セッションCookieを手動で設定
        response = _corsify_actual_response(response)
        return response
    else:
        response = jsonify({"success": False})
        response.status_code = 401
        return _corsify_actual_response(response)

@bp.route('/logout', methods=['GET', 'OPTIONS'])
def api_logout():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
        
    session.pop('user', None)
    response = jsonify({"success": True})
    return _corsify_actual_response(response)

@bp.route('/register', methods=['POST', 'OPTIONS'])
def api_register():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
        
    # init_db()
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # 新規ユーザーのロール（管理者のみが別の管理者を作成可能）
    role = data.get('role', 'user')
    if role not in ['user', 'admin']:
        role = 'user'  # 不正な値の場合はデフォルトに戻す
    
    # 簡易的なバリデーション
    if len(username) < 3:
        response = jsonify({"success": False, "message": "ユーザー名は3文字以上必要です"})
        response.status_code = 400
        return _corsify_actual_response(response)
        
    if len(password) < 6:
        response = jsonify({"success": False, "message": "パスワードは6文字以上必要です"})
        response.status_code = 400
        return _corsify_actual_response(response)
            
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)', 
                    (username, password_hash, role))
        conn.commit()
        cur = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_id = cur.fetchone()[0]
        session['user'] = username  # セッションにユーザー名を保存
        # 新規ユーザーの情報を返す（パスワードは除く）
        response = jsonify({
            "success": True, 
            "user": {
                "username": username,
                "role": role
            },
            "id": user_id,
            "message": f"ユーザー '{username}' を {role} 権限で登録しました"
        })
        return _corsify_actual_response(response)
    except sqlite3.IntegrityError:
        response = jsonify({"success": False, "message": "このユーザー名は既に使用されています"})
        response.status_code = 409
        return _corsify_actual_response(response)
    finally:
        conn.close()

@bp.route('/users', methods=['GET', 'OPTIONS'])
def api_get_users():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    # セッションチェック - ユーザーがログインしているか確認
    if 'user' not in session:
        response = jsonify({"success": False, "message": "ログインが必要です"})
        response.status_code = 401
        return _corsify_actual_response(response)
    
    # 管理者権限チェック - is_admin関数が引数を取らないので修正
    is_admin_status = check_admin_status()

    if not is_admin_status:
        response = jsonify({"success": False, "message": "管理者権限が必要です"})
        response.status_code = 403
        return _corsify_actual_response(response)
    
    # デバッグ用の情報を簡素化
    debug_info = {
        "session_user": session.get('user'),
        "is_admin": is_admin_status
    }
    
    conn = get_db()
    try:
        # ユーザー一覧を取得（パスワードハッシュは除外）
        cur = conn.execute("SELECT id, username, role FROM users ORDER BY username")
        users = [{"id": row["id"], "username": row["username"], "role": row["role"]} for row in cur.fetchall()]
        response = jsonify({
            "success": True, 
            "users": users,
            "debug_info": debug_info
        })
        return _corsify_actual_response(response)
    except Exception as e:
        response = jsonify({
            "success": False, 
            "message": str(e),
            "debug_info": debug_info
        })
        response.status_code = 500
        return _corsify_actual_response(response)
    finally:
        conn.close()

# ユーザーが管理者かどうかを確認する関数
@bp.route('/is-admin/<int:user_id>', methods=['GET', 'OPTIONS'])
def is_admin(user_id):
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    conn = get_db()
    try:
        cur = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        response = jsonify({"success": True, "is_admin": row and row['role'] == 'admin'})
        return _corsify_actual_response(response)
    except Exception as e:
        print(f"管理者権限の確認中にエラー: {e}")
        response = jsonify({"success": False, "message": str(e)})
        response.status_code = 500
        return _corsify_actual_response(response)
    finally:
        conn.close()

@bp.route('/<int:user_id>', methods=['GET', 'OPTIONS'])
def get_user_by_id(user_id):
    """特定のユーザーIDからユーザー情報を取得するエンドポイント"""
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
    
    conn = get_db()
    try:
        cur = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            user_info = {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"]
            }
            response = jsonify({"success": True, "user": user_info})
        else:
            response = jsonify({"success": False, "message": "ユーザーが見つかりません"})
            response.status_code = 404
        return _corsify_actual_response(response)
    except Exception as e:
        response = jsonify({"success": False, "message": str(e)})
        response.status_code = 500
        return _corsify_actual_response(response)
    finally:
        conn.close()

# 管理者ステータスをチェックするユーティリティ関数
def check_admin_status():
    username = session.get('user')
    print(f"セッションユーザー: {username}")
    if not username:
        print("ログインしていません")
        return False
    conn = get_db()
    try:
        cur = conn.execute("SELECT role FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        print(f"データベースから取得した行: {row}")
        return row and row['role'] == 'admin'
    except Exception as e:
        print(f"管理者権限の確認中にエラー: {e}")
        return False
    finally:
        conn.close()

# CORS プリフライトレスポンスを構築する関数
def _build_cors_preflight_response():
    response = make_response()
    origin = request.headers.get("Origin", "*")
    allowed_origins = ["https://bonsai.modur4.com", "https://bonsai-backend.modur4.com", "http://localhost:6173", "http://localhost:6000"]
    
    # オリジンが許可リストにあることを確認
    if origin in allowed_origins or origin == "*":
        response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,Accept,X-Requested-With")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Max-Age", "600")
        response.headers.add("Vary", "Origin") # キャッシュ制御のために追加
    
    return response

# 実際のレスポンスにCORSヘッダーを追加する関数
def _corsify_actual_response(response):
    origin = request.headers.get("Origin", "*")
    # 許可されたオリジンのリストをチェック
    allowed_origins = ["https://bonsai.modur4.com", "https://bonsai-backend.modur4.com", "http://localhost:6173", "http://localhost:6000"]
    
    # ヘッダーが既に設定されていないことを確認
    if (origin == "*" or origin in allowed_origins) and 'Access-Control-Allow-Origin' not in response.headers:
        response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Vary", "Origin")  # キャッシュ制御のためにVaryヘッダーを追加
    
    return response

