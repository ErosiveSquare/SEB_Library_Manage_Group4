import os

class Config:
    SECRET_KEY = 'dev'
    # 核心业务数据库 (图书、借阅等)
    DATABASE = os.path.join(os.getcwd(), 'instance', 'library.db')
    # AI 助手数据库 (存储对话历史)
    AI_DATABASE = os.path.join(os.getcwd(), 'instance', 'AI.db')
    # 硅基流动 (SiliconCloud) API 配置
    LLM_API_KEY = 'sk-gpgfpqxmrxythmzrgktgeqdudtluqigwrnjssrbqegxzfyax'
    LLM_BASE_URL = 'https://api.siliconflow.cn/v1'

    #LLM_MODEL_NAME = 'deepseek-ai/DeepSeek-R1-0528-Qwen3-8B'
    LLM_MODEL_NAME = 'Qwen/Qwen3-8B'