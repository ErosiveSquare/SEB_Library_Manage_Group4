from flask import Blueprint, render_template, request, flash, session, redirect, url_for, jsonify
from app.models import get_db, CLC_DATA
from app.blueprints.auth import permission_required
from app.services.map_service import MapService
import datetime
import random

bp = Blueprint('acq', __name__, url_prefix='/acq')

import requests  # 确保头部已导入 requests

@bp.route('/search_online', methods=['POST'])
@permission_required('access_services')
def search_online():
    """
    根据书名/作者在线反查 ISBN (基于 Open Library)
    """
    data = request.get_json()
    query = data.get('query', '').strip()

    if not query:
        return jsonify({'success': False, 'message': '搜索内容不能为空'})

    # 构造 Open Library 搜索请求
    # q=title:{query} 表示在标题中搜索，fields 指定返回字段以减少流量
    api_url = "https://openlibrary.org/search.json"
    params = {
        'q': query,
        'fields': 'title,author_name,isbn,publisher,first_publish_year,cover_i,language',
        'limit': 5  # 只取相关度最高的前5个结果
    }

    try:
        resp = requests.get(api_url, params=params, timeout=8)
        resp.raise_for_status()
        result = resp.json()

        if result.get('num_found', 0) == 0:
            return jsonify({'success': True, 'found': False, 'results': []})

        formatted_results = []
        for doc in result.get('docs', []):
            # 数据清洗：提取最有价值的信息

            # 1. 获取 ISBN (优先取 13位，如果没有则取 10位，取第一个)
            isbn_list = doc.get('isbn', [])
            best_isbn = ""
            if isbn_list:
                # 尝试找 978 开头的
                candidates = [i for i in isbn_list if i.startswith('978')]
                best_isbn = candidates[0] if candidates else isbn_list[0]

            # 2. 处理作者和出版社 (列表转字符串)
            authors = ", ".join(doc.get('author_name', []))
            publishers = ", ".join(doc.get('publisher', []))

            # 3. 封面图
            cover_id = doc.get('cover_i')
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-S.jpg" if cover_id else None

            formatted_results.append({
                'title': doc.get('title'),
                'author': authors,
                'isbn': best_isbn,
                'publisher': publishers,
                'year': doc.get('first_publish_year'),
                'cover': cover_url
            })

        return jsonify({'success': True, 'found': True, 'results': formatted_results})

    except Exception as e:
        print(f"OpenLibrary API Error: {e}")
        return jsonify({'success': False, 'message': '连接图书数据库超时，请稍后重试'})


@bp.route('/suggestion', methods=('GET', 'POST'))
@permission_required('access_services')
def suggestion():
    # ===== 1. 前置：校验用户登录态，无登录态直接拦截，杜绝KeyError =====
    if 'user_id' not in session:
        flash('请先登录后再进行图书荐购操作！', 'danger')
        return redirect(url_for('auth.login'))  # 跳转到你的登录页路由

    db = get_db()
    # ===== 定义常量，消除魔法值，提升可读性 =====
    STATUS_PENDING = 0  # 荐购待处理状态
    TABLE_NAME = 'ACQ_SUGGESTION'

    if request.method == 'POST':
        # ===== 2. 统一使用get+strip，所有字段去空格，杜绝硬取下标，避免KeyError =====
        book_name = request.form.get('book_name', '').strip()
        isbn = request.form.get('isbn', '').strip()
        author = request.form.get('author', '').strip()
        publisher = request.form.get('publisher', '').strip()
        reader_id = session['user_id']

        # ===== 3. 必填项非空校验，拦截空数据/纯空格 =====
        if not book_name:
            flash('图书名称为必填项，不能为空！', 'danger')
            return redirect(url_for('acq.suggestion'))
        if not author:
            flash('作者名称为必填项，不能为空！', 'danger')
            return redirect(url_for('acq.suggestion'))

        # ===== 4. ISBN格式校验：非空时校验为纯数字 =====
        if isbn and not isbn.isdigit():
            flash('ISBN格式错误，仅支持纯数字的ISBN编码！', 'danger')
            return redirect(url_for('acq.suggestion'))

        # ===== 5. 防重复提交校验：同用户+同图书+待处理状态 不重复提交 =====
        duplicate = db.execute(
            f'SELECT 1 FROM {TABLE_NAME} WHERE READER_ID = ? AND BOOK_NAME = ? AND AUTHOR = ? AND STATUS = ? LIMIT 1',
            (reader_id, book_name, author, STATUS_PENDING)
        ).fetchone()
        if duplicate:
            flash('该图书已提交荐购，请勿重复提交，耐心等待审核即可！', 'warning')
            return redirect(url_for('acq.suggestion'))

        # ===== 6. 数据库写操作：try-except捕获异常 + 事务回滚，保证数据一致性 =====
        try:
            db.execute(
                f'INSERT INTO {TABLE_NAME} (READER_ID, BOOK_NAME, AUTHOR, ISBN, PUBLISHER, STATUS) VALUES (?, ?, ?, ?, ?, ?)',
                (reader_id, book_name, author, isbn, publisher, STATUS_PENDING)
            )
            db.commit()
            flash('荐购提交成功！请耐心等待管理员审核处理。', 'success')
        except Exception as e:
            # 异常时强制回滚事务，避免脏数据
            db.rollback()
            # 打印异常日志，方便排查问题
            print(f'图书荐购入库失败：{str(e)}')
            flash('荐购提交失败，请稍后重试！', 'danger')
        finally:
            # 显式关闭游标，释放数据库资源
            db.close()

        return redirect(url_for('acq.suggestion'))

    # ===== GET请求：查询荐购历史 + 可选分页优化（推荐） =====
    # 分页参数：页码默认1，每页条数默认10
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    history = db.execute(
        f'SELECT * FROM {TABLE_NAME} WHERE READER_ID = ? ORDER BY ACQ_ID DESC LIMIT ? OFFSET ?',
        (session['user_id'], per_page, offset)
    ).fetchall()

    # 统计总条数，用于前端分页组件
    total = db.execute(
        f'SELECT COUNT(*) FROM {TABLE_NAME} WHERE READER_ID = ?',
        (session['user_id'],)
    ).fetchone()[0]

    return render_template('acq/suggestion.html', history=history, page=page, total=total, per_page=per_page)


