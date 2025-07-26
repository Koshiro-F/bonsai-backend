import os
from flask import Flask
from flask_cors import CORS
from .db import init_db, close_db, init_db_command, init_master_data_command

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    app.config.from_mapping(
        SECRET_KEY='bonsai-secret-key',
        DATABASE=os.path.join(app.instance_path, 'bonsai_users.db'),
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 最大16MBのアップロードを許可
    )
    
    if test_config is None:
        # 本番環境の設定を読み込む
        app.config.from_pyfile('config.py', silent=True)
    else:
        # テスト用設定を適用
        app.config.from_mapping(test_config)
    
    # インスタンスディレクトリとアップロードディレクトリの作成
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError:
        pass
    
    # CORS設定（より包括的に設定）
    CORS(app, 
         supports_credentials=True, 
         origins=[
             "https://bonsai.modur4.com", 
             "https://bonsai-backend.modur4.com", 
             "http://localhost:6173", 
             "http://localhost:6000",
             "http://localhost:5000"
         ],
         allow_headers=[
             "Content-Type", 
             "Authorization", 
             "Accept", 
             "X-Requested-With",
             "Origin",
             "Access-Control-Request-Method",
             "Access-Control-Request-Headers"
         ],
         expose_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         max_age=600,
         vary_header=True,
         send_wildcard=False,
         automatic_options=True)

    # データベース初期化と接続終了
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(init_master_data_command)
    
    # 初回起動時にデータベースを初期化
    with app.app_context():
        init_db()

    # Blueprintの登録
    from .routes import bonsai, pesticide, recommend, user, other_settings, admin_master, work_log
    app.register_blueprint(bonsai.bp)
    app.register_blueprint(pesticide.bp)
    app.register_blueprint(recommend.bp)
    app.register_blueprint(user.bp)
    app.register_blueprint(other_settings.bp)
    app.register_blueprint(admin_master.bp)
    app.register_blueprint(work_log.bp)

    # デバッグ用：全エンドポイントの一覧表示（開発時のみ）
    if app.debug:
        @app.before_first_request
        def show_routes():
            print("🔗 登録されたエンドポイント:")
            for rule in app.url_map.iter_rules():
                if 'pesticides' in rule.rule:
                    print(f"   {rule.rule} -> {rule.methods}")

    return app
