from flask import Blueprint, render_template, request, session, abort, current_app, redirect, url_for, flash
from app.models import get_db, CLC_DATA
from app.blueprints.auth import permission_required, login_required
from app.services.map_service import MapService
import os
import datetime

bp = Blueprint('main', __name__)


@bp.route('/')
@permission_required('access_dashboard')
def dashboard():
    """图书馆首页 - 数据大屏 (Data Visualization Dashboard)"""
    db = get_db()

    # --- 1. 基础核心指标 ---
    total_titles = db.execute('SELECT COUNT(*) FROM CIRCULATION_HEAD').fetchone()[0]
    total_books = db.execute('SELECT COUNT(*) FROM CIRCULATION_DETAIL WHERE STATUS != 4').fetchone()[0]
    total_borrows = db.execute('SELECT COUNT(*) FROM BORROW_RECORD').fetchone()[0]
    active_borrows = db.execute('SELECT COUNT(*) FROM BORROW_RECORD WHERE STATUS = 1').fetchone()[0]

    # 今日借阅人数 (Real-time)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    today_borrowers = db.execute(
        "SELECT COUNT(DISTINCT READER_ID) FROM BORROW_RECORD WHERE substr(BORROW_DATE, 1, 10) = ?",
        (today_str,)
    ).fetchone()[0]

    # --- 2. 真实图表数据：近7天借阅趋势 ---
    today = datetime.date.today()
    dates_last_7_days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]

    weekly_labels = []
    weekly_data = []

    for d in dates_last_7_days:
        weekly_labels.append(d.strftime('%m-%d'))
        count = db.execute(
            "SELECT COUNT(*) FROM BORROW_RECORD WHERE substr(BORROW_DATE, 1, 10) = ?",
            (str(d),)
        ).fetchone()[0]
        weekly_data.append(count)

    # --- 3. 馆藏分类统计 (Top 10 + 其他) ---
    # 按数量降序排列
    cat_stats = db.execute('''
        SELECT substr(CLC_CODE, 1, 1) as P, COUNT(*) as C 
        FROM CIRCULATION_HEAD 
        GROUP BY substr(CLC_CODE, 1, 1) 
        ORDER BY C DESC
    ''').fetchall()

    pie_labels = []
    pie_data = []

    # 取前 10 名
    top_n = 10
    for i, row in enumerate(cat_stats):
        if i < top_n:
            code = row['P']
            # 获取中文名称
            full_name = CLC_DATA.get(code, '综合').split('、')[0]
            pie_labels.append(f"{code} {full_name}")
            pie_data.append(row['C'])
        else:
            # 剩下的归为"其他"
            if len(pie_labels) <= top_n:
                pie_labels.append("其他分类")
                pie_data.append(row['C'])
            else:
                pie_data[-1] += row['C']

    # --- 4. 最新入库推荐 ---
    new_arrivals = db.execute('SELECT * FROM CIRCULATION_HEAD ORDER BY rowid DESC LIMIT 4').fetchall()
    covers_path = os.path.join(current_app.static_folder, 'asset', 'covers')
    cover_images = []
    if os.path.exists(covers_path):
        cover_images = [f for f in os.listdir(covers_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        cover_images.sort()
    if not cover_images: cover_images = ['default.png']

    formatted_arrivals = []
    for index, book in enumerate(new_arrivals):
        b = dict(book)
        b['cover_image'] = cover_images[index % len(cover_images)]
        formatted_arrivals.append(b)

    stats = {
        'titles': total_titles,
        'books': total_books,
        'borrows': total_borrows,
        'active': active_borrows,
        'today_borrowers': today_borrowers,
        # 图表数据
        'pie_labels': pie_labels,
        'pie_data': pie_data,
        'trend_labels': weekly_labels,
        'trend_data': weekly_data
    }

    return render_template('main/dashboard.html', stats=stats, new_arrivals=formatted_arrivals)


@bp.route('/profile')
@login_required
def profile():
    db = get_db()
    user_id = session.get('user_id')
    user = db.execute('''
        SELECT r.*, ro.ROLE_NAME 
        FROM READER r 
        JOIN SYS_ROLE ro ON r.ROLE_ID = ro.ROLE_ID 
        WHERE r.READER_ID = ?
    ''', (user_id,)).fetchone()
    credit_logs = db.execute('SELECT * FROM CREDIT_LOG WHERE READER_ID=? ORDER BY LOG_TIME DESC', (user_id,)).fetchall()
    return render_template('main/profile.html', user=user, credit_logs=credit_logs)


@bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    db = get_db()
    user_id = session.get('user_id')
    action = request.form.get('action')

    if action == 'update_info':
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        if email and '@' not in email:
            flash('邮箱格式不正确', 'error')
            return redirect(url_for('main.profile'))
        db.execute("UPDATE READER SET EMAIL = ?, TELEPHONE = ? WHERE READER_ID = ?", (email, phone, user_id))
        db.commit()
        flash('个人资料已更新', 'success')

    elif action == 'change_password':
        new_pwd = request.form.get('new_password', '').strip()
        confirm_pwd = request.form.get('confirm_password', '').strip()
        if not new_pwd or len(new_pwd) < 6:
            flash('新密码长度至少需要6位', 'error')
        elif new_pwd != confirm_pwd:
            flash('两次输入的密码不一致', 'error')
        else:
            db.execute("UPDATE READER SET PASSWORD = ? WHERE READER_ID = ?", (new_pwd, user_id))
            db.commit()
            flash('密码修改成功，下次登录请使用新密码', 'success')

    return redirect(url_for('main.profile'))


@bp.route('/search')
@permission_required('access_dashboard')
def search():
    query = request.args.get('q', '')
    clc_filter = request.args.get('clc', '')
    books = []
    discovery_data = {}
    covers_path = os.path.join(current_app.static_folder, 'asset', 'covers')
    cover_images = []
    if os.path.exists(covers_path):
        cover_images = [f for f in os.listdir(covers_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        cover_images.sort()
    if not cover_images: cover_images = ['default.png']

    db = get_db()
    if query or clc_filter:
        sql = '''
        SELECT h.*, 
                (SELECT COUNT(*) FROM CIRCULATION_DETAIL d WHERE d.ISBN = h.ISBN AND d.STATUS = 1) as available_count
        FROM CIRCULATION_HEAD h
        WHERE 1=1
        '''
        params = []
        if query:
            sql += " AND (h.BOOK_NAME LIKE ? OR h.AUTHOR LIKE ? OR h.ISBN LIKE ?)"
            s = f'%{query}%'
            params.extend([s, s, s])
        if clc_filter:
            sql += " AND h.CLC_CODE LIKE ?"
            params.append(f'{clc_filter}%')
        books = db.execute(sql, tuple(params)).fetchall()
    else:
        latest_books_raw = db.execute('SELECT * FROM CIRCULATION_HEAD ORDER BY rowid DESC LIMIT 8').fetchall()
        latest_books = []
        for index, book in enumerate(latest_books_raw):
            book_dict = dict(book)
            book_dict['cover_image'] = cover_images[index % len(cover_images)]
            latest_books.append(book_dict)
        cat_stats = db.execute(
            '''SELECT substr(CLC_CODE, 1, 1) as P, COUNT(*) as C FROM CIRCULATION_HEAD GROUP BY substr(CLC_CODE, 1, 1) ORDER BY C DESC LIMIT 5''').fetchall()
        formatted_stats = []
        for row in cat_stats:
            code = row['P']
            name = CLC_DATA.get(code, '综合类').split('、')[0]
            formatted_stats.append({'code': code, 'name': name, 'count': row['C']})
        discovery_data = {'latest': latest_books, 'stats': formatted_stats}

    return render_template('main/search.html', books=books, query=query, clc_filter=clc_filter,
                           discovery=discovery_data, CLC_DATA=CLC_DATA)


@bp.route('/book/<isbn>')
@permission_required('access_dashboard')
def book_detail(isbn):
    db = get_db()
    book = db.execute('SELECT * FROM CIRCULATION_HEAD WHERE ISBN = ?', (isbn,)).fetchone()
    if book is None: abort(404)
    copies = db.execute('''SELECT d.* FROM CIRCULATION_DETAIL d WHERE d.ISBN = ? ORDER BY d.STATUS ASC''',
                        (isbn,)).fetchall()
    map_data = MapService.get_map_data(target_isbn=isbn)
    return render_template('main/book_detail.html', book=book, copies=copies, map_data=map_data)


@bp.route('/credit_log')
@permission_required('access_services')
def credit_log():
    return redirect(url_for('main.profile'))


@bp.route('/map')
@permission_required('access_dashboard')
def library_map():
    map_data = MapService.get_map_data()
    return render_template('main/library_map.html', map_data=map_data)