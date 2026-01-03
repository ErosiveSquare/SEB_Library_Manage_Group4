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


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """严格基于数据设计文档V2创建表结构 (修复版)"""
    db = get_db()

    # --- 1. 基础字典类 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS SUPPLIER (
        SUPPLIER_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        NAME VARCHAR(100) NOT NULL,
        ADDRESS VARCHAR(200) NOT NULL,
        CONTACT_PERSON VARCHAR(50) NOT NULL,
        TELEPHONE VARCHAR(20) NOT NULL,
        BANK_NAME VARCHAR(100),
        BANK_ACCOUNT VARCHAR(50),
        CREDIT_LEVEL CHAR(1) NOT NULL,
        EMAIL VARCHAR(100)
    );''')

    # --- 2. 采访与订单类 (此次修复重点) ---
    # 2.1 荐购表
    db.execute('''
    CREATE TABLE IF NOT EXISTS ACQ_SUGGESTION (
        ACQ_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        READER_ID INTEGER NOT NULL,
        BOOK_NAME VARCHAR(100) NOT NULL,
        AUTHOR VARCHAR(50),
        ISBN VARCHAR(20),
        PUBLISHER VARCHAR(100),
        STATUS INTEGER NOT NULL DEFAULT 0 -- 0:未处理, 1:已加入订单, 2:驳回
    );''')

    # 2.2 订单头表 (ORDER_HEAD) - 之前缺失
    db.execute('''
    CREATE TABLE IF NOT EXISTS ORDER_HEAD (
        ORDER_NO INTEGER PRIMARY KEY AUTOINCREMENT,
        PURCHASER VARCHAR(50) NOT NULL,
        ORDER_DATE TIMESTAMP NOT NULL,
        SUPPLIER_ID INTEGER NOT NULL,
        TOTAL_PRICE DECIMAL(12,2) NOT NULL
    );''')

    # 2.3 订单明细行 (ORDER_LINE) - 之前缺失
    db.execute('''
    CREATE TABLE IF NOT EXISTS ORDER_LINE (
        LINE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        ORDER_NO INTEGER NOT NULL,
        SUGGESTION_ID INTEGER,
        BOOK_NAME VARCHAR(100) NOT NULL,
        ISBN VARCHAR(20) NOT NULL,
        AUTHOR VARCHAR(50) NOT NULL,
        PUBLISHER VARCHAR(100) NOT NULL,
        PRICE DECIMAL(10,2) NOT NULL,
        QUANTITY INTEGER NOT NULL,
        STATUS INTEGER NOT NULL, -- 0:未到 1:已验收 2:已退货
        FOREIGN KEY (ORDER_NO) REFERENCES ORDER_HEAD(ORDER_NO)
    );''')

    # 2.4 验收清单 (ACCEPT_LIST) - 之前缺失
    db.execute('''
    CREATE TABLE IF NOT EXISTS ACCEPT_LIST (
        ACCEPT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        LINE_ID INTEGER NOT NULL,
        QUANTITY INTEGER NOT NULL,
        CHECK_MAN VARCHAR(50) NOT NULL,
        CHECK_DATE TIMESTAMP NOT NULL,
        FOREIGN KEY (LINE_ID) REFERENCES ORDER_LINE(LINE_ID)
    );''')

    # 2.5 退货清单 (RETURN_LIST) - 之前缺失
    db.execute('''
    CREATE TABLE IF NOT EXISTS RETURN_LIST (
        RETURN_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        LINE_ID INTEGER NOT NULL,
        QUANTITY INTEGER NOT NULL,
        REASON VARCHAR(200) NOT NULL,
        HANDLER VARCHAR(50) NOT NULL,
        RETURN_DATE TIMESTAMP NOT NULL,
        FOREIGN KEY (LINE_ID) REFERENCES ORDER_LINE(LINE_ID)
    );''')

    # --- 3. 编目与馆藏类 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS CIRCULATION_HEAD (
        ISBN VARCHAR(20) PRIMARY KEY,
        CALL_NUMBER VARCHAR(50) NOT NULL,
        BOOK_NAME VARCHAR(100) NOT NULL,
        AUTHOR VARCHAR(50) NOT NULL,
        CLC_CODE VARCHAR(20) NOT NULL
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS CIRCULATION_DETAIL (
        BARCODE VARCHAR(20) PRIMARY KEY,
        ISBN VARCHAR(20) NOT NULL,
        LOCATION VARCHAR(50) NOT NULL,
        STATUS INTEGER NOT NULL, -- 1:在馆, 2:借出, 3:预约, 4:报损, 5:遗失
        ENTRY_DATE TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ISBN) REFERENCES CIRCULATION_HEAD(ISBN)
    );''')

    # --- 4. 用户与权限类 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS CREDIT_LEVEL (
        LEVEL_ID INTEGER PRIMARY KEY,
        NAME VARCHAR(20) NOT NULL,
        MAX_BORROW_NUM INTEGER NOT NULL,
        MAX_BORROW_DAY INTEGER NOT NULL,
        MAX_RESERVE_DAY INTEGER NOT NULL,
        ENABLE_BORROW INTEGER NOT NULL,
        ENTRY_SCORE INTEGER NOT NULL,
        MIN_SCORE INTEGER NOT NULL
    );''')

    # 初始化预设等级
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (0, '访客', 0, 0, 0, 0, 0, 0)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (1, '本科生', 10, 30, 7, 1, 100, 60)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (2, '研究生', 20, 60, 15, 1, 120, 60)")
    db.execute("INSERT OR IGNORE INTO CREDIT_LEVEL VALUES (3, '教师', 50, 90, 30, 1, 150, 60)")

    db.execute('''
    CREATE TABLE IF NOT EXISTS READER (
        READER_ID INTEGER PRIMARY KEY,
        NAME VARCHAR(50) NOT NULL,
        SEX CHAR(1) NOT NULL,
        DEPT_NAME VARCHAR(50),
        LEVEL_ID INTEGER NOT NULL,
        CURRENT_CREDIT INTEGER NOT NULL,
        STATUS INTEGER NOT NULL DEFAULT 1,
        EXPIRY_DATE DATE NOT NULL,
        PASSWORD VARCHAR(64) NOT NULL,
        FOREIGN KEY (LEVEL_ID) REFERENCES CREDIT_LEVEL(LEVEL_ID)
    );''')

    db.execute('''
    CREATE TABLE IF NOT EXISTS ADMIN (
        ADMIN_ID INTEGER PRIMARY KEY,
        NAME VARCHAR(50) NOT NULL,
        PASSWORD VARCHAR(64) NOT NULL,
        ROLE INTEGER NOT NULL -- 0采编/1流通/2系统
    );''')

    # --- 5. 流通业务类 ---
    db.execute('''
    CREATE TABLE IF NOT EXISTS BORROW_RECORD (
        BORROW_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        READER_ID INTEGER NOT NULL,
        BARCODE VARCHAR(20) NOT NULL,
        BORROW_DATE TIMESTAMP NOT NULL,
        DUE_DATE TIMESTAMP NOT NULL,
        RETURN_DATE TIMESTAMP,
        STATUS INTEGER NOT NULL, -- 1:借出, 2:已还, 3:超期
        FOREIGN KEY (READER_ID) REFERENCES READER(READER_ID),
        FOREIGN KEY (BARCODE) REFERENCES CIRCULATION_DETAIL(BARCODE)
    );''')

    # 默认管理员 (Role 2: 系统超级管理员)
    db.execute("INSERT OR IGNORE INTO ADMIN (ADMIN_ID, NAME, PASSWORD, ROLE) VALUES (1001, 'Admin', 'admin123', 2)")

    db.commit()