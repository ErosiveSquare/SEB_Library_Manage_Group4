from flask import Blueprint, request, jsonify, session
from app.models import get_db
from app.blueprints.auth import permission_required, login_required
import datetime

bp = Blueprint('notice', __name__, url_prefix='/notice')


@bp.route('/latest', methods=['GET'])
@login_required
def get_latest():
    db = get_db()
    role_id = session.get('role_id', 1)
    notices = db.execute('''SELECT * FROM NOTICE ORDER BY IS_TOP DESC, PUBLISH_DATE DESC LIMIT 20''').fetchall()
    data = []
    if role_id >= 4:
        messages = db.execute(
            '''SELECT m.*, r.NAME as READER_NAME FROM USER_MESSAGE m JOIN READER r ON m.READER_ID = r.READER_ID WHERE m.IS_READ = 0 ORDER BY m.CREATE_TIME DESC''').fetchall()
        for m in messages:
            data.append({'type': 'message', 'id': m['MSG_ID'], 'title': f"来自 {m['READER_NAME']} 的留言",
                         'content': m['CONTENT'], 'publisher': str(m['READER_ID']),
                         'date': m['CREATE_TIME'].strftime('%Y-%m-%d %H:%M'), 'is_top': 0, 'is_read': 0})
    for n in notices:
        data.append({'type': 'notice', 'id': n['NOTICE_ID'], 'title': n['TITLE'], 'content': n['CONTENT'],
                     'publisher': n['PUBLISHER_NAME'], 'date': n['PUBLISH_DATE'].strftime('%Y-%m-%d %H:%M'),
                     'is_top': n['IS_TOP']})
    data.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'notices': data})


@bp.route('/publish', methods=['POST'])
@permission_required('publish_notice')
def publish():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    is_top = 1 if data.get('is_top') else 0
    include_overdue = data.get('include_overdue', False)  # 新增参数

    if not title:
        return jsonify({'success': False, 'message': '标题不能为空'})

    db = get_db()

    # --- 核心：自动生成超期报表 ---
    if include_overdue:
        # 查询所有逾期记录
        overdue_records = db.execute('''
            SELECT b.*, r.NAME, h.BOOK_NAME 
            FROM BORROW_RECORD b
            JOIN READER r ON b.READER_ID = r.READER_ID
            JOIN CIRCULATION_DETAIL d ON b.BARCODE = d.BARCODE
            JOIN CIRCULATION_HEAD h ON d.ISBN = h.ISBN
            WHERE b.STATUS = 3 OR (b.STATUS = 1 AND b.DUE_DATE < CURRENT_TIMESTAMP)
        ''').fetchall()

        if overdue_records:
            table_html = "<br><hr><h3>📢 超期通报表 (System Generated)</h3>"
            table_html += "<table style='width:100%; border-collapse:collapse; font-size:13px; margin-top:10px;'>"
            table_html += "<tr style='background:#f3f4f6; text-align:left;'><th style='padding:8px;'>读者</th><th style='padding:8px;'>图书</th><th style='padding:8px;'>应还日期</th></tr>"

            for rec in overdue_records:
                due_str = rec['DUE_DATE'].strftime('%Y-%m-%d')
                table_html += f"<tr><td style='padding:8px; border-bottom:1px solid #eee;'>{rec['NAME']}({rec['READER_ID']})</td><td style='padding:8px; border-bottom:1px solid #eee;'>{rec['BOOK_NAME']}</td><td style='padding:8px; border-bottom:1px solid #eee; color:red;'>{due_str}</td></tr>"

            table_html += "</table>"
            content += table_html  # 将表格追加到内容中
        else:
            content += "<br><hr><p style='color:#10b981;'>🎉 目前没有超期记录。</p>"

    db.execute("INSERT INTO NOTICE (TITLE, CONTENT, PUBLISHER_NAME, IS_TOP) VALUES (?, ?, ?, ?)",
               (title, content, session.get('user_name'), is_top))
    db.commit()
    return jsonify({'success': True})


@bp.route('/leave_message', methods=['POST'])
@login_required
def leave_message():
    data = request.get_json()
    content = data.get('content')
    if not content: return jsonify({'success': False, 'message': '内容不能为空'})
    db = get_db()
    db.execute("INSERT INTO USER_MESSAGE (READER_ID, CONTENT) VALUES (?, ?)", (session['user_id'], content))
    db.commit()
    return jsonify({'success': True})


@bp.route('/read_message', methods=['POST'])
@permission_required('access_dashboard')
def read_message():
    data = request.get_json()
    msg_id = data.get('msg_id')
    db = get_db()
    db.execute("UPDATE USER_MESSAGE SET IS_READ = 1 WHERE MSG_ID = ?", (msg_id,))
    db.commit()
    return jsonify({'success': True})