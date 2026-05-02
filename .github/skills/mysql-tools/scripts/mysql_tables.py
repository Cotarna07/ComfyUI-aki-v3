#!/usr/bin/env python3
"""MySQL 数据库表列表查询工具 (使用 PyMySQL)"""

import argparse
import json
import sys
from decimal import Decimal

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


class CustomJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 Decimal 类型"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def list_tables(host: str, port: int, user: str, password: str, database: str) -> dict:
    """列出数据库中的所有表"""
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
        
        # 查询所有表和视图
        query = """
            SELECT 
                TABLE_NAME as table_name,
                TABLE_TYPE as table_type,
                ENGINE as engine,
                TABLE_ROWS as row_count,
                ROUND(DATA_LENGTH / 1024 / 1024, 2) as data_size_mb,
                TABLE_COMMENT as comment
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """
        cursor.execute(query, (database,))
        tables = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "database": database,
                "table_count": len(tables),
                "tables": tables
            },
            "message": f"找到 {len(tables)} 个表"
        }
    except pymysql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "查询表列表失败"
        }


def main():
    parser = argparse.ArgumentParser(description="列出 MySQL 数据库中的所有表")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = list_tables(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
