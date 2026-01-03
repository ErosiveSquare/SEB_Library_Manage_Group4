from app import create_app, models
import os
app = create_app()

# 首次运行时自动初始化数据库
with app.app_context():
    if not os.path.exists(os.path.join(app.instance_path, 'library.db')):
        print("Database not found. Initializing...")
        models.init_db()
        print("Database initialized with schema v2.")

if __name__ == '__main__':
    app.run(debug=True, port=5000)