1. 这是一个基于你提供的【DFD蓝图】（业务逻辑）和【学长版本数据设计】（参考字段）生成的**优化版图书管理系统数据设计文档**。

   ### 设计说明：

   1. **规范化命名**：将所有表名和字段名统一为标准的英文命名（Snake_Case风格），解决了学长版本中拼写错误（如 `OREDRMAN` -> `PURCHASER`）和中英混用的问题。
   2. **数据类型修正**：
   * 原 `LONG` 统一对应数据库的 `BIGINT`。
   * 原 `INT` 存价格不科学，改为 `DECIMAL(10,2)`。
   * 原 `BOOL` 统一为 `TINYINT(1)`（标准数据库布尔值存法）。
   * 加入了 `DATETIME` 以精确记录时间（不仅是日期）。


   3. **模块化设计**：按照DFD的子系统（采访、编目、流通、用户、系统）进行分类展示。

   ---

   # 图书管理系统数据库设计说明书

   ## 1. 基础字典模块 (1.1, 1.2, 1.6 支持)

   此模块存储系统通用的基础数据，供采访和编目子系统调用。

   ### 1.1 书商信息表 (SUPPLIER_DICT)

   | 字段名          | 数据类型 | 长度 | 约束         | 含义     | 描述                         |
   | --------------- | -------- | ---- | ------------ | -------- | ---------------------------- |
   | **SUPPLIER_ID** | BIGINT   | 20   | PK, Not Null | 书商编号 | 替代原Name主键，数字ID更高效 |
   | NAME            | VARCHAR  | 100  | Not Null     | 书商名称 |                              |
   | ADDRESS         | VARCHAR  | 200  | Not Null     | 地址     |                              |
   | CONTACT_PERSON  | VARCHAR  | 50   | Not Null     | 联系人   |                              |
   | TELEPHONE       | VARCHAR  | 20   | Not Null     | 电话     | 兼容带区号的格式             |
   | BANK_NAME       | VARCHAR  | 100  | Null         | 开户行   |                              |
   | BANK_ACCOUNT    | VARCHAR  | 50   | Null         | 账号     |                              |
   | CREDIT_LEVEL    | CHAR     | 1    | Not Null     | 信誉度   | A/B/C/D等级                  |
   | EMAIL           | VARCHAR  | 100  | Null         | 邮箱     |                              |

   ### 1.2 出版社信息表 (PUBLISHER_DICT)

   | 字段名           | 数据类型 | 长度 | 约束         | 含义       | 描述         |
   | ---------------- | -------- | ---- | ------------ | ---------- | ------------ |
   | **PUBLISHER_ID** | BIGINT   | 20   | PK, Not Null | 出版社编号 |              |
   | NAME             | VARCHAR  | 100  | Not Null     | 出版社名称 |              |
   | ADDRESS          | VARCHAR  | 200  | Not Null     | 地址       |              |
   | PUBLISH_PLACE    | VARCHAR  | 100  | Not Null     | 出版地     |              |
   | ISBN_PREFIX      | VARCHAR  | 20   | Null         | ISBN前缀   | 用于辅助编目 |

   ### 1.3 中图法分类表 (CLC_DICT)

   | 字段名       | 数据类型 | 长度 | 约束         | 含义       | 描述          |
   | ------------ | -------- | ---- | ------------ | ---------- | ------------- |
   | **CLC_CODE** | VARCHAR  | 20   | PK, Not Null | 中图分类号 | 如 TP311      |
   | TYPE_NAME    | VARCHAR  | 100  | Not Null     | 类别名称   | 如 计算机软件 |

   ---

   ## 2. 采访子系统数据表 (DFD 1.1)

   对应DFD中读者荐购、订单管理、验收、退货流程。

   ### 2.1 采访清单/荐购表 (ACQUISITION_LIST)

   | 字段名     | 数据类型 | 长度 | 约束         | 含义      | 描述                           |
   | ---------- | -------- | ---- | ------------ | --------- | ------------------------------ |
   | **ACQ_ID** | BIGINT   | 20   | PK, Not Null | 记录序号  |                                |
   | READER_ID  | BIGINT   | 20   | FK, Not Null | 读者/学号 | 关联读者表                     |
   | BOOK_NAME  | VARCHAR  | 100  | Not Null     | 书名      |                                |
   | AUTHOR     | VARCHAR  | 50   | Null         | 作者      |                                |
   | ISBN       | VARCHAR  | 20   | Null         | ISBN      |                                |
   | PUBLISHER  | VARCHAR  | 100  | Null         | 出版社    |                                |
   | STATUS     | TINYINT  | 1    | Not Null     | 处理状态  | 0:未处理, 1:已加入订单, 2:驳回 |

   ### 2.2 订单头表 (ORDER_HEAD)

   | 字段名       | 数据类型 | 长度 | 约束         | 含义     | 描述               |
   | ------------ | -------- | ---- | ------------ | -------- | ------------------ |
   | **ORDER_NO** | BIGINT   | 20   | PK, Not Null | 订单号   |                    |
   | PURCHASER    | VARCHAR  | 50   | Not Null     | 采购人   | 经办的馆员姓名或ID |
   | ORDER_DATE   | DATETIME |      | Not Null     | 采购日期 |                    |
   | SUPPLIER_ID  | BIGINT   | 20   | FK, Not Null | 书商ID   | 关联书商表         |
   | TOTAL_PRICE  | DECIMAL  | 12,2 | Not Null     | 总金额   |                    |

   ### 2.3 订单明细行 (ORDER_LINE)

   | 字段名      | 数据类型 | 长度 | 约束         | 含义     | 描述         |
   | ----------- | -------- | ---- | ------------ | -------- | ------------ |
   | **LINE_ID** | BIGINT   | 20   | PK, Not Null | 行号     |              |
   | ORDER_NO    | BIGINT   | 20   | FK, Not Null | 订单号   | 关联订单头表 |
   | BOOK_NAME   | VARCHAR  | 100  | Not Null     | 书名     |              |
   | ISBN        | VARCHAR  | 20   | Not Null     | ISBN     |              |
   | AUTHOR      | VARCHAR  | 50   | Not Null     | 作者     |              |
   | PUBLISHER   | VARCHAR  | 100  | Not Null     | 出版社   |              |
   | PRICE       | DECIMAL  | 10,2 | Not Null     | 单价     |              |
   | QUANTITY    | INT      | 4    | Not Null     | 订购数量 |              |
   | ARRIVED_QTY | INT      | 4    | Default 0    | 到货数量 |              |

   ### 2.4 验收清单 (ACCEPTANCE_LIST)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义       | 描述               |
   | ------------- | -------- | ---- | ------------ | ---------- | ------------------ |
   | **ACCEPT_ID** | BIGINT   | 20   | PK, Not Null | 验收记录号 |                    |
   | LINE_ID       | BIGINT   | 20   | FK, Not Null | 订单行号   | 关联订单明细       |
   | QUANTITY      | INT      | 4    | Not Null     | 实收数量   |                    |
   | CHECK_MAN     | VARCHAR  | 50   | Not Null     | 验收人     |                    |
   | CHECK_DATE    | DATETIME |      | Not Null     | 验收日期   |                    |
   | IS_CATALOGED  | TINYINT  | 1    | Default 0    | 是否编目   | 0:未编目, 1:已编目 |

   ### 2.5 退货清单 (RETURN_LIST)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义     | 描述 |
   | ------------- | -------- | ---- | ------------ | -------- | ---- |
   | **RETURN_ID** | BIGINT   | 20   | PK, Not Null | 退货单号 |      |
   | LINE_ID       | BIGINT   | 20   | FK, Not Null | 订单行号 |      |
   | QUANTITY      | INT      | 4    | Not Null     | 退货数量 |      |
   | REASON        | VARCHAR  | 200  | Not Null     | 退货原因 |      |
   | HANDLER       | VARCHAR  | 50   | Not Null     | 经手人   |      |
   | RETURN_DATE   | DATETIME |      | Not Null     | 退货日期 |      |

   ---

   ## 3. 编目与馆藏子系统 (DFD 1.2)

   对应DFD中编目查重、入库移送、新书通报流程。

   ### 3.1 编目缓冲/中间表 (CATALOG_BUFFER)

   *说明：DFD中提到的“编目清单”，作为验收和正式入库之间的工作区。*

   | 字段名      | 数据类型 | 长度 | 约束         | 含义       | 描述                 |
   | ----------- | -------- | ---- | ------------ | ---------- | -------------------- |
   | **TEMP_ID** | BIGINT   | 20   | PK, Not Null | 编目流水号 |                      |
   | ISBN        | VARCHAR  | 20   | Not Null     | ISBN       |                      |
   | CALL_NUMBER | VARCHAR  | 50   | Not Null     | 索书号     | 核心字段，分类排架用 |
   | BOOK_NAME   | VARCHAR  | 100  | Not Null     | 书名       |                      |
   | AUTHOR      | VARCHAR  | 50   | Not Null     | 作者       |                      |
   | PUBLISHER   | VARCHAR  | 100  | Not Null     | 出版社     |                      |
   | PUB_DATE    | DATE     |      | Null         | 出版日期   |                      |
   | PRICE       | DECIMAL  | 10,2 | Not Null     | 价格       |                      |

   ### 3.2 图书流通库表 (BOOK_STOCK)

   *说明：这是核心资产表，每一本书（复本）对应一条记录。*

   | 字段名      | 数据类型 | 长度 | 约束         | 含义     | 描述                                   |
   | ----------- | -------- | ---- | ------------ | -------- | -------------------------------------- |
   | **BARCODE** | VARCHAR  | 20   | PK, Not Null | 条码号   | 贴在书后的唯一标识                     |
   | ISBN        | VARCHAR  | 20   | FK, Not Null | ISBN     | 关联书目信息                           |
   | CALL_NUMBER | VARCHAR  | 50   | Not Null     | 索书号   |                                        |
   | BOOK_NAME   | VARCHAR  | 100  | Not Null     | 书名     | 冗余字段，优化查询                     |
   | AUTHOR      | VARCHAR  | 50   | Not Null     | 作者     | 冗余字段                               |
   | LOCATION    | VARCHAR  | 50   | Not Null     | 馆藏地   | 如：一楼流通室                         |
   | STATUS      | TINYINT  | 1    | Not Null     | 状态     | 1:在馆, 2:借出, 3:预约, 4:报损, 5:遗失 |
   | ENTRY_DATE  | DATETIME |      | Not Null     | 入库日期 |                                        |

   ### 3.3 期刊库表 (JOURNAL_STOCK)

   | 字段名       | 数据类型 | 长度 | 约束         | 含义   | 描述           |
   | ------------ | -------- | ---- | ------------ | ------ | -------------- |
   | **BARCODE**  | VARCHAR  | 20   | PK, Not Null | 条码号 |                |
   | ISSN         | VARCHAR  | 20   | Not Null     | ISSN   |                |
   | JOURNAL_NAME | VARCHAR  | 100  | Not Null     | 期刊名 |                |
   | YEAR_ISSUE   | VARCHAR  | 20   | Not Null     | 年卷期 | 如 2025年第3期 |
   | CALL_NUMBER  | VARCHAR  | 50   | Not Null     | 索书号 |                |

   ### 3.4 报损/注销记录 (DAMAGE_RECORD)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义     | 描述           |
   | ------------- | -------- | ---- | ------------ | -------- | -------------- |
   | **RECORD_ID** | BIGINT   | 20   | PK, Not Null | 记录号   |                |
   | BARCODE       | VARCHAR  | 20   | FK, Not Null | 图书条码 | 关联流通库     |
   | TYPE          | VARCHAR  | 20   | Not Null     | 类型     | 报损/丢失/剔旧 |
   | HANDLER       | VARCHAR  | 50   | Not Null     | 经手人   |                |
   | DATE          | DATETIME |      | Not Null     | 日期     |                |
   | REMARK        | VARCHAR  | 200  | Null         | 备注     |                |

   ---

   ## 4. 用户管理子系统 (DFD 1.4)

   ### 4.1 读者信息表 (READER_INFO)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义          | 描述                   |
   | ------------- | -------- | ---- | ------------ | ------------- | ---------------------- |
   | **READER_ID** | BIGINT   | 20   | PK, Not Null | 学号/工号     |                        |
   | NAME          | VARCHAR  | 50   | Not Null     | 姓名          |                        |
   | SEX           | CHAR     | 1    | Not Null     | 性别          | M/F                    |
   | DEPT_NAME     | VARCHAR  | 50   | Null         | 学院/部门     |                        |
   | LEVEL_ID      | INT      | 4    | FK, Not Null | 信用/读者等级 | 关联等级表             |
   | STATUS        | TINYINT  | 1    | Not Null     | 账号状态      | 1:正常, 0:封禁, 2:注销 |
   | EXPIRY_DATE   | DATE     |      | Not Null     | 有效期至      | 毕业或离职时间         |
   | PASSWORD      | VARCHAR  | 64   | Not Null     | 登录密码      | 加密存储               |

   ### 4.2 信用等级/权限表 (CREDIT_LEVEL)

   | 字段名          | 数据类型 | 长度 | 约束         | 含义         | 描述                 |
   | --------------- | -------- | ---- | ------------ | ------------ | -------------------- |
   | **LEVEL_ID**    | INT      | 4    | PK, Not Null | 等级编号     | 1:本科, 2:研, 3:教师 |
   | MAX_BORROW_NUM  | INT      | 4    | Not Null     | 最大借书量   | 本                   |
   | MAX_BORROW_DAY  | INT      | 4    | Not Null     | 最大借阅天数 | 天                   |
   | MAX_RESERVE_DAY | INT      | 4    | Not Null     | 最长预约保留 | 天                   |

   ### 4.3 管理员信息表 (ADMIN_INFO)

   | 字段名       | 数据类型 | 长度 | 约束         | 含义       | 描述                 |
   | ------------ | -------- | ---- | ------------ | ---------- | -------------------- |
   | **ADMIN_ID** | BIGINT   | 20   | PK, Not Null | 管理员编号 |                      |
   | NAME         | VARCHAR  | 50   | Not Null     | 姓名       |                      |
   | PASSWORD     | VARCHAR  | 64   | Not Null     | 密码       |                      |
   | ROLE         | VARCHAR  | 20   | Not Null     | 角色       | 采编/流通/系统管理员 |

   ---

   ## 5. 流通子系统 (DFD 1.3)

   核心业务表，连接读者与图书。

   ### 5.1 借阅记录表 (BORROW_RECORD)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义         | 描述                   |
   | ------------- | -------- | ---- | ------------ | ------------ | ---------------------- |
   | **BORROW_ID** | BIGINT   | 20   | PK, Not Null | 流水号       |                        |
   | READER_ID     | BIGINT   | 20   | FK, Not Null | 读者ID       |                        |
   | BARCODE       | VARCHAR  | 20   | FK, Not Null | 图书条码     |                        |
   | BORROW_DATE   | DATETIME |      | Not Null     | 借阅时间     |                        |
   | DUE_DATE      | DATETIME |      | Not Null     | 应还时间     |                        |
   | RETURN_DATE   | DATETIME |      | Null         | 实际归还时间 | 空表示未还             |
   | STATUS        | TINYINT  | 1    | Not Null     | 状态         | 1:借出, 2:已还, 3:超期 |

   ### 5.2 预约信息表 (RESERVATION)

   | 字段名         | 数据类型 | 长度 | 约束         | 含义         | 描述                               |
   | -------------- | -------- | ---- | ------------ | ------------ | ---------------------------------- |
   | **RESERVE_ID** | BIGINT   | 20   | PK, Not Null | 预约编号     |                                    |
   | READER_ID      | BIGINT   | 20   | FK, Not Null | 读者ID       |                                    |
   | BARCODE        | VARCHAR  | 20   | FK, Not Null | 图书条码     |                                    |
   | RESERVE_DATE   | DATETIME |      | Not Null     | 预约发起时间 |                                    |
   | EXPIRE_DATE    | DATETIME |      | Not Null     | 预约失效时间 |                                    |
   | STATUS         | TINYINT  | 1    | Not Null     | 状态         | 1:排队中, 2:待取书, 3:已取, 4:失效 |

   ### 5.3 处罚记录表 (PUNISHMENT_RECORD)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义     | 描述                               |
   | ------------- | -------- | ---- | ------------ | -------- | ---------------------------------- |
   | **PUNISH_ID** | BIGINT   | 20   | PK, Not Null | 处罚单号 |                                    |
   | READER_ID     | BIGINT   | 20   | FK, Not Null | 读者ID   |                                    |
   | BORROW_ID     | BIGINT   | 20   | FK, Null     | 关联借阅 | 可为空（如果是人为损坏非借阅导致） |
   | REASON        | VARCHAR  | 50   | Not Null     | 处罚原因 | 超期/丢失/损坏                     |
   | AMOUNT        | DECIMAL  | 8,2  | Not Null     | 罚款金额 |                                    |
   | CREATE_DATE   | DATETIME |      | Not Null     | 产生时间 |                                    |
   | IS_PAID       | TINYINT  | 1    | Default 0    | 是否缴费 | 0:未缴, 1:已缴                     |

   ### 5.4 默认处罚配置 (PUNISH_CONFIG)

   | 字段名         | 数据类型 | 长度 | 约束         | 含义          | 描述                  |
   | -------------- | -------- | ---- | ------------ | ------------- | --------------------- |
   | **CONFIG_KEY** | VARCHAR  | 50   | PK, Not Null | 配置键        | 如 OVERDUE_DAILY_FINE |
   | VALUE          | DECIMAL  | 8,2  | Not Null     | 罚款金额/数值 | 如 0.10 (元/天)       |
   | DESCRIPTION    | VARCHAR  | 100  | Null         | 描述          |                       |

   ### 5.5 延期申请表 (EXTENSION_APP)

   对应 DFD 1.5.1 和 1.4.11
   | 字段名     | 数据类型 | 长度 | 约束         | 含义       | 描述                   |
   | :--------- | :------- | :--- | :----------- | :--------- | :--------------------- |
   | **APP_ID** | BIGINT   | 20   | PK, Not Null | 申请编号   |                        |
   | READER_ID  | BIGINT   | 20   | FK, Not Null | 读者ID     |                        |
   | BORROW_ID  | BIGINT   | 20   | FK, Not Null | 借阅记录ID |                        |
   | REASON     | VARCHAR  | 200  | Null         | 申请理由   |                        |
   | APPLY_TIME | DATETIME |      | Not Null     | 申请时间   |                        |
   | STATUS     | TINYINT  | 1    | Not Null     | 审批状态   | 0:待审, 1:通过, 2:拒绝 |
   | AUDITOR_ID | BIGINT   | 20   | FK, Null     | 审核管理员 |                        |

   ---

   ## 6. 系统与Web交互模块 (DFD 1.5, 1.6, 1.7)

   ### 6.1 公告表 (ANNOUNCEMENT)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义     | 描述   |
   | ------------- | -------- | ---- | ------------ | -------- | ------ |
   | **NOTICE_ID** | BIGINT   | 20   | PK, Not Null | 公告编号 |        |
   | TITLE         | VARCHAR  | 100  | Not Null     | 标题     |        |
   | CONTENT       | TEXT     |      | Not Null     | 内容     | 长文本 |
   | PUBLISH_TIME  | DATETIME |      | Not Null     | 发布时间 |        |
   | ADMIN_ID      | BIGINT   | 20   | FK, Not Null | 发布人   |        |

   ### 6.2 留言板 (MESSAGE_BOARD)

   | 字段名        | 数据类型 | 长度 | 约束         | 含义       | 描述 |
   | ------------- | -------- | ---- | ------------ | ---------- | ---- |
   | **MSG_ID**    | BIGINT   | 20   | PK, Not Null | 留言ID     |      |
   | READER_ID     | BIGINT   | 20   | FK, Not Null | 留言者     |      |
   | CONTENT       | VARCHAR  | 500  | Not Null     | 留言内容   |      |
   | MSG_TIME      | DATETIME |      | Not Null     | 留言时间   |      |
   | REPLY_CONTENT | VARCHAR  | 500  | Null         | 管理员回复 |      |
   | REPLY_ADMIN   | BIGINT   | 20   | FK, Null     | 回复人     |      |

   ### 6.3 备份配置 (BACKUP_CONFIG)

   | 字段名         | 数据类型 | 长度 | 约束         | 含义         | 描述 |
   | -------------- | -------- | ---- | ------------ | ------------ | ---- |
   | **TABLE_NAME** | VARCHAR  | 50   | PK, Not Null | 表名         |      |
   | CYCLE_DAYS     | INT      | 4    | Not Null     | 备份周期(天) |      |
   | PATH           | VARCHAR  | 200  | Not Null     | 存储路径     |      |

   ### 6.4 统计预设表 (STAT_PRESET)

   对应 DFD 1.7
   | 字段名        | 数据类型 | 长度 | 约束         | 含义         | 描述            |
   | :------------ | :------- | :--- | :----------- | :----------- | :-------------- |
   | **STAT_CODE** | VARCHAR  | 20   | PK, Not Null | 统计编码     | 如 TOP10_BORROW |
   | SQL_LOGIC     | TEXT     |      | Not Null     | 统计逻辑/SQL | 存储查询逻辑    |
   | CHART_TYPE    | VARCHAR  | 20   | Not Null     | 图表类型     | Bar/Pie/Line    |
   | IS_ENABLED    | TINYINT  | 1    | Default 1    | 是否启用     |                 |