from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.models import get_db
from app.blueprints.auth import permission_required
from app.blueprints.circ import update_user_credit
import datetime

bp = Blueprint('sys_admin', __name__, url_prefix='/admin')


@bp.route('/users', methods=['GET', 'POST'])
@permission_required('manage_users')
def user_list():
    db = get_db()
    all_roles = db.execute('SELECT * FROM SYS_ROLE').fetchall()

    if request.method == 'POST':
        action = request.form.get('action')
        target_id = request.form['reader_id']

        if str(target_id) == '1001':
            flash('System Alert: 无法修改根超级管理员 (1001) 的权限。', 'error')
            return redirect(url_for('sys_admin.user_list'))

        if action == 'update_credit':
            # 兼容手动修改，也使用 helper 限制范围
            change_val = int(request.form['change_val'])
            reason = request.form['reason']
            update_user_credit(db, target_id, change_val, reason, session['user_name'])
            db.commit()
            flash(f'用户 {target_id} 信用分已更新。', 'success')

        elif action == 'update_role':
            if session.get('role_id') != 8:
                flash('权限不足：只有超级管理员可以任命管理员。', 'error')
            else:
                # --- 核心修改：角色任命限制逻辑 ---
                # 1. 获取目标用户当前信息
                target_user = db.execute("SELECT ROLE_ID, NAME FROM READER WHERE READER_ID = ?",
                                         (target_id,)).fetchone()

                if not target_user:
                    flash(f'用户 {target_id} 不存在。', 'error')
                else:
                    current_role_id = target_user['ROLE_ID']

                    # 规则：只有教职工 (3) 或者 已经是管理员 (4-8) 可以被任命/变更为管理员
                    # 如果是 访客(1) 或 学生(2)，则禁止提升
                    if current_role_id not in [3, 4, 5, 6, 7, 8]:
                        flash(
                            f'任命失败：用户 {target_user["NAME"]} ({target_id}) 当前身份为学生或访客，不可任命为管理员。仅限教职工。',
                            'error')
                    else:
                        new_role_id = int(request.form['new_role_id'])
                        db.execute("UPDATE READER SET ROLE_ID = ? WHERE READER_ID = ?", (new_role_id, target_id))
                        role_name = \
                        db.execute("SELECT ROLE_NAME FROM SYS_ROLE WHERE ROLE_ID=?", (new_role_id,)).fetchone()[0]
                        flash(f'用户 {target_id} 的角色已变更为：{role_name}', 'success')
                        db.commit()

        return redirect(url_for('sys_admin.user_list'))

    readers = db.execute('''
        SELECT r.*, ro.ROLE_NAME 
        FROM READER r 
        JOIN SYS_ROLE ro ON r.ROLE_ID = ro.ROLE_ID
        ORDER BY r.ROLE_ID DESC, r.READER_ID ASC
    ''').fetchall()

    return render_template('admin/user_list.html', readers=readers, all_roles=all_roles)


@bp.route('/maintenance', methods=['GET', 'POST'])
@permission_required('manage_users')
def maintenance():
    """
    系统维护与批处理任务面板
    模拟系统自动执行的任务：月度信用恢复、预约超期检查
    """
    db = get_db()

    if request.method == 'POST':
        task_type = request.form.get('task_type')

        # --- 任务1：预约超期扫描 ---
        # 规则：预约了书 (Status=2 已分配) 但3天没来取 -> 扣10分，取消预约
        if task_type == 'scan_reservation_expiry':
            now = datetime.datetime.now()
            # 查找状态为 2 (已分配) 且当前时间 > EXPIRE_DATE
            expired_reserves = db.execute("""
                SELECT * FROM RESERVE_INFO 
                WHERE STATUS = 2 AND EXPIRE_DATE < ?
            """, (now,)).fetchall()

            count = 0
            for res in expired_reserves:
                # 扣分
                update_user_credit(db, res['READER_ID'], -10, "预约违约：3天未取书", "System_Auto")
                # 更新预约状态为 4 (失效/违约)
                db.execute("UPDATE RESERVE_INFO SET STATUS=4 WHERE RESERVE_ID=?", (res['RESERVE_ID'],))
                # 释放图书：将图书状态从 3 (预约保留) 恢复为 1 (在馆)
                if res['BARCODE']:
                    db.execute("UPDATE CIRCULATION_DETAIL SET STATUS=1 WHERE BARCODE=?", (res['BARCODE'],))
                count += 1

            db.commit()
            flash(f'扫描完成：处理了 {count} 条违约预约记录。', 'success')

        # --- 任务2：月度信用恢复 ---
        # 规则：信用分 < 100 的用户，恢复 10 分 (不超过100)
        elif task_type == 'monthly_recovery':
            # 查找所有不满100分的用户
            readers = db.execute("SELECT READER_ID, CURRENT_CREDIT FROM READER WHERE CURRENT_CREDIT < 100").fetchall()
            count = 0
            for r in readers:
                update_user_credit(db, r['READER_ID'], 10, "月度信用自动恢复", "System_Auto")
                count += 1

            db.commit()
            flash(f'结算完成：已为 {count} 位用户恢复信用分。', 'success')

        return redirect(url_for('sys_admin.maintenance'))

    return render_template('admin/maintenance.html')