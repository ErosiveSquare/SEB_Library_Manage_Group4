from flask import Blueprint, render_template, session, request, flash, redirect, url_for
from app.models import get_db
from app.blueprints.auth import permission_required
import datetime

bp = Blueprint('circ', __name__, url_prefix='/circ')


# --- 辅助函数：信用分变更 ---
def update_user_credit(db, reader_id, delta, reason, operator_name):
    """
    更新用户信用分，严格控制在 0-100 之间。
    :param delta: 变动值 (正数加分，负数扣分)
    """
    # 1. 获取当前分数
    reader = db.execute("SELECT CURRENT_CREDIT FROM READER WHERE READER_ID=?", (reader_id,)).fetchone()
    if not reader:
        return

    current_score = reader['CURRENT_CREDIT']
    new_score = current_score + delta

    # 2. 范围限制 0 - 100
    if new_score > 100:
        new_score = 100
    elif new_score < 0:
        new_score = 0

    # 3. 如果分数有变化，执行更新和日志
    if new_score != current_score:
        db.execute("UPDATE READER SET CURRENT_CREDIT = ? WHERE READER_ID = ?", (new_score, reader_id))

        # 记录实际变动值
        real_delta = new_score - current_score
        db.execute("INSERT INTO CREDIT_LOG (READER_ID, CHANGE_VAL, REASON, OPERATOR) VALUES (?, ?, ?, ?)",
                   (reader_id, real_delta, reason, operator_name))


@bp.route('/history')
@permission_required('access_services')
def history():
    db = get_db()
    user_id = session.get('user_id')

    # 获取用户信用分，用于前端判断是否允许申请延期
    reader = db.execute("SELECT CURRENT_CREDIT FROM READER WHERE READER_ID=?", (user_id,)).fetchone()
    current_credit = reader['CURRENT_CREDIT'] if reader else 0

    records = db.execute('''
        SELECT b.*, h.BOOK_NAME, h.AUTHOR, h.CALL_NUMBER, e.STATUS as APP_STATUS
        FROM BORROW_RECORD b
        JOIN CIRCULATION_DETAIL d ON b.BARCODE = d.BARCODE
        JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN
        LEFT JOIN EXTENSION_APP e ON b.BORROW_ID = e.BORROW_ID
        WHERE b.READER_ID = ?
        ORDER BY b.BORROW_DATE DESC
    ''', (user_id,)).fetchall()

    return render_template('circ/history.html', records=records, current_credit=current_credit)


@bp.route('/extend', methods=['POST'])
@permission_required('access_services')
def apply_extension():
    borrow_id = request.form['borrow_id']
    days = int(request.form.get('days', 30))
    reason = request.form.get('reason', '')
    user_id = session.get('user_id')
    db = get_db()

    # --- 规则：信用分 < 80 不可延期 ---
    reader = db.execute("SELECT CURRENT_CREDIT FROM READER WHERE READER_ID=?", (user_id,)).fetchone()
    if reader['CURRENT_CREDIT'] < 80:
        flash(f'申请失败：您的信用分为 {reader["CURRENT_CREDIT"]} (低于80分)，暂停延期权限。', 'error')
        return redirect(url_for('circ.history'))

    record = db.execute("SELECT * FROM BORROW_RECORD WHERE BORROW_ID=?", (borrow_id,)).fetchone()
    if not record or record['STATUS'] != 1:
        flash('无法申请：记录不存在或图书已归还', 'error')
        return redirect(url_for('circ.history'))

    exist = db.execute("SELECT * FROM EXTENSION_APP WHERE BORROW_ID=?", (borrow_id,)).fetchone()
    if exist:
        flash('该订单已提交过申请，请勿重复提交', 'warning')
    else:
        db.execute(
            "INSERT INTO EXTENSION_APP (READER_ID, BORROW_ID, APPLY_DAYS, REASON, STATUS) VALUES (?, ?, ?, ?, 0)",
            (user_id, borrow_id, days, reason))
        db.commit()
        flash('延期申请已提交，请等待管理员审核。', 'success')
    return redirect(url_for('circ.history'))


