# 常用达梦数据库 SQL 查询参考

## 数据库管理

### 查看数据库版本
```sql
SELECT * FROM V$VERSION;
```

### 查看实例信息
```sql
SELECT * FROM V$INSTANCE;
```

### 查看数据库信息
```sql
SELECT * FROM V$DATABASE;
```

### 查看字符集
```sql
SELECT * FROM V$NLS_PARAMETERS;
```

## Schema 和用户管理

### 查看所有用户
```sql
SELECT USERNAME, ACCOUNT_STATUS, CREATED 
FROM DBA_USERS 
ORDER BY CREATED DESC;
```

### 查看当前用户
```sql
SELECT USER FROM DUAL;
```

### 查看用户拥有的对象
```sql
SELECT OBJECT_TYPE, COUNT(*) 
FROM USER_OBJECTS 
GROUP BY OBJECT_TYPE;
```

## 表操作

### 查看所有表
```sql
SELECT OWNER, TABLE_NAME, NUM_ROWS 
FROM ALL_TABLES 
WHERE OWNER = 'SCHEMA_NAME'
ORDER BY TABLE_NAME;
```

### 查看表结构
```sql
-- 方式1：使用 DESCRIBE
DESCRIBE table_name;

-- 方式2：查询数据字典
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    DATA_LENGTH,
    NULLABLE
FROM ALL_TAB_COLUMNS
WHERE OWNER = 'SCHEMA_NAME' AND TABLE_NAME = 'TABLE_NAME'
ORDER BY COLUMN_ID;
```

### 查看表的约束
```sql
SELECT 
    CONSTRAINT_NAME,
    CONSTRAINT_TYPE,
    STATUS
FROM ALL_CONSTRAINTS
WHERE OWNER = 'SCHEMA_NAME' AND TABLE_NAME = 'TABLE_NAME';
```

### 查看表索引
```sql
SELECT 
    INDEX_NAME,
    UNIQUENESS,
    STATUS
FROM ALL_INDEXES
WHERE OWNER = 'SCHEMA_NAME' AND TABLE_NAME = 'TABLE_NAME';
```

### 查看索引列
```sql
SELECT 
    INDEX_NAME,
    COLUMN_NAME,
    COLUMN_POSITION
FROM ALL_IND_COLUMNS
WHERE TABLE_OWNER = 'SCHEMA_NAME' AND TABLE_NAME = 'TABLE_NAME'
ORDER BY INDEX_NAME, COLUMN_POSITION;
```

### 查看外键
```sql
SELECT 
    a.CONSTRAINT_NAME,
    a.COLUMN_NAME,
    c.TABLE_NAME as REFERENCED_TABLE,
    c.COLUMN_NAME as REFERENCED_COLUMN
FROM ALL_CONS_COLUMNS a
JOIN ALL_CONSTRAINTS b ON a.CONSTRAINT_NAME = b.CONSTRAINT_NAME
JOIN ALL_CONS_COLUMNS c ON b.R_CONSTRAINT_NAME = c.CONSTRAINT_NAME
WHERE b.CONSTRAINT_TYPE = 'R' 
    AND a.OWNER = 'SCHEMA_NAME' 
    AND a.TABLE_NAME = 'TABLE_NAME';
```

## 数据分析

### 统计记录数
```sql
SELECT COUNT(*) FROM table_name;
```

### 分组统计
```sql
SELECT column_name, COUNT(*) as count
FROM table_name
GROUP BY column_name
ORDER BY count DESC;
```

### 查看空值情况
```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN column_name IS NULL THEN 1 ELSE 0 END) as null_count
FROM table_name;
```

### 数据抽样
```sql
-- 使用 ROWNUM 限制行数
SELECT * FROM table_name WHERE ROWNUM <= 10;

-- 分页查询
SELECT * FROM (
    SELECT t.*, ROWNUM as rn FROM table_name t WHERE ROWNUM <= 20
) WHERE rn > 10;

-- 使用 LIMIT（达梦支持）
SELECT * FROM table_name LIMIT 10;
SELECT * FROM table_name LIMIT 10 OFFSET 10;
```

## 性能分析

### 查看当前会话
```sql
SELECT 
    SESS_ID,
    USER_NAME,
    CLNT_HOST,
    STATE
FROM V$SESSIONS;
```

### 查看正在执行的 SQL
```sql
SELECT 
    SESS_ID,
    SQL_TEXT,
    STATE
FROM V$SESSIONS
WHERE SQL_TEXT IS NOT NULL;
```

### 查看等待事件
```sql
SELECT * FROM V$WAITSTAT;
```

### 分析查询计划
```sql
EXPLAIN SELECT * FROM table_name WHERE column = 'value';
```

## 空间管理

### 查看表空间使用情况
```sql
SELECT 
    TABLESPACE_NAME,
    FILE_NAME,
    BYTES / 1024 / 1024 as SIZE_MB
FROM DBA_DATA_FILES;
```

### 查看表大小
```sql
SELECT 
    SEGMENT_NAME,
    BYTES / 1024 / 1024 as SIZE_MB
FROM USER_SEGMENTS
WHERE SEGMENT_TYPE = 'TABLE'
ORDER BY BYTES DESC;
```

## 数据修改

### 批量更新
```sql
UPDATE table_name 
SET column = 'new_value' 
WHERE condition;
COMMIT;
```

### 批量删除
```sql
DELETE FROM table_name WHERE condition;
COMMIT;
```

### 事务控制
```sql
-- 开始事务
SET AUTOCOMMIT OFF;

UPDATE table_name SET column = 'value' WHERE id = 1;

-- 检查结果
SELECT * FROM table_name WHERE id = 1;

-- 确认提交或回滚
COMMIT;  -- 或 ROLLBACK;

SET AUTOCOMMIT ON;
```

## 常用函数

### 字符串函数
```sql
CONCAT(str1, str2)           -- 连接字符串
SUBSTR(str, start, len)      -- 截取字符串
TRIM(str)                    -- 去除空格
UPPER(str) / LOWER(str)      -- 大小写转换
LENGTH(str)                  -- 字符串长度
INSTR(str, substr)           -- 查找位置
REPLACE(str, old, new)       -- 替换字符串
```

### 日期函数
```sql
SYSDATE                      -- 当前日期时间
CURRENT_DATE                 -- 当前日期
ADD_MONTHS(date, n)          -- 加减月份
MONTHS_BETWEEN(d1, d2)       -- 月份差
TO_CHAR(date, 'YYYY-MM-DD')  -- 日期格式化
TO_DATE(str, 'YYYY-MM-DD')   -- 字符串转日期
```

### 聚合函数
```sql
COUNT(*), SUM(col), AVG(col), MAX(col), MIN(col)
```

### NULL 处理
```sql
NVL(column, default_value)       -- 替换 NULL
NVL2(col, val1, val2)            -- 非空返回 val1，否则 val2
COALESCE(col1, col2, default)    -- 返回第一个非 NULL 值
NULLIF(col1, col2)               -- 相等时返回 NULL
```

## 序列操作

### 查看序列
```sql
SELECT SEQUENCE_NAME, LAST_NUMBER, INCREMENT_BY 
FROM USER_SEQUENCES;
```

### 获取序列值
```sql
SELECT sequence_name.NEXTVAL FROM DUAL;
SELECT sequence_name.CURRVAL FROM DUAL;
```
