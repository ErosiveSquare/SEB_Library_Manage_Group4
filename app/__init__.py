import os
from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'library.db'),
    )

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import models
    # 注册数据库初始化命令
    app.teardown_appcontext(models.close_db)

    # 注册蓝图
    from .blueprints import auth, main, acq, circ, sys_admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(acq.bp)
    app.register_blueprint(circ.bp)  # 新增这一行
    app.register_blueprint(sys_admin.bp)

    # 设置默认路由
    app.add_url_rule('/', endpoint='main.dashboard')

    return app