@bp.route('/reserve', methods=['POST'])
@permission_required('access_services')
def reserve():
    isbn = request.form['isbn']
    reader_id = session.get('user_id')
    db = get_db()

    reader = db.execute("SELECT * FROM READER WHERE READER_ID=?", (reader_id,)).fetchone()

    # --- 规则：信用分 < 90 不可预约 ---
    if reader['CURRENT_CREDIT'] < 90:
        flash(f'预约失败：您的信用分为 {reader["CURRENT_CREDIT"]} (低于90分)，暂停预约权限。', 'error')
        return redirect(url_for('main.book_detail', isbn=isbn))

    # --- 规则：每人只能同时预约一本 ---
    # 查询状态为 1(排队中) 或 2(已分配待取) 的预约记录
    active_reserve = db.execute(
        "SELECT COUNT(*) FROM RESERVE_INFO WHERE READER_ID=? AND STATUS IN (1, 2)",
        (reader_id,)
    ).fetchone()[0]

    if active_reserve >= 1:
        flash('预约失败：您当前已有 1 本正在进行中的预约。请先完成借阅或取消现有预约。', 'error')
        return redirect(url_for('main.book_detail', isbn=isbn))

    # 检查是否有在馆复本 (有书不能预约，直接去借)
    available_count = \
    db.execute("SELECT COUNT(*) FROM CIRCULATION_DETAIL WHERE ISBN=? AND STATUS=1", (isbn,)).fetchone()[0]
    if available_count > 0:
        flash('预约失败：该书目前有在馆复本，请直接前往架位借阅。', 'warning')
        return redirect(url_for('main.book_detail', isbn=isbn))

    # 检查是否重复预约同一本
    exist = db.execute("SELECT * FROM RESERVE_INFO WHERE READER_ID=? AND ISBN=? AND (STATUS=1 OR STATUS=2)",
                       (reader_id, isbn)).fetchone()
    if exist:
        flash('您已在排队预约该书，请勿重复提交。', 'error')
        return redirect(url_for('main.book_detail', isbn=isbn))

    expire_time = datetime.datetime.now() + datetime.timedelta(days=60)
    db.execute("INSERT INTO RESERVE_INFO (READER_ID, ISBN, EXPIRE_DATE, STATUS) VALUES (?, ?, ?, 1)",
               (reader_id, isbn, expire_time))
    db.commit()
    flash('预约成功！当有复本归还时，系统将通知您取书。', 'success')
    return redirect(url_for('main.book_detail', isbn=isbn))


@bp.route('/workbench', methods=('GET', 'POST'))
@permission_required('manage_circulation')
def workbench():
    db = get_db()

    # --- 延期审批 ---
    if request.method == 'POST' and request.form.get('action') == 'review_extension':
        app_id = request.form['app_id']
        decision = request.form['decision']
        app_record = db.execute("SELECT * FROM EXTENSION_APP WHERE APP_ID=?", (app_id,)).fetchone()

        if decision == 'approve':
            borrow_rec = db.execute("SELECT * FROM BORROW_RECORD WHERE BORROW_ID=?",
                                    (app_record['BORROW_ID'],)).fetchone()
            new_due = borrow_rec['DUE_DATE'] + datetime.timedelta(days=app_record['APPLY_DAYS'])
            db.execute("UPDATE BORROW_RECORD SET DUE_DATE=? WHERE BORROW_ID=?", (new_due, app_record['BORROW_ID']))
            db.execute("UPDATE EXTENSION_APP SET STATUS=1 WHERE APP_ID=?", (app_id,))
            flash(f'已批准延期。', 'success')
        elif decision == 'reject':
            db.execute("UPDATE EXTENSION_APP SET STATUS=2 WHERE APP_ID=?", (app_id,))
            flash('已拒绝该延期申请。', 'warning')
        db.commit()
        return redirect(url_for('circ.workbench'))

    # --- 借还/报损 ---
    if request.method == 'POST':
        action = request.form.get('action')
        barcode = request.form.get('barcode', '').strip()

        # 1. 报损逻辑
        if action == 'report_damage':
            reason = request.form.get('reason', '图书破损/丢失')
            book = db.execute("""
                SELECT d.*, h.BOOK_NAME, h.ISBN 
                FROM CIRCULATION_DETAIL d 
                JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN 
                WHERE d.BARCODE=?
            """, (barcode,)).fetchone()

            if book:
                db.execute("""
                    INSERT INTO BOOK_DAMAGE_LOG (BARCODE, BOOK_NAME, ISBN, REASON, HANDLER) 
                    VALUES (?, ?, ?, ?, ?)
                """, (barcode, book['BOOK_NAME'], book['ISBN'], reason, session['user_name']))
                db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=4 WHERE BARCODE=?", (barcode,))

                borrow_rec = db.execute("SELECT * FROM BORROW_RECORD WHERE BARCODE=? AND STATUS=1",
                                        (barcode,)).fetchone()
                if borrow_rec:
                    db.execute("UPDATE BORROW_RECORD SET STATUS=2, RETURN_DATE=? WHERE BORROW_ID=?",
                               (datetime.datetime.now(), borrow_rec['BORROW_ID']))
                    flash(f'图书 {barcode} 已标记为报损，关联借阅记录已强制归还。', 'warning')
                else:
                    flash(f'图书 {barcode} 已标记为报损/销毁。', 'success')
                db.commit()
            else:
                flash('找不到该条码的图书。', 'error')

        # 2. 归还逻辑 (含逾期扣分 & 预约触发)
        elif action == 'return':
            record = db.execute("SELECT * FROM BORROW_RECORD WHERE BARCODE=? AND STATUS=1", (barcode,)).fetchone()
            book_detail = db.execute("SELECT * FROM CIRCULATION_DETAIL WHERE BARCODE=?", (barcode,)).fetchone()
            if record:
                now = datetime.datetime.now()
                # --- 规则：超期自动扣分 (固定扣10分) ---
                overdue_days = 0
                msg_prefix = "归还成功"

                if now > record['DUE_DATE']:
                    overdue_days = (now - record['DUE_DATE']).days
                    # 调用辅助函数扣分
                    update_user_credit(db, record['READER_ID'], -10, f"图书逾期{overdue_days}天归还",
                                       session['user_name'])
                    db.execute("UPDATE BORROW_RECORD SET RETURN_DATE=?, STATUS=3 WHERE BORROW_ID=?",
                               (now, record['BORROW_ID']))
                    msg_prefix = f"归还成功 (已逾期{overdue_days}天，自动扣除信用分 10 分)"
                else:
                    db.execute("UPDATE BORROW_RECORD SET RETURN_DATE=?, STATUS=2 WHERE BORROW_ID=?",
                               (now, record['BORROW_ID']))

                # 预约分配逻辑
                isbn = book_detail['ISBN']
                reserve = db.execute(
                    "SELECT * FROM RESERVE_INFO WHERE ISBN=? AND STATUS=1 ORDER BY RESERVE_DATE ASC LIMIT 1",
                    (isbn,)).fetchone()

                if reserve:
                    # 将书的状态改为3 (预约保留)
                    db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=3 WHERE BARCODE=?", (barcode,))
                    # 更新预约记录：状态变为2 (已分配/待取)，记录分配时间
                    db.execute("UPDATE RESERVE_INFO SET STATUS=2, BARCODE=?, EXPIRE_DATE=? WHERE RESERVE_ID=?",
                               (barcode, now + datetime.timedelta(days=3), reserve['RESERVE_ID']))

                    flash(
                        f'{msg_prefix}。**触发预约：请保留给读者 {reserve["READER_ID"]}！(保留至 {(now + datetime.timedelta(days=3)).strftime("%m-%d")})**',
                        'warning')
                else:
                    db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=1 WHERE BARCODE=?", (barcode,))
                    flash(f'{msg_prefix}。', 'success')
                db.commit()
            else:
                flash(f'图书 {barcode} 未借出或条码错误', 'error')

        # 3. 借阅逻辑 (含信用分门槛 & 数量限制)
        elif action == 'borrow':
            reader_id = request.form['reader_id'].strip()
            book = db.execute("SELECT * FROM CIRCULATION_DETAIL WHERE BARCODE=?", (barcode,)).fetchone()
            reader = db.execute("SELECT * FROM READER WHERE READER_ID=?", (reader_id,)).fetchone()

            error = None
            if not book:
                error = '图书条码不存在'
            elif not reader:
                error = '读者ID不存在'
            else:
                credit = reader['CURRENT_CREDIT']

                # --- 规则：信用分 < 60 禁止借阅 ---
                if credit < 60:
                    error = f'借阅被拒：读者信用分 ({credit}) 低于60分。'

                else:
                    # --- 规则：借阅数量限制 ---
                    # < 70分：限2本； >= 70分：限5本
                    max_books = 2 if credit < 70 else 5

                    current_borrow_count = db.execute(
                        "SELECT COUNT(*) FROM BORROW_RECORD WHERE READER_ID=? AND STATUS=1",
                        (reader_id,)
                    ).fetchone()[0]

                    if current_borrow_count >= max_books:
                        error = f'借阅被拒：当前已借 {current_borrow_count} 本，读者上限为 {max_books} 本 (信用分: {credit})。'

            if not error and book['STATUS'] == 4:
                error = '图书已报损，不可借阅'
            elif not error and book['STATUS'] == 3:
                # 检查是否是该读者预约的这本书
                res = db.execute("SELECT * FROM RESERVE_INFO WHERE BARCODE=? AND READER_ID=? AND STATUS=2",
                                 (barcode, reader_id)).fetchone()
                if not res:
                    error = '该书已被他人预约'
                else:
                    # 完成预约：状态改为4 (已完成/失效历史)
                    db.execute("UPDATE RESERVE_INFO SET STATUS=4 WHERE RESERVE_ID=?", (res['RESERVE_ID'],))

            elif not error and book['STATUS'] != 1 and book['STATUS'] != 3:
                error = '图书状态不可借'

            if not error:
                due_date = datetime.datetime.now() + datetime.timedelta(days=30)
                db.execute(
                    "INSERT INTO BORROW_RECORD (READER_ID, BARCODE, BORROW_DATE, DUE_DATE, STATUS) VALUES (?, ?, ?, ?, 1)",
                    (reader_id, barcode, datetime.datetime.now(), due_date))
                db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=2 WHERE BARCODE=?", (barcode,))
                db.commit()
                flash(f'借阅成功 (当前已借: {current_borrow_count + 1}/{max_books})', 'success')
            else:
                flash(error, 'error')

    pending_apps = db.execute(
        '''SELECT a.*, r.NAME as READER_NAME, h.BOOK_NAME FROM EXTENSION_APP a JOIN READER r ON a.READER_ID = r.READER_ID JOIN BORROW_RECORD b ON a.BORROW_ID = b.BORROW_ID JOIN CIRCULATION_DETAIL d ON b.BARCODE = d.BARCODE JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN WHERE a.STATUS = 0''').fetchall()

    damage_logs = db.execute("SELECT * FROM BOOK_DAMAGE_LOG ORDER BY LOG_DATE DESC LIMIT 50").fetchall()

    return render_template('circ/workbench.html', pending_apps=pending_apps, damage_logs=damage_logs)