@bp.route('/orders', methods=('GET', 'POST'))
@permission_required('manage_acq_order')
def order_process():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')

        # --- 2. 管理员手工添加订单 (无荐购) ---
        if action == 'manual_add':
            book_name = request.form['book_name']
            isbn = request.form.get('isbn', '').strip()
            author = request.form['author']
            publisher = request.form.get('publisher', '')

            # [修改] 移除价格输入，默认为 0.00
            price = 0.00
            quantity = int(request.form.get('quantity', 1))

            # 创建一个新订单头
            db.execute("INSERT INTO ORDER_HEAD (PURCHASER, ORDER_DATE, SUPPLIER_ID, TOTAL_PRICE) VALUES (?, ?, 1, ?)",
                       (session['user_name'], datetime.datetime.now(), price * quantity))
            order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            db.execute('''
                INSERT INTO ORDER_LINE (ORDER_NO, SUGGESTION_ID, BOOK_NAME, ISBN, AUTHOR, PUBLISHER, PRICE, QUANTITY, STATUS)
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 0)
            ''', (order_id, book_name, isbn, author, publisher, price, quantity))

            db.commit()
            flash(f'手工订单 #{order_id} 已创建。', 'success')
            return redirect(url_for('acq.order_process'))

        # --- 现有逻辑：处理荐购 ---
        selected_ids = request.form.getlist('selected_ids')
        if not selected_ids and action in ['create_order', 'reject']:
            flash('请先选择条目', 'error')
        else:
            if action == 'create_order':
                db.execute(
                    "INSERT INTO ORDER_HEAD (PURCHASER, ORDER_DATE, SUPPLIER_ID, TOTAL_PRICE) VALUES (?, ?, 1, 0)",
                    (session['user_name'], datetime.datetime.now()))
                order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                total_price = 0
                for acq_id in selected_ids:
                    sug = db.execute("SELECT * FROM ACQ_SUGGESTION WHERE ACQ_ID=?", (acq_id,)).fetchone()
                    qty_key = f"qty_{acq_id}"
                    quantity = int(request.form.get(qty_key, 1))
                    db.execute('''INSERT INTO ORDER_LINE (ORDER_NO, SUGGESTION_ID, BOOK_NAME, ISBN, AUTHOR, PUBLISHER, PRICE, QUANTITY, STATUS)
                                  VALUES (?, ?, ?, ?, ?, ?, 50.00, ?, 0)''',
                               (order_id, acq_id, sug['BOOK_NAME'], sug['ISBN'], sug['AUTHOR'], sug['PUBLISHER'],
                                quantity))
                    total_price += 50.00 * quantity
                    db.execute('UPDATE ACQ_SUGGESTION SET STATUS = 1 WHERE ACQ_ID = ?', (acq_id,))
                db.execute("UPDATE ORDER_HEAD SET TOTAL_PRICE=? WHERE ORDER_NO=?", (total_price, order_id))
                db.commit()
                flash(f'订单 #{order_id} 已生成。', 'success')
            elif action == 'reject':
                for acq_id in selected_ids:
                    db.execute('UPDATE ACQ_SUGGESTION SET STATUS = 2 WHERE ACQ_ID = ?', (acq_id,))
                db.commit()
                flash(f'已驳回 {len(selected_ids)} 条荐购申请。', 'warning')

    pending_list = db.execute(
        'SELECT s.*, r.NAME as READER_NAME FROM ACQ_SUGGESTION s JOIN READER r ON s.READER_ID = r.READER_ID WHERE s.STATUS = 0').fetchall()
    return render_template('acq/order_process.html', pending_list=pending_list)


@bp.route('/arrival', methods=('GET', 'POST'))
@permission_required('manage_acq_arrival')
def arrival_check():
    db = get_db()
    new_book_map = None

    if request.method == 'POST':
        line_id = request.form['line_id']
        action = request.form['action']
        line = db.execute("SELECT * FROM ORDER_LINE WHERE LINE_ID=?", (line_id,)).fetchone()

        if action == 'accept':
            manual_isbn = request.form['isbn'].strip()
            manual_clc = request.form['clc_code'].strip()
            manual_author = request.form['author'].strip()
            if not manual_isbn or not manual_clc:
                flash('编目失败：ISBN 和 分类号 必须填写', 'error')
                return redirect(url_for('acq.arrival_check'))

            auto_call_num = MapService.generate_call_number(manual_isbn, manual_clc, manual_author)
            db.execute("INSERT INTO ACCEPT_LIST (LINE_ID, QUANTITY, CHECK_MAN, CHECK_DATE) VALUES (?, ?, ?, ?)",
                       (line_id, line['QUANTITY'], session['user_name'], datetime.datetime.now()))
            db.execute("UPDATE ORDER_LINE SET STATUS=1, ISBN=? WHERE LINE_ID=?", (manual_isbn, line_id))

            exist_head = db.execute("SELECT * FROM CIRCULATION_HEAD WHERE ISBN=?", (manual_isbn,)).fetchone()
            if not exist_head:
                db.execute(
                    "INSERT INTO CIRCULATION_HEAD (ISBN, CALL_NUMBER, BOOK_NAME, AUTHOR, CLC_CODE) VALUES (?, ?, ?, ?, ?)",
                    (manual_isbn, auto_call_num, line['BOOK_NAME'], manual_author, manual_clc))
                flash(f'新书入库！索书号: {auto_call_num}', 'success')
            else:
                flash(f'复本入库。', 'success')
                auto_call_num = exist_head['CALL_NUMBER']

            for i in range(line['QUANTITY']):
                isbn_suffix = manual_isbn[-6:] if len(manual_isbn) > 6 else manual_isbn
                time_part = datetime.datetime.now().strftime('%M%S')
                rand_part = random.randint(100, 999)
                barcode = f"{isbn_suffix}-{time_part}-{rand_part}-{i}"
                db.execute("INSERT INTO CIRCULATION_DETAIL (BARCODE, ISBN, LOCATION, STATUS) VALUES (?, ?, ?, 1)",
                           (barcode, manual_isbn, '一楼流通库'))
            db.commit()
            new_book_map = MapService.get_map_data(target_isbn=manual_isbn)
            new_book_map['book_name'] = line['BOOK_NAME']
            new_book_map['call_no'] = auto_call_num

        # --- 3. 退货逻辑 (记录理由) ---
        elif action == 'return':
            reason = request.form.get('return_reason', '质量不合格')  # 获取弹窗填写的理由
            db.execute(
                "INSERT INTO RETURN_LIST (LINE_ID, QUANTITY, REASON, HANDLER, RETURN_DATE) VALUES (?, ?, ?, ?, ?)",
                (line_id, line['QUANTITY'], reason, session['user_name'], datetime.datetime.now()))
            db.execute("UPDATE ORDER_LINE SET STATUS=2 WHERE LINE_ID=?", (line_id,))
            if line['SUGGESTION_ID']:
                db.execute("UPDATE ACQ_SUGGESTION SET STATUS=2 WHERE ACQ_ID=?", (line['SUGGESTION_ID'],))
            flash(f'《{line["BOOK_NAME"]}》已退货。原因：{reason}', 'warning')
            db.commit()

    orders = db.execute(
        '''SELECT l.*, h.ORDER_DATE FROM ORDER_LINE l JOIN ORDER_HEAD h ON l.ORDER_NO = h.ORDER_NO WHERE l.STATUS = 0''').fetchall()
    return render_template('acq/arrival.html', orders=orders, clc_data=CLC_DATA, new_book_map=new_book_map)