from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.models import get_db
from app.blueprints.auth import login_required

bp = Blueprint('sys_admin', __name__, url_prefix='/admin')


@bp.route('/users')
@login_required
def user_list():
    if session.get('user_role') != 2:  # 只有Role 2 (系统管理员) 可见
        return redirect(url_for('main.dashboard'))

    db = get_db()
    # 查询所有读者
    readers = db.execute('SELECT * FROM READER').fetchall()
    # 查询所有管理员
    admins = db.execute('SELECT * FROM ADMIN').fetchall()

    return render_template('admin/user_list.html', readers=readers, admins=admins)