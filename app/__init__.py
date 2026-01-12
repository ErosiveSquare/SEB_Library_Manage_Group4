import os
from flask import Flask

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # 加载 Config 类配置
    from config import Config
    app.config.from_object(Config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import models
    # 注册数据库关闭函数
    app.teardown_appcontext(models.close_db)

    # 注册蓝图
    from .blueprints import auth, main, acq, circ, sys_admin, ai, notice  # [新增 notice]

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(acq.bp)
    app.register_blueprint(circ.bp)
    app.register_blueprint(sys_admin.bp)
    app.register_blueprint(ai.bp)
    app.register_blueprint(notice.bp)

    app.add_url_rule('/', endpoint='main.dashboard')

    return app