# 常用 MySQL 查询参考

## 数据库管理

### 查看所有数据库
```sql
SHOW DATABASES;
```

### 查看数据库大小
```sql
SELECT 
    TABLE_SCHEMA as database_name,
    ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as size_mb
FROM information_schema.TABLES 
GROUP BY TABLE_SCHEMA
ORDER BY size_mb DESC;
```

### 查看数据库字符集
```sql
SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME 
FROM information_schema.SCHEMATA 
WHERE SCHEMA_NAME = 'your_database';
```

## 表操作

### 查看表结构
```sql
DESCRIBE table_name;
-- 或更详细
SHOW CREATE TABLE table_name;
```

### 查看表索引
```sql
SHOW INDEX FROM table_name;
```

### 查看表状态
```sql
SHOW TABLE STATUS LIKE 'table_name';
```

### 查看所有外键
```sql
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE REFERENCED_TABLE_SCHEMA = 'your_database'
    AND REFERENCED_TABLE_NAME IS NOT NULL;
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
-- 随机抽取 10 条
SELECT * FROM table_name ORDER BY RAND() LIMIT 10;

-- 分页查询
SELECT * FROM table_name LIMIT 10 OFFSET 0;
```

## 性能分析

### 查看慢查询
```sql
SHOW VARIABLES LIKE 'slow_query%';
```

### 查看当前连接
```sql
SHOW PROCESSLIST;
```

### 查看表锁
```sql
SHOW OPEN TABLES WHERE In_use > 0;
```

### 分析查询计划
```sql
EXPLAIN SELECT * FROM table_name WHERE column = 'value';
```

## 数据导出

### 导出为 CSV 格式
```sql
SELECT * FROM table_name
INTO OUTFILE '/tmp/export.csv'
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n';
```

### 查询结果格式化
```sql
-- 日期格式化
SELECT DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') FROM table_name;

-- 数字格式化
SELECT FORMAT(price, 2) FROM table_name;
```

## 数据修改

### 安全更新模式
```sql
-- 关闭安全模式（允许无 WHERE 的 UPDATE/DELETE）
SET SQL_SAFE_UPDATES = 0;

-- 开启安全模式
SET SQL_SAFE_UPDATES = 1;
```

### 批量更新
```sql
UPDATE table_name 
SET column = 'new_value' 
WHERE condition;
```

### 批量删除
```sql
DELETE FROM table_name WHERE condition;
```

## 常用函数

### 字符串函数
```sql
CONCAT(str1, str2)           -- 连接字符串
SUBSTRING(str, start, len)   -- 截取字符串
TRIM(str)                    -- 去除空格
UPPER(str) / LOWER(str)      -- 大小写转换
LENGTH(str)                  -- 字符串长度
```

### 日期函数
```sql
NOW()                        -- 当前时间
CURDATE()                    -- 当前日期
DATE_ADD(date, INTERVAL n DAY)  -- 日期加减
DATEDIFF(date1, date2)       -- 日期差
```

### 聚合函数
```sql
COUNT(*), SUM(col), AVG(col), MAX(col), MIN(col)
```
