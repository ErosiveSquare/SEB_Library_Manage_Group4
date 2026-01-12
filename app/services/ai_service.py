from flask import current_app
from app.models import get_ai_db
from openai import OpenAI


class AIService:
    def __init__(self):
        # 初始化 SiliconCloud 客户端
        self.client = OpenAI(
            api_key=current_app.config['LLM_API_KEY'],
            base_url=current_app.config['LLM_BASE_URL']
        )
        # 使用配置中的模型名称
        self.model = current_app.config['LLM_MODEL_NAME']

    def get_history(self, user_id, limit=20):
        """获取最近的对话历史，用于构建上下文"""
        db = get_ai_db()
        cursor = db.execute('''
            SELECT * FROM CHAT_MESSAGE 
            WHERE USER_ID = ? 
            ORDER BY CREATED_AT DESC LIMIT ?
        ''', (str(user_id), limit))
        rows = cursor.fetchall()
        # 数据库查出来是倒序(最新在前)，转回正序(时间顺序)给AI
        return list(reversed(rows))

    def save_message(self, user_id, role, content):
        """保存消息到 AI.db"""
        db = get_ai_db()
        db.execute('''
            INSERT INTO CHAT_MESSAGE (USER_ID, ROLE, CONTENT) 
            VALUES (?, ?, ?)
        ''', (str(user_id), role, content))
        db.commit()

    def chat(self, user_id, user_input):
        """核心对话逻辑"""
        # 1. 保存用户的提问
        self.save_message(user_id, 'user', user_input)

        # 2. 构建发送给 AI 的消息列表 (Context)
        # 获取最近 10 条历史记录，让 AI 拥有“记忆”
        history = self.get_history(user_id, limit=10)

        messages = [
            {
                "role": "system",
                "content": """你是华北电力大学图书馆的智能助手“华电小图”。
                              不能使用Markdown，只允许纯文本输出。
                              不要使用思考模式，必须一定要快速回答。
                              请用专业、亲切、简洁的语气回答读者关于图书借阅、检索、系统使用等问题。
                              不要回答与图书馆或学习无关的敏感政治问题。"""
            }
        ]

        for msg in history:
            # 过滤掉之前的 system 消息，只保留 user 和 assistant
            if msg['ROLE'] in ['user', 'assistant']:
                messages.append({"role": msg['ROLE'], "content": msg['CONTENT']})

        # 3. 调用 SiliconCloud API
        ai_reply = ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # 创造性控制
                max_tokens=512  # 限制回复长度，避免废话
            )
            ai_reply = response.choices[0].message.content
        except Exception as e:
            print(f"AI API Error: {e}")
            ai_reply = "抱歉，AI 连接出现问题，请稍后再试。(错误信息: API连接失败)"

        # 4. 保存 AI 的回复
        self.save_message(user_id, 'assistant', ai_reply)

        return ai_reply