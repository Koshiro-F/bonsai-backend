from flask import Blueprint, jsonify, current_app
from ..db import get_db
from datetime import datetime, timedelta

bp = Blueprint('other_settings', __name__, url_prefix='/api/other_settings')

# セッションCookieの設定をカスタマイズ
@bp.after_request
def after_request(response):
    # リクエスト元のオリジンを取得
    origin = request.headers.get('Origin', '')
    allowed_origins = ["https://bonsai.modur4.com", "https://bonsai-backend.modur4.com", "http://localhost:6173", "http://localhost:6000"]
    
    # CORS設定は flask_cors によって自動的に設定される場合があるため、
    # 既にヘッダーが設定されているかチェックして、設定されていない場合のみ追加する
    if origin in allowed_origins and 'Access-Control-Allow-Origin' not in response.headers:
        response.headers.add('Access-Control-Allow-Origin', origin)
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,X-Requested-With')
        
    # SameSite属性を設定
    if 'Set-Cookie' in response.headers:
        # 既存のSet-Cookieヘッダーを保持しつつ、必要な属性を追加
        response.headers['Set-Cookie'] = response.headers['Set-Cookie'] + '; HttpOnly; SameSite=None; Secure'
    
    return response