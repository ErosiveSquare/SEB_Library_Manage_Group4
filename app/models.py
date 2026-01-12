import sqlite3
import os
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def get_ai_db():
    if 'ai_db' not in g:
        g.ai_db = sqlite3.connect(
            current_app.config['AI_DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.ai_db.row_factory = sqlite3.Row
    return g.ai_db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
    ai_db = g.pop('ai_db', None)
    if ai_db is not None:
        ai_db.close()


def init_db():
    """初始化数据库表结构 (含报损、退货增强)"""
    db = get_db()

    # --- 1. 基础业务表 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS SUPPLIER (
        SUPPLIER_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        NAME VARCHAR(100), ADDRESS VARCHAR(200), CONTACT_PERSON VARCHAR(50), 
        TELEPHONE VARCHAR(20), BANK_NAME VARCHAR(100), BANK_ACCOUNT VARCHAR(50), 
        CREDIT_LEVEL CHAR(1), EMAIL VARCHAR(100)
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS ACQ_SUGGESTION (
        ACQ_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        READER_ID INTEGER, BOOK_NAME VARCHAR(100), AUTHOR VARCHAR(50), 
        ISBN VARCHAR(20), PUBLISHER VARCHAR(100), STATUS INTEGER DEFAULT 0
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS ORDER_HEAD (
        ORDER_NO INTEGER PRIMARY KEY AUTOINCREMENT,
        PURCHASER VARCHAR(50), ORDER_DATE TIMESTAMP, SUPPLIER_ID INTEGER, TOTAL_PRICE DECIMAL(12,2)
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS ORDER_LINE (
        LINE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        ORDER_NO INTEGER, SUGGESTION_ID INTEGER, BOOK_NAME VARCHAR(100), 
        ISBN VARCHAR(20), AUTHOR VARCHAR(50), PUBLISHER VARCHAR(100), 
        PRICE DECIMAL(10,2), QUANTITY INTEGER, STATUS INTEGER,
        FOREIGN KEY (ORDER_NO) REFERENCES ORDER_HEAD(ORDER_NO)
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS ACCEPT_LIST (
        ACCEPT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        LINE_ID INTEGER, QUANTITY INTEGER, CHECK_MAN VARCHAR(50), CHECK_DATE TIMESTAMP
    );''')

    # 退货记录表
    db.execute('''
    CREATE TABLE IF NOT EXISTS RETURN_LIST (
        RETURN_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        LINE_ID INTEGER, QUANTITY INTEGER, REASON VARCHAR(200), HANDLER VARCHAR(50), RETURN_DATE TIMESTAMP
    );''')

    # 图书报损/销毁记录表
    db.execute('''
    CREATE TABLE IF NOT EXISTS BOOK_DAMAGE_LOG (
        LOG_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        BARCODE VARCHAR(20),
        BOOK_NAME VARCHAR(100),
        ISBN VARCHAR(20),
        REASON VARCHAR(200),
        HANDLER VARCHAR(50),
        LOG_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS CIRCULATION_HEAD (
        ISBN VARCHAR(20) PRIMARY KEY, CALL_NUMBER VARCHAR(50), 
        BOOK_NAME VARCHAR(100), AUTHOR VARCHAR(50), CLC_CODE VARCHAR(20)
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS CIRCULATION_DETAIL (
        BARCODE VARCHAR(20) PRIMARY KEY, ISBN VARCHAR(20), LOCATION VARCHAR(50), 
        STATUS INTEGER, -- 1:在馆, 2:借出, 3:预约, 4:报损/丢失
        ENTRY_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );''')

    # --- 2. 权限与角色系统 ---
    db.execute(
        '''CREATE TABLE IF NOT EXISTS SYS_ROLE (ROLE_ID INTEGER PRIMARY KEY, ROLE_NAME VARCHAR(50), DESCRIPTION VARCHAR(100));''')
    db.execute(
        '''CREATE TABLE IF NOT EXISTS SYS_PERMISSION (PERM_ID INTEGER PRIMARY KEY, PERM_CODE VARCHAR(50) UNIQUE, PERM_NAME VARCHAR(50));''')
    db.execute(
        '''CREATE TABLE IF NOT EXISTS SYS_ROLE_PERMISSION (ROLE_ID INTEGER, PERM_ID INTEGER, PRIMARY KEY (ROLE_ID, PERM_ID));''')

    # --- 3. 公告与留言 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS NOTICE (
        NOTICE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        TITLE VARCHAR(100) NOT NULL,
        CONTENT TEXT NOT NULL,
        PUBLISHER_NAME VARCHAR(50) NOT NULL,
        PUBLISH_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        IS_TOP INTEGER DEFAULT 0
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS USER_MESSAGE (
        MSG_ID INTEGER PRIMARY KEY AUTOINCREMENT, READER_ID INTEGER, CONTENT TEXT, 
        CREATE_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP, IS_READ INTEGER DEFAULT 0
    );''')

    # --- 4. 初始化数据 ---
    roles = [(1, '访客', ''), (2, '学生', ''), (3, '教职工', ''), (4, '采编', ''), (5, '编目', ''), (6, '流通', ''),
             (7, '用户管理', ''), (8, '超管', '')]
    db.executemany("INSERT OR IGNORE INTO SYS_ROLE VALUES (?,?,?)", roles)

    perms = [
        (1, 'access_dashboard', '访问仪表盘'), (2, 'access_services', '访问读者服务'),
        (3, 'manage_acq_order', '管理采访订单'), (4, 'manage_acq_arrival', '管理编目验收'),
        (5, 'manage_circulation', '管理流通工作台'), (6, 'manage_users', '管理用户与权限'),
        (7, 'publish_notice', '发布系统公告'), (99, 'root_access', '超级管理员权限')
    ]
    db.executemany("INSERT OR IGNORE INTO SYS_PERMISSION VALUES (?,?,?)", perms)

    db.execute("DELETE FROM SYS_ROLE_PERMISSION")
    role_perms = [(1, 1)] + \
                 [(r, 1) for r in [2, 3]] + [(r, 2) for r in [2, 3]] + \
                 [(4, 1), (4, 2), (4, 3), (4, 7)] + \
                 [(5, 1), (5, 2), (5, 4), (5, 7)] + \
                 [(6, 1), (6, 2), (6, 5), (6, 7)] + \
                 [(7, 1), (7, 2), (7, 6), (7, 7)] + \
                 [(8, 99)]
    db.executemany("INSERT INTO SYS_ROLE_PERMISSION VALUES (?,?)", role_perms)

    db.execute(
        '''CREATE TABLE IF NOT EXISTS CREDIT_LEVEL (LEVEL_ID INTEGER PRIMARY KEY, NAME VARCHAR(20), MAX_BORROW_NUM INTEGER, MAX_BORROW_DAY INTEGER, MAX_RESERVE_DAY INTEGER, ENABLE_BORROW INTEGER, ENTRY_SCORE INTEGER, MIN_SCORE INTEGER);''')
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (0,'访客',0,0,0,0,0,0)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (1,'本科生',10,30,7,1,100,60)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (2,'研究生',20,60,15,1,120,60)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (3,'教师',50,90,30,1,150,60)")

    # READER 表创建 (基础字段)
    db.execute(
        '''CREATE TABLE IF NOT EXISTS READER (READER_ID INTEGER PRIMARY KEY, NAME VARCHAR(50), SEX CHAR(1), DEPT_NAME VARCHAR(50), LEVEL_ID INTEGER, ROLE_ID INTEGER DEFAULT 1, CURRENT_CREDIT INTEGER, STATUS INTEGER DEFAULT 1, EXPIRY_DATE DATE, PASSWORD VARCHAR(64));''')

    # [新增] 尝试添加 EMAIL 和 TELEPHONE 字段 (兼容旧数据库)
    try:
        db.execute("ALTER TABLE READER ADD COLUMN EMAIL VARCHAR(100)")
    except sqlite3.OperationalError:
        pass  # 字段已存在

    try:
        db.execute("ALTER TABLE READER ADD COLUMN TELEPHONE VARCHAR(20)")
    except sqlite3.OperationalError:
        pass  # 字段已存在

    try:
        db.execute(
            "INSERT INTO READER (READER_ID, NAME, SEX, LEVEL_ID, ROLE_ID, CURRENT_CREDIT, EXPIRY_DATE, PASSWORD) VALUES (1001, 'SuperAdmin', 'M', 3, 8, 999, '2099-12-31', 'admin123')")
    except:
        pass

    db.execute(
        '''CREATE TABLE IF NOT EXISTS CREDIT_LOG (LOG_ID INTEGER PRIMARY KEY AUTOINCREMENT, READER_ID INTEGER, CHANGE_VAL INTEGER, REASON VARCHAR(100), OPERATOR VARCHAR(50), LOG_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
    db.execute(
        '''CREATE TABLE IF NOT EXISTS BORROW_RECORD (BORROW_ID INTEGER PRIMARY KEY AUTOINCREMENT, READER_ID INTEGER, BARCODE VARCHAR(20), BORROW_DATE TIMESTAMP, DUE_DATE TIMESTAMP, RETURN_DATE TIMESTAMP, STATUS INTEGER);''')
    db.execute(
        '''CREATE TABLE IF NOT EXISTS RESERVE_INFO (RESERVE_ID INTEGER PRIMARY KEY AUTOINCREMENT, READER_ID INTEGER, ISBN VARCHAR(20), BARCODE VARCHAR(20), RESERVE_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP, EXPIRE_DATE TIMESTAMP, STATUS INTEGER);''')
    db.execute(
        '''CREATE TABLE IF NOT EXISTS EXTENSION_APP (APP_ID INTEGER PRIMARY KEY AUTOINCREMENT, READER_ID INTEGER, BORROW_ID INTEGER, APPLY_DAYS INTEGER, REASON VARCHAR(200), APPLY_TIME TIMESTAMP DEFAULT CURRENT_TIMESTAMP, STATUS INTEGER DEFAULT 0);''')

    db.commit()


def init_ai_db():
    db = get_ai_db()
    db.execute(
        '''CREATE TABLE IF NOT EXISTS CHAT_MESSAGE (MSG_ID INTEGER PRIMARY KEY AUTOINCREMENT, USER_ID VARCHAR(50), ROLE VARCHAR(20), CONTENT TEXT, CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP);''')
    db.commit()


CLC_DATA = {
    'A': '马克思主义、列宁主义、毛泽东思想、邓小平理论', 'B': '哲学、宗教', 'C': '社会科学总论',
    'D': '政治、法律', 'E': '军事', 'F': '经济', 'G': '文化、科学、教育、体育',
    'H': '语言、文字', 'I': '文学', 'J': '艺术', 'K': '历史、地理', 'N': '自然科学总论',
    'O': '数理科学和化学', 'P': '天文学、地球科学', 'Q': '生物科学', 'R': '医药、卫生',
    'S': '农业科学', 'T': '工业技术', 'TP': '自动化技术、计算机技术', 'TQ': '化学工业',
    'U': '交通运输', 'V': '航空、航天', 'X': '环境科学、安全科学', 'Z': '综合性图书'
}