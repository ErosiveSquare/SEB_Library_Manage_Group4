from flask import Blueprint, request, jsonify, session
from app.blueprints.auth import login_required
from app.services.ai_service import AIService

bp = Blueprint('ai', __name__, url_prefix='/ai')


@bp.route('/ask', methods=['POST'])
@login_required
def ask():
    # 获取当前登录用户 ID
    user_id = session.get('user_id')

    # 获取前端发送的 JSON 数据
    data = request.get_json()
    user_input = data.get('message', '').strip()

    if not user_input:
        return jsonify({'error': '内容不能为空'}), 400

    # 调用 Service 进行处理
    service = AIService()
    reply = service.chat(user_id, user_input)

    return jsonify({'reply': reply})


@bp.route('/history', methods=['GET'])
@login_required
def history():
    user_id = session.get('user_id')
    service = AIService()

    # 获取历史记录并转换为 JSON 格式返回给前端
    raw_history = service.get_history(user_id, limit=50)
    history_data = [
        {
            'role': row['ROLE'],
            'content': row['CONTENT'],
            'time': row['CREATED_AT'].strftime('%H:%M') if row['CREATED_AT'] else ''
        }
        for row in raw_history
    ]
    return jsonify({'history': history_data})