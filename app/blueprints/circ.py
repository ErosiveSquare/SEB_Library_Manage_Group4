from flask import Blueprint, render_template, session, request, flash, redirect, url_for
from app.models import get_db
from app.blueprints.auth import login_required
import datetime

bp = Blueprint('circ', __name__, url_prefix='/circ')


@bp.route('/history')
@login_required
def history():
    db = get_db()
    user_id = session.get('user_id')
    records = db.execute('''
        SELECT b.*, h.BOOK_NAME, h.AUTHOR, h.CALL_NUMBER
        FROM BORROW_RECORD b
        JOIN CIRCULATION_DETAIL d ON b.BARCODE = d.BARCODE
        JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN
        WHERE b.READER_ID = ?
        ORDER BY b.BORROW_DATE DESC
    ''', (user_id,)).fetchall()
    return render_template('circ/history.html', records=records)


# --- 新增：流通工作台 (Admin only) ---
@bp.route('/workbench', methods=('GET', 'POST'))
@login_required
def workbench():
    if not session.get('user_role') in [1, 2]:
        flash('权限不足', 'error')
        return redirect(url_for('main.dashboard'))

    db = get_db()
    result_msg = None

    if request.method == 'POST':
        action = request.form['action']  # 'borrow' or 'return'
        barcode = request.form['barcode'].strip()

        # 1. 还书逻辑
        if action == 'return':
            # 查该书当前是否借出
            record = db.execute("SELECT * FROM BORROW_RECORD WHERE BARCODE=? AND STATUS=1", (barcode,)).fetchone()
            if record:
                # 更新还书时间
                db.execute("UPDATE BORROW_RECORD SET RETURN_DATE=?, STATUS=2 WHERE BORROW_ID=?",
                           (datetime.datetime.now(), record['BORROW_ID']))
                # 更新图书状态 -> 在馆
                db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=1 WHERE BARCODE=?", (barcode,))
                db.commit()
                flash(f'图书 {barcode} 归还成功！', 'success')
            else:
                flash(f'图书 {barcode} 未借出或条码错误', 'error')

        # 2. 借书逻辑
        elif action == 'borrow':
            reader_id = request.form['reader_id'].strip()
            # 校验图书状态
            book = db.execute("SELECT * FROM CIRCULATION_DETAIL WHERE BARCODE=?", (barcode,)).fetchone()
            # 校验读者
            reader = db.execute("SELECT * FROM READER WHERE READER_ID=?", (reader_id,)).fetchone()

            error = None
            if not book:
                error = '图书条码不存在'
            elif book['STATUS'] != 1:
                error = '图书状态不可借 (已借出/报损)'
            elif not reader:
                error = '读者ID不存在'

            if not error:
                # 计算应还日期 (默认30天)
                due_date = datetime.datetime.now() + datetime.timedelta(days=30)

                # 插入借阅记录
                db.execute(
                    "INSERT INTO BORROW_RECORD (READER_ID, BARCODE, BORROW_DATE, DUE_DATE, STATUS) VALUES (?, ?, ?, ?, 1)",
                    (reader_id, barcode, datetime.datetime.now(), due_date))
                # 更新图书状态 -> 借出
                db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=2 WHERE BARCODE=?", (barcode,))
                db.commit()
                flash(f'图书借阅成功：{reader_id} 借走了 {barcode}', 'success')
            else:
                flash(error, 'error')

    return render_template('circ/workbench.html')