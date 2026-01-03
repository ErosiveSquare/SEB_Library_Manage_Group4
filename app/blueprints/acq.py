from flask import Blueprint, render_template, request, flash, session, redirect, url_for
from app.models import get_db
from app.blueprints.auth import login_required
import datetime

bp = Blueprint('acq', __name__, url_prefix='/acq')


# ... (保留原有的 suggestion 和 order_process 路由) ...

@bp.route('/suggestion', methods=('GET', 'POST'))
@login_required
def suggestion():
    # ... (保持之前的代码不变) ...
    db = get_db()
    if request.method == 'POST':
        book_name = request.form['book_name']
        isbn = request.form.get('isbn')
        author = request.form.get('author')
        publisher = request.form.get('publisher')
        db.execute(
            'INSERT INTO ACQ_SUGGESTION (READER_ID, BOOK_NAME, AUTHOR, ISBN, PUBLISHER, STATUS) VALUES (?, ?, ?, ?, ?, 0)',
            (session['user_id'], book_name, author, isbn, publisher))
        db.commit()
        flash('荐购提交成功！', 'success')
        return redirect(url_for('acq.suggestion'))

    history = db.execute('SELECT * FROM ACQ_SUGGESTION WHERE READER_ID = ? ORDER BY ACQ_ID DESC',
                         (session['user_id'],)).fetchall()
    return render_template('acq/suggestion.html', history=history)


@bp.route('/orders', methods=('GET', 'POST'))
@login_required
def order_process():
    # ... (保持之前的代码不变，但添加一个逻辑：生成订单时同时插入 ORDER_LINE) ...
    # 为了简化演示，我们假设点击生成订单时，在后台自动创建了一个模拟的 ORDER_HEAD 和 ORDER_LINE
    # 实际项目中这里应该有一个更复杂的表单来填价格和书商

    if not session.get('user_role') in [0, 2]:
        flash('权限不足', 'error')
        return redirect(url_for('main.dashboard'))

    db = get_db()
    if request.method == 'POST':
        selected_ids = request.form.getlist('selected_ids')
        if selected_ids:
            # 1. 创建订单头 (模拟)
            db.execute("INSERT INTO ORDER_HEAD (PURCHASER, ORDER_DATE, SUPPLIER_ID, TOTAL_PRICE) VALUES (?, ?, 1, 0)",
                       (session['user_name'], datetime.datetime.now()))
            order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # 2. 处理每一条荐购 -> 转为订单行
            for acq_id in selected_ids:
                # 获取荐购信息
                sug = db.execute("SELECT * FROM ACQ_SUGGESTION WHERE ACQ_ID=?", (acq_id,)).fetchone()
                # 插入 ORDER_LINE (状态0: 未到货)
                db.execute('''
                    INSERT INTO ORDER_LINE (ORDER_NO, SUGGESTION_ID, BOOK_NAME, ISBN, AUTHOR, PUBLISHER, PRICE, QUANTITY, STATUS)
                    VALUES (?, ?, ?, ?, ?, ?, 50.00, 1, 0)
                ''', (order_id, acq_id, sug['BOOK_NAME'], sug['ISBN'], sug['AUTHOR'], sug['PUBLISHER']))

                # 更新荐购状态
                db.execute('UPDATE ACQ_SUGGESTION SET STATUS = 1 WHERE ACQ_ID = ?', (acq_id,))

            db.commit()
            flash(f'订单 #{order_id} 已生成，等待到货验收。', 'success')
        else:
            flash('请先选择条目', 'error')

    pending_list = db.execute(
        'SELECT s.*, r.NAME as READER_NAME FROM ACQ_SUGGESTION s JOIN READER r ON s.READER_ID = r.READER_ID WHERE s.STATUS = 0').fetchall()
    return render_template('acq/order_process.html', pending_list=pending_list)


# --- 新增：验收与入库 (Arrival Check) ---
@bp.route('/arrival', methods=('GET', 'POST'))
@login_required
def arrival_check():
    # SDD 1.1.3 验收 / 1.1.4 退货 / 1.2 编目入库
    if not session.get('user_role') in [0, 2]:
        return redirect(url_for('main.dashboard'))

    db = get_db()

    if request.method == 'POST':
        line_id = request.form['line_id']
        action = request.form['action']  # 'accept' or 'return'

        line = db.execute("SELECT * FROM ORDER_LINE WHERE LINE_ID=?", (line_id,)).fetchone()

        if action == 'accept':
            # 1. 写入验收清单 ACCEPT_LIST
            db.execute("INSERT INTO ACCEPT_LIST (LINE_ID, QUANTITY, CHECK_MAN, CHECK_DATE) VALUES (?, ?, ?, ?)",
                       (line_id, line['QUANTITY'], session['user_name'], datetime.datetime.now()))

            # 2. 更新订单行状态 -> 1:已验收
            db.execute("UPDATE ORDER_LINE SET STATUS=1 WHERE LINE_ID=?", (line_id,))

            # 3. [自动化] 简化版编目入库：直接根据ISBN写入 CIRCULATION_HEAD 和 CIRCULATION_DETAIL
            # 3.1 检查/插入 头表
            exist_head = db.execute("SELECT * FROM CIRCULATION_HEAD WHERE ISBN=?", (line['ISBN'],)).fetchone()
            if not exist_head:
                # 如果没有，插入头表 (模拟自动生成索书号)
                call_num = f"TP311/{line['ISBN'][-4:]}"
                db.execute(
                    "INSERT INTO CIRCULATION_HEAD (ISBN, CALL_NUMBER, BOOK_NAME, AUTHOR, CLC_CODE) VALUES (?, ?, ?, ?, ?)",
                    (line['ISBN'], call_num, line['BOOK_NAME'], line['AUTHOR'], 'TP311'))

            # 3.2 插入明细表 (生成条码)
            # 条码规则：ISBN + 时间戳后4位 (模拟)
            barcode = f"{line['ISBN']}-{datetime.datetime.now().strftime('%M%S')}"
            db.execute("INSERT INTO CIRCULATION_DETAIL (BARCODE, ISBN, LOCATION, STATUS) VALUES (?, ?, ?, 1)",
                       (barcode, line['ISBN'], '一楼流通库'))

            flash(f'《{line["BOOK_NAME"]}》验收成功！已自动编目入库，条码: {barcode}', 'success')

        elif action == 'return':
            # 1. 写入退货清单 RETURN_LIST
            reason = request.form.get('reason', '质量不合格')
            db.execute(
                "INSERT INTO RETURN_LIST (LINE_ID, QUANTITY, REASON, HANDLER, RETURN_DATE) VALUES (?, ?, ?, ?, ?)",
                (line_id, line['QUANTITY'], reason, session['user_name'], datetime.datetime.now()))

            # 2. 更新订单行状态 -> 2:已退货
            db.execute("UPDATE ORDER_LINE SET STATUS=2 WHERE LINE_ID=?", (line_id,))
            flash(f'《{line["BOOK_NAME"]}》已退货处理。', 'warning')

        db.commit()

    # 获取所有状态为0 (未到货) 的订单行
    orders = db.execute('''
        SELECT l.*, h.ORDER_DATE 
        FROM ORDER_LINE l 
        JOIN ORDER_HEAD h ON l.ORDER_NO = h.ORDER_NO 
        WHERE l.STATUS = 0
    ''').fetchall()

    return render_template('acq/arrival.html', orders=orders)