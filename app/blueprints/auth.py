import functools
import random
import time
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, abort
from app.models import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        reader_id = request.form['reader_id'].strip()
        name = request.form['name']
        sex = request.form['sex']
        password = request.form['password']
        db = get_db()
        error = None

        if not reader_id: error = 'ID is required.'

        # --- 自动角色判定逻辑 ---
        role_id = 1  # 默认为访客
        level_id = 0  # 借阅等级

        id_len = len(reader_id)
        if id_len == 12 and reader_id.isdigit():
            role_id = 2  # 学生角色
            level_id = 1  # 本科生借阅等级 (默认)
        elif id_len == 8 and reader_id.isdigit():
            role_id = 3  # 教职工角色
            level_id = 3  # 教师借阅等级
        else:
            # 不符合规则的注册，默认为访客
            pass

        if error is None:
            try:
                db.execute(
                    "INSERT INTO READER (READER_ID, NAME, SEX, LEVEL_ID, ROLE_ID, CURRENT_CREDIT, EXPIRY_DATE, PASSWORD) VALUES (?, ?, ?, ?, ?, 100, '2029-06-30', ?)",
                    (reader_id, name, sex, level_id, role_id, password)
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {reader_id} is already registered."
            else:
                flash(f'注册成功！系统识别您为：{"学生" if role_id == 2 else "教职工" if role_id == 3 else "访客"}',
                      'success')
                return redirect(url_for('auth.login'))

        flash(error, 'error')

    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']
        db = get_db()
        error = None

        # 统一查询 READER 表
        user = db.execute('''
            SELECT r.*, ro.ROLE_NAME 
            FROM READER r 
            JOIN SYS_ROLE ro ON r.ROLE_ID = ro.ROLE_ID 
            WHERE r.READER_ID = ?
        ''', (user_id,)).fetchone()

        if user is None:
            error = '账号不存在。'
        elif user['PASSWORD'] != password:
            error = '密码错误。'

        if error is None:
            session.clear()
            session['user_id'] = user['READER_ID']
            session['user_name'] = user['NAME']
            session['role_id'] = user['ROLE_ID']  # 核心：存储角色ID
            session['role_name'] = user['ROLE_NAME']

            # --- 加载权限列表到 Session ---
            # 如果是超管 (8)，拥有 root_access
            if user['ROLE_ID'] == 8:
                session['permissions'] = ['root_access', 'access_dashboard', 'access_services', 'manage_acq_order',
                                          'manage_acq_arrival', 'manage_circulation', 'manage_users']
            else:
                perms = db.execute('''
                    SELECT p.PERM_CODE 
                    FROM SYS_ROLE_PERMISSION rp
                    JOIN SYS_PERMISSION p ON rp.PERM_ID = p.PERM_ID
                    WHERE rp.ROLE_ID = ?
                ''', (user['ROLE_ID'],)).fetchall()
                session['permissions'] = [p['PERM_CODE'] for p in perms]

            return redirect(url_for('main.dashboard'))

        flash(error, 'error')

    return render_template('auth/login.html')


@bp.route('/guest_login')
def guest_login():
    """
    访客一键登录
    逻辑：生成以 99 开头的 8 位随机 ID，注册并自动登录
    """
    db = get_db()

    # 生成随机访客ID (99 + 6位随机数)
    guest_id = int(f"99{random.randint(100000, 999999)}")
    guest_name = f"访客 {str(guest_id)[-4:]}"

    # 尝试创建访客账户
    try:
        # ROLE_ID = 1 (访客), LEVEL_ID = 0 (无借阅权)
        db.execute(
            "INSERT INTO READER (READER_ID, NAME, SEX, LEVEL_ID, ROLE_ID, CURRENT_CREDIT, EXPIRY_DATE, PASSWORD) VALUES (?, ?, 'M', 0, 1, 0, '2099-12-31', 'guest')",
            (guest_id, guest_name)
        )
        db.commit()
    except db.IntegrityError:
        # 极低概率碰撞，重试一次
        guest_id = int(f"99{random.randint(100000, 999999)}")
        guest_name = f"访客 {str(guest_id)[-4:]}"
        db.execute(
            "INSERT INTO READER (READER_ID, NAME, SEX, LEVEL_ID, ROLE_ID, CURRENT_CREDIT, EXPIRY_DATE, PASSWORD) VALUES (?, ?, 'M', 0, 1, 0, '2099-12-31', 'guest')",
            (guest_id, guest_name)
        )
        db.commit()

    # 设置 Session
    session.clear()
    session['user_id'] = guest_id
    session['user_name'] = guest_name
    session['role_id'] = 1
    session['role_name'] = '访客'
    # 访客只有基础查看权限
    session['permissions'] = ['access_dashboard']

    # 标记为临时访客，Logout 时销毁
    session['is_temp_guest'] = True

    flash(f'欢迎您，{guest_name}！您正以访客身份浏览。', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/logout')
def logout():
    # 检查是否是临时访客
    if session.get('is_temp_guest'):
        user_id = session.get('user_id')
        if user_id:
            db = get_db()
            # 物理销毁账号
            db.execute("DELETE FROM READER WHERE READER_ID = ? AND ROLE_ID = 1", (user_id,))
            db.commit()
            print(f"System: Guest account {user_id} destroyed.")

    session.clear()
    return redirect(url_for('auth.login'))


# --- 权限控制装饰器 ---

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return view(**kwargs)

    return wrapped_view


def permission_required(perm_code):
    """
    RBAC 核心装饰器：检查当前用户是否拥有指定权限代码
    """

    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            # 1. 未登录
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))

            # [修复] 脏Session检查：
            # 如果用户已登录，但 Session 中没有 permissions 字段（说明是旧代码留下的缓存），
            # 强制清空并重新登录，而不是报错 403。
            if 'permissions' not in session:
                session.clear()
                flash('系统升级，请重新登录以更新权限。', 'warning')
                return redirect(url_for('auth.login'))

            # 2. 检查权限
            user_perms = session.get('permissions', [])
            if 'root_access' in user_perms or perm_code in user_perms:
                return view(**kwargs)
            else:
                abort(403)  # 403 Forbidden

        return wrapped_view

    return decorator