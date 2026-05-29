#!/usr/bin/env python3
"""MySQL 数据库表结构查询工具 (使用 PyMySQL)"""

import argparse
import json
import sys

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "pymysql 未安装",
        "message": "请运行: pip install pymysql"
    }, ensure_ascii=False))
    sys.exit(1)


def get_table_schema(host: str, port: int, user: str, password: str, database: str, table: str) -> dict:
    """获取指定表的结构信息"""
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        cursor = connection.cursor()
        
        # 查询表结构
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        
        # 查询索引信息
        cursor.execute(f"SHOW INDEX FROM `{table}`")
        indexes = cursor.fetchall()
        
        # 查询表信息
        query = """
            SELECT 
                TABLE_ROWS as row_count,
                ENGINE as engine,
                TABLE_COLLATION as collation,
                CREATE_TIME as create_time,
                UPDATE_TIME as update_time,
                TABLE_COMMENT as comment
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """
        cursor.execute(query, (database, table))
        table_info = cursor.fetchone()
        
        # 处理日期时间字段
        if table_info:
            for key in ['create_time', 'update_time']:
                if table_info.get(key):
                    table_info[key] = str(table_info[key])
        
        cursor.close()
        connection.close()
        
        # 整理索引信息
        index_map = {}
        for idx in indexes:
            idx_name = idx['Key_name']
            if idx_name not in index_map:
                index_map[idx_name] = {
                    "name": idx_name,
                    "unique": not idx['Non_unique'],
                    "columns": []
                }
            index_map[idx_name]["columns"].append(idx['Column_name'])
        
        return {
            "success": True,
            "data": {
                "table": table,
                "database": database,
                "columns": columns,
                "indexes": list(index_map.values()),
                "table_info": table_info
            },
            "message": f"表 {table} 结构查询成功"
        }
    except pymysql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"查询表 {table} 结构失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看 MySQL 表结构")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    parser.add_argument("--table", required=True, help="表名")
    
    args = parser.parse_args()
    
    result = get_table_schema(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        table=args.table
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
