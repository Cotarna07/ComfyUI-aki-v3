#!/usr/bin/env python3
"""MySQL SQL 查询执行工具 (使用 PyMySQL)"""

import argparse
import json
import sys
from decimal import Decimal
from datetime import datetime, date, timedelta

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
    """自定义 JSON 编码器，处理特殊数据类型"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        return super().default(obj)


def execute_query(host: str, port: int, user: str, password: str, database: str, query: str) -> dict:
    """执行 SQL 查询"""
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
        
        # 判断是否为 SELECT 查询
        query_upper = query.strip().upper()
        is_select = (
            query_upper.startswith("SELECT") or 
            query_upper.startswith("SHOW") or 
            query_upper.startswith("DESCRIBE") or 
            query_upper.startswith("EXPLAIN")
        )
        
        cursor.execute(query)
        
        if is_select:
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            result = {
                "success": True,
                "data": {
                    "rows": rows,
                    "row_count": len(rows),
                    "columns": columns
                },
                "message": f"查询成功，返回 {len(rows)} 行"
            }
        else:
            connection.commit()
            affected_rows = cursor.rowcount
            result = {
                "success": True,
                "data": {
                    "affected_rows": affected_rows,
                    "last_insert_id": cursor.lastrowid
                },
                "message": f"执行成功，影响 {affected_rows} 行"
            }
        
        cursor.close()
        connection.close()
        
        return result
    except pymysql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "SQL 执行失败"
        }


def main():
    parser = argparse.ArgumentParser(description="执行 MySQL SQL 查询")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    parser.add_argument("--query", required=True, help="要执行的 SQL 语句")
    
    args = parser.parse_args()
    
    result = execute_query(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        query=args.query
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
