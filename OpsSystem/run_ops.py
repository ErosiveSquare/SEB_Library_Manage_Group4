import os
import sqlite3
import shutil
import datetime
import hashlib
import zipfile
from flask import Flask, render_template, request, session, redirect, url_for, flash, send_file

# --- 配置路径 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
# 指向项目根目录 (LibraryManage)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '../'))
INSTANCE_PATH = os.path.abspath(os.path.join(BASE_DIR, '../instance'))
OPS_DB = os.path.join(BASE_DIR, 'ops_data.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = 'ciCDH*AUni#avudh%afe^n--kll%@'

DB_MAP = {
    'library': os.path.join(INSTANCE_PATH, 'library.db'),
    'ai': os.path.join(INSTANCE_PATH, 'AI.db'),
    'ops': OPS_DB
}


# --- 核心辅助函数 ---

def get_daily_key():
    """
    生成每日动态注册密钥
    逻辑：MD5(当前日期 + 系统盐) 取前10位大写
    """
    salt = "NCEPU_LIBRARY_OPS_SECRET_SALT_2026"
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    raw_str = f"{today_str}_{salt}"
    hash_obj = hashlib.md5(raw_str.encode())
    return hash_obj.hexdigest()[:10].upper()


def get_db_connection(db_key):
    path = DB_MAP.get(db_key)
    if not path or not os.path.exists(path): return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_ops_db():
    conn = sqlite3.connect(OPS_DB)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS ADMIN_USER (ID INTEGER PRIMARY KEY, USERNAME TEXT, PASSWORD TEXT)')

    # 超级管理员 1001
    super_admin = c.execute("SELECT * FROM ADMIN_USER WHERE USERNAME='1001'").fetchone()
    if not super_admin:
        c.execute("INSERT INTO ADMIN_USER (USERNAME, PASSWORD) VALUES (?, ?)", ('1001', 'admin123'))
        print(">>> 超级管理员 (1001) 已自动创建")

    # 默认 admin
    default_admin = c.execute("SELECT * FROM ADMIN_USER WHERE USERNAME='admin'").fetchone()
    if not default_admin:
        c.execute("INSERT INTO ADMIN_USER (USERNAME, PASSWORD) VALUES (?, ?)", ('admin', 'admin888'))

    conn.commit()
    conn.close()


# --- 装饰器 ---
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'ops_user' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# --- 路由 ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection('ops')
        user = conn.execute("SELECT * FROM ADMIN_USER WHERE USERNAME=?", (username,)).fetchone()
        conn.close()

        if user and user['PASSWORD'] == password:
            session['ops_user'] = username
            return redirect(url_for('dashboard'))
        flash('认证失败：用户名或密码错误', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']
        input_key = request.form.get('reg_key', '').strip().upper()

        correct_key = get_daily_key()
        if input_key != correct_key:
            flash(f'注册密钥错误！', 'error')
            return render_template('register.html')

        if password != confirm:
            flash('两次密码输入不一致', 'error')
            return render_template('register.html')

        conn = get_db_connection('ops')
        exist = conn.execute("SELECT * FROM ADMIN_USER WHERE USERNAME=?", (username,)).fetchone()
        if exist:
            flash('用户名已存在', 'error')
        else:
            conn.execute("INSERT INTO ADMIN_USER (USERNAME, PASSWORD) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('注册成功，请登录', 'success')
            conn.close()
            return redirect(url_for('login'))
        conn.close()

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    status = []
    for k, p in DB_MAP.items():
        exists = os.path.exists(p)
        size = round(os.path.getsize(p) / 1024, 2) if exists else 0
        status.append({'name': k.upper(), 'path': p, 'exists': exists, 'size': size})

    today_key = get_daily_key()
    return render_template('dashboard.html', db_status=status, today_key=today_key)


@app.route('/db/<db_key>', methods=['GET', 'POST'])
@login_required
def db_manager(db_key):
    if db_key not in DB_MAP: return redirect(url_for('dashboard'))
    conn = get_db_connection(db_key)
    if not conn:
        flash(f'数据库文件 {db_key} 不存在', 'error')
        return redirect(url_for('dashboard'))

    cursor = conn.cursor()
    tables = [r['name'] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    selected_table = request.args.get('table', tables[0] if tables else None)

    rows = []
    columns = []

    if selected_table:
        cols_info = cursor.execute(f"PRAGMA table_info({selected_table})").fetchall()
        columns = [c['name'] for c in cols_info]

        if request.method == 'POST':
            action = request.form.get('action')
            try:
                if action == 'add':
                    fields, values, placeholders = [], [], []
                    for col in columns:
                        val = request.form.get(f'col_{col}')
                        if val == '' and col.upper().endswith('ID'): continue
                        fields.append(col)
                        values.append(val)
                        placeholders.append('?')
                    sql = f"INSERT INTO {selected_table} ({','.join(fields)}) VALUES ({','.join(placeholders)})"
                    cursor.execute(sql, values)
                    conn.commit()
                    flash('成功添加一条记录', 'success')

                elif action == 'edit':
                    rowid = request.form.get('rowid')
                    set_clause, values = [], []
                    for col in columns:
                        val = request.form.get(f'col_{col}')
                        set_clause.append(f"{col} = ?")
                        values.append(val)
                    values.append(rowid)
                    sql = f"UPDATE {selected_table} SET {', '.join(set_clause)} WHERE rowid = ?"
                    cursor.execute(sql, values)
                    conn.commit()
                    flash(f'ID: {rowid} 更新成功', 'success')

                elif action == 'delete':
                    rowid = request.form.get('rowid')
                    cursor.execute(f"DELETE FROM {selected_table} WHERE rowid = ?", (rowid,))
                    conn.commit()
                    flash('记录已删除', 'success')

            except Exception as e:
                flash(f'操作失败: {str(e)}', 'error')

        rows_raw = cursor.execute(f"SELECT rowid, * FROM {selected_table} ORDER BY rowid DESC LIMIT 200").fetchall()
        rows = [dict(row) for row in rows_raw]

    conn.close()
    return render_template('db_manager.html', current_db=db_key, tables=tables, selected_table=selected_table,
                           columns=columns, rows=rows)


# --- 核心修复：Backup Route ---
@app.route('/backup', methods=['GET', 'POST'])
@login_required
def backup_center():
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

    if request.method == 'POST':
        # 获取前端传来的 action (对应 input value)
        act = request.form.get('action')
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        print(f">>> 接收到备份指令: {act}")  # 调试打印

        try:
            if act == 'db':
                # 仅备份数据库文件
                count = 0
                for k, p in DB_MAP.items():
                    if os.path.exists(p):
                        try:
                            shutil.copy(p, os.path.join(BACKUP_DIR, f"{k}_{ts}.db"))
                            count += 1
                        except Exception as copy_err:
                            flash(f"警告：{k} 备份失败 ({copy_err})", 'error')
                flash(f'成功备份 {count} 个数据库文件', 'success')

            elif act == 'full':
                # 全量备份
                zip_filename = os.path.join(BACKUP_DIR, f"Project_Full_{ts}.zip")
                with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(PROJECT_ROOT):
                        # 排除列表
                        for ignore in ['backups', '__pycache__', '.git', '.idea', 'venv']:
                            if ignore in dirs: dirs.remove(ignore)

                        for file in files:
                            if file.endswith('.zip') or file.endswith('.pyc'): continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, PROJECT_ROOT)
                            try:
                                zipf.write(file_path, arcname)
                            except:
                                pass
                flash(f'全项目源码归档完成！', 'success')

            else:
                flash(f'未知的操作指令: {act}', 'error')

        except Exception as e:
            flash(f'备份执行出错: {str(e)}', 'error')

    # 读取备份列表
    files = []
    if os.path.exists(BACKUP_DIR):
        for f in os.listdir(BACKUP_DIR):
            fp = os.path.join(BACKUP_DIR, f)
            if os.path.isfile(fp):
                size = round(os.path.getsize(fp) / (1024 * 1024), 2)
                t = datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')
                files.append({'name': f, 'size': size, 'time': t})

    files.sort(key=lambda x: x['time'], reverse=True)
    return render_template('backup.html', files=files)


@app.route('/dl/<path:filename>')
@login_required
def dl_backup(filename):
    return send_file(os.path.join(BACKUP_DIR, filename), as_attachment=True)


if __name__ == '__main__':
    init_ops_db()
    app.run(host='0.0.0.0', port=5001, debug=True)