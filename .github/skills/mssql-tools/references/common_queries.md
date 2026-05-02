# 常用 T-SQL 查询参考

## 数据库管理

### 查看所有数据库
```sql
SELECT name, state_desc, recovery_model_desc 
FROM sys.databases
ORDER BY name;
```

### 查看数据库大小
```sql
SELECT 
    DB_NAME(database_id) as database_name,
    CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(18,2)) as size_mb
FROM sys.master_files
GROUP BY database_id
ORDER BY size_mb DESC;
```

### 查看数据库属性
```sql
SELECT 
    name,
    collation_name,
    recovery_model_desc,
    state_desc
FROM sys.databases
WHERE name = 'your_database';
```

## 表操作

### 查看表结构
```sql
-- 方式1：使用系统存储过程
EXEC sp_help 'table_name';

-- 方式2：查询系统视图
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'table_name'
ORDER BY ORDINAL_POSITION;
```

### 查看表索引
```sql
EXEC sp_helpindex 'table_name';

-- 或使用查询
SELECT 
    i.name as index_name,
    i.type_desc,
    i.is_unique,
    COL_NAME(ic.object_id, ic.column_id) as column_name
FROM sys.indexes i
JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
WHERE OBJECT_NAME(i.object_id) = 'table_name';
```

### 查看所有外键
```sql
SELECT 
    fk.name as constraint_name,
    OBJECT_NAME(fk.parent_object_id) as table_name,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) as column_name,
    OBJECT_NAME(fk.referenced_object_id) as referenced_table,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) as referenced_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id;
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
-- 随机抽取 10 条 (NEWID() 方式)
SELECT TOP 10 * FROM table_name ORDER BY NEWID();

-- 分页查询 (SQL Server 2012+)
SELECT * FROM table_name
ORDER BY id
OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY;

-- 传统分页
SELECT TOP 10 * FROM table_name
WHERE id NOT IN (SELECT TOP 0 id FROM table_name ORDER BY id)
ORDER BY id;
```

## 性能分析

### 查看当前连接
```sql
SELECT 
    session_id,
    login_name,
    host_name,
    program_name,
    status
FROM sys.dm_exec_sessions
WHERE is_user_process = 1;
```

### 查看正在执行的查询
```sql
SELECT 
    r.session_id,
    r.status,
    r.command,
    r.wait_type,
    t.text as query_text
FROM sys.dm_exec_requests r
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.session_id > 50;
```

### 查看表锁
```sql
SELECT 
    OBJECT_NAME(resource_associated_entity_id) as table_name,
    request_mode,
    request_status
FROM sys.dm_tran_locks
WHERE resource_type = 'OBJECT';
```

### 分析查询计划
```sql
SET SHOWPLAN_TEXT ON;
GO
SELECT * FROM table_name WHERE column = 'value';
GO
SET SHOWPLAN_TEXT OFF;
```

## 数据导出

### 导出为表格格式
```sql
-- 使用 BCP 命令导出
-- bcp "SELECT * FROM database.dbo.table_name" queryout "C:\output.csv" -c -t"," -S server -U user -P password
```

### 查询结果格式化
```sql
-- 日期格式化
SELECT FORMAT(create_time, 'yyyy-MM-dd HH:mm:ss') FROM table_name;

-- 数字格式化
SELECT FORMAT(price, 'N2') FROM table_name;
```

## 数据修改

### 批量更新
```sql
UPDATE table_name 
SET column = 'new_value' 
WHERE condition;
```

### 批量删除
```sql
DELETE FROM table_name WHERE condition;

-- 删除所有数据（更快）
TRUNCATE TABLE table_name;
```

### 事务控制
```sql
BEGIN TRANSACTION;

UPDATE table_name SET column = 'value' WHERE id = 1;

-- 检查结果
SELECT * FROM table_name WHERE id = 1;

-- 确认提交或回滚
COMMIT;  -- 或 ROLLBACK;
```

## 常用函数

### 字符串函数
```sql
CONCAT(str1, str2)           -- 连接字符串
SUBSTRING(str, start, len)   -- 截取字符串
LTRIM(RTRIM(str))            -- 去除空格
UPPER(str) / LOWER(str)      -- 大小写转换
LEN(str)                     -- 字符串长度
CHARINDEX(find, str)         -- 查找位置
```

### 日期函数
```sql
GETDATE()                    -- 当前时间
CAST(value AS DATE)          -- 转换为日期
DATEADD(DAY, n, date)        -- 日期加减
DATEDIFF(DAY, date1, date2)  -- 日期差
FORMAT(date, 'yyyy-MM-dd')   -- 日期格式化
```

### 聚合函数
```sql
COUNT(*), SUM(col), AVG(col), MAX(col), MIN(col)
```

### NULL 处理
```sql
ISNULL(column, default_value)    -- 替换 NULL
COALESCE(col1, col2, default)    -- 返回第一个非 NULL 值
NULLIF(col1, col2)               -- 相等时返回 NULL
```
