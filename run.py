from app import create_app, models
import os

app = create_app()

with app.app_context():
    if not os.path.exists(os.path.join(app.instance_path, 'library.db')):
        print("没有library.db,创建中")
        models.init_db()

    if not os.path.exists(os.path.join(app.instance_path, 'AI.db')):
        print("没有AI.db,创建中")
        models.init_ai_db()

    print("系统启动就绪，访问地址: http://127.0.0.1:5000")
    #print(">>> 若Host/Client链接李炅阳热点，局域网访问地址: http://192.168.255.85:5000")

if __name__ == '__main__':
    # host='0.0.0.0' 允许局域网访问
    app.run(host='0.0.0.0', debug=True, port=5000)