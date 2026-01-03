import functools
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from app.models import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        reader_id = request.form['reader_id']
        name = request.form['name']
        sex = request.form['sex']
        password = request.form['password']
        db = get_db()
        error = None

        if not reader_id: error = 'ID is required.'

        if error is None:
            try:
                # 默认注册为本科生 (LEVEL_ID=1), 初始分=100
                db.execute(
                    "INSERT INTO READER (READER_ID, NAME, SEX, LEVEL_ID, CURRENT_CREDIT, EXPIRY_DATE, PASSWORD) VALUES (?, ?, ?, 1, 100, '2029-06-30', ?)",
                    (reader_id, name, sex, password)
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {reader_id} is already registered."
            else:
                flash('注册成功，请登录。', 'success')
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

        # 尝试查询读者
        user = db.execute('SELECT * FROM READER WHERE READER_ID = ?', (user_id,)).fetchone()
        role = None

        # 如果不是读者，尝试查询管理员
        if user is None:
            user = db.execute('SELECT * FROM ADMIN WHERE ADMIN_ID = ?', (user_id,)).fetchone()
            if user:
                role = user['ROLE']  # 0, 1, 2

        if user is None:
            error = '账号不存在。'
        elif user['PASSWORD'] != password:
            error = '密码错误。'

        if error is None:
            session.clear()
            # 区分读者和管理员存储session
            if role is not None:
                session['user_id'] = user['ADMIN_ID']
                session['user_name'] = user['NAME']
                session['user_role'] = role  # 有role代表是管理员
            else:
                session['user_id'] = user['READER_ID']
                session['user_name'] = user['NAME']

            return redirect(url_for('main.dashboard'))

        flash(error, 'error')

    return render_template('auth/login.html')  # 使用你提供的 Login.html


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


# 登录验证装饰器
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return view(**kwargs)

    return wrapped_view