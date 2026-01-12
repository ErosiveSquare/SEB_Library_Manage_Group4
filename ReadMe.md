<div align="center">
  <img src="app/static/asset/NCEPU_LIB.png" width="120" alt="NCEPU Library Logo">
  <h1>NCEPU Library OS</h1>
  <h3>华北电力大学 · 下一代智慧图书馆管理系统</h3>

  <p>
    <b>数字孪生 (Digital Twin)</b> • <b>生成式 AI (GenAI)</b> • <b>iOS 极致美学</b>
  </p>

  <p>
    <a href="#-核心特性">核心特性</a> •
    <a href="#-技术栈">技术栈</a> •
    <a href="#-UI-设计哲学">UI 设计</a> •
    <a href="#-快速开始">快速开始</a> •
    <a href="#-系统运维">运维中台</a>
  </p>

  <img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-2.3-green?style=flat-square&logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/SQLite-Integrated-003B57?style=flat-square&logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/LLM-SiliconFlow-purple?style=flat-square&logo=openai" alt="LLM">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
</div>

---

## 📖 项目简介 (Introduction)

**NCEPU Library OS** 是一款专为高校设计的现代化图书管理系统。不同于传统的管理软件，本项目在保证业务逻辑严密性的基础上，引入了**数字孪生可视化**与**大模型智能问答**技术，并采用了类 Apple iOS 的 **Glassmorphism (磨砂玻璃)** 设计语言，旨在提供极致的用户体验。

系统集成了 **采访 (Acquisition)**、**编目 (Cataloging)**、**流通 (Circulation)**、**典藏 (Collection)** 四大核心业务，并配套了独立的**运维中台 (Ops System)** 用于数据治理与灾备。

## ✨ 核心特性 (Key Features)

### 🧠 智能化与可视化
- **🗺️ 数字孪生馆藏地图**: 基于 Canvas 的网格化地图引擎，实时渲染馆藏热力分布，支持楼层切换与书架定位导航。
- **🤖 AI 智能馆员 "华电小图"**: 集成 SiliconFlow API (Qwen/DeepSeek)，支持自然语言查书、规章咨询及闲聊，具备上下文记忆能力。
- **📊 动态数据大屏**: 实时展示借阅趋势、馆藏分类占比 (Chart.js)、入库新书轮播及动态时钟。

### 🛡️ 严密的业务逻辑
- **🔐 RBAC 权限控制体系**: 
  - 支持 **5级** 角色：访客、学生、教职工、各级管理员（采编/流通/用户管理）、超级管理员。
  - 细粒度权限装饰器 (`@permission_required`) 确保接口安全。
- **💳 信用分博弈机制**: 
  - 建立用户信用档案，逾期、违约自动扣分。
  - 信用分直接挂钩借阅权限（如 <80分禁止延期，<60分禁止借阅）。
- **📚 采访与编目流**: 
  - 支持 OpenLibrary API 在线反查 ISBN，自动回填元数据。
  - 完整的“读者荐购 -> 审批 -> 生成订单 -> 验收编目 -> 上架”闭环。

### 🎨 现代化交互
- **全站 AJAX 异步交互**: 搜索、借还、弹窗均无刷新，体验丝般顺滑。
- **响应式 iOS 风格**: 统一的圆角、阴影、磨砂玻璃背景，适配高分屏。

## 🛠 技术栈 (Tech Stack)

| 领域         | 技术/库          | 说明                                    |
| :----------- | :--------------- | :-------------------------------------- |
| **Backend**  | Python 3, Flask  | 核心 Web 框架，Blueprints 模块化设计    |
| **Database** | SQLite3          | 原生 SQL 操作，包含事务控制与 JSON 存储 |
| **Frontend** | HTML5, CSS3, JS  | 纯手写 iOS 风格组件库，无重型框架依赖   |
| **AI / LLM** | OpenAI SDK       | 接入 SiliconFlow (Qwen/DeepSeek) 模型   |
| **Charts**   | Chart.js         | 数据可视化图表                          |
| **Ops**      | Flask (独立实例) | 独立的运维与备份子系统                  |

## 🎨 UI 设计哲学 (Design Philosophy)

本项目遵循 **"Content First"** 与 **"Glassmorphism"** 设计理念：

> "好的设计是显而易见的，伟大的设计是透明的。"

* **视觉层级**: 使用透明度与模糊 (Backdrop Filter) 区分层级，而非简单的边框。
* **交互反馈**: 按钮、输入框具备细腻的 Hover/Focus 动效与阴影变化。
* **布局**: 采用 `Bento Grid` (便当盒) 风格的仪表盘布局，信息密度高且不杂乱。

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
确保已安装 Python 3.9+。

```bash
# 克隆仓库
git clone [https://github.com/YourUsername/LibraryManage.git](https://github.com/YourUsername/LibraryManage.git)
cd LibraryManage

# 创建并激活虚拟环境 (推荐)
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 安装依赖 (建议手动创建 requirements.txt 或安装以下核心包)
pip install flask requests openai
```

### 2. 配置说明

修改 `config.py` 中的 API Key (推荐使用环境变量，不要直接提交到仓库)：

```python
class Config:
    # 替换为你自己的 SiliconFlow 或 OpenAI API Key
    LLM_API_KEY = os.getenv('LLM_API_KEY', 'sk-xxxxxxxx')
```

### 3. 初始化与运行

项目会自动检测并初始化数据库 (`library.db` 和 `AI.db`)。

```bash
# 启动主系统 (默认端口 5000)
python run.py
```

访问浏览器：`http://127.0.0.1:5000`

- **默认超管账号**: `1001`
- **默认密码**: `admin123`

## 🔧 运维中台 (Ops System)

本项目包含一个独立的运维子系统，用于数据库热备份、日志审计和数据修正。

```bash
# 启动运维系统 (默认端口 5001)
python OpsSystem/run_ops.py
```

访问：`http://127.0.0.1:5001`

- **注册密钥**: 每日动态生成（查看控制台输出或算法生成 `MD5(Date + Salt)`）
- **功能**: 全量代码 ZIP 归档、SQL 数据库一键备份、表级数据增删改查。

## 📂 项目目录结构

```plaintext
LibraryManage
├── app
│   ├── blueprints      # 蓝图 (业务逻辑模块)
│   │   ├── acq.py      # 采访与编目
│   │   ├── circ.py     # 流通与借阅
│   │   ├── ai.py       # AI 助手接口
│   │   └── ...
│   ├── services        # 核心服务层
│   │   ├── map_service.py  # 地图算法与热力图生成
│   │   └── ai_service.py   # LLM 对话封装
│   ├── static          # 静态资源 (CSS/JS/Images)
│   ├── templates       # Jinja2 模板 (前端页面)
│   └── models.py       # 数据库模型与初始化
├── OpsSystem           # 独立运维系统
├── instance            # 数据库存储目录 (自动生成)
├── config.py           # 全局配置
└── run.py              # 启动入口
```

## 🤝 贡献与许可 (Contribution & License)

欢迎提交 Issue 或 Pull Request 来改进本项目。

本项目采用 **MIT License** 开源许可。Copyright © 2026 NCEPU Group 4.

------

<div align="center">Made with ❤️ by 华北电力大学软件工程课程设计小组</div>