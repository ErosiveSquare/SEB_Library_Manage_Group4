from flask import Blueprint, render_template, request, session
from app.models import get_db
from app.blueprints.auth import login_required

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def dashboard():
    db = get_db()

    # 统计数据 (对应 SDD 统计子系统的一部分逻辑)
    total_books = db.execute('SELECT COUNT(*) FROM CIRCULATION_DETAIL WHERE STATUS=1').fetchone()[0]
    my_borrows_count = 0

    # 模拟“最近借阅活动” (Recent Borrowing Activity)
    # SDD 4.5.2 个人中心 - 我的借阅
    user_id = session.get('user_id')
    recent_activity = []

    if session.get('user_role') is None:  # 是读者
        recent_activity = db.execute('''
            SELECT b.*, h.BOOK_NAME 
            FROM BORROW_RECORD b 
            JOIN CIRCULATION_DETAIL d ON b.BARCODE = d.BARCODE
            JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN
            WHERE b.READER_ID = ? 
            ORDER BY b.BORROW_DATE DESC LIMIT 5
        ''', (user_id,)).fetchall()

        # 获取积分 (SDD 4.1 Reader.CURRENT_CREDIT)
        reader = db.execute('SELECT CURRENT_CREDIT, LEVEL_ID FROM READER WHERE READER_ID = ?', (user_id,)).fetchone()
        credit = reader['CURRENT_CREDIT'] if reader else 0
    else:
        credit = "N/A"

    return render_template('main/dashboard.html',
                           total_books=total_books,
                           activities=recent_activity,
                           credit=credit)


@bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    books = []
    if query:
        db = get_db()
        # SDD 4.5.1 图书检索 SQL实现
        # 关联查询头表和在馆数量
        sql = '''
        SELECT h.*, 
               (SELECT COUNT(*) FROM CIRCULATION_DETAIL d WHERE d.ISBN = h.ISBN AND d.STATUS = 1) as available_count
        FROM CIRCULATION_HEAD h
        WHERE h.BOOK_NAME LIKE ? OR h.AUTHOR LIKE ?
        '''
        search_term = f'%{query}%'
        books = db.execute(sql, (search_term, search_term)).fetchall()

    return render_template('main/search.html', books=books, query=query)