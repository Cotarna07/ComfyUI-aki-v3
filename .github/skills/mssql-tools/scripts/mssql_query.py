#!/usr/bin/env python3
"""MSSQL SQL 查询执行工具"""

import argparse
import json
import sys
from decimal import Decimal
from datetime import datetime, date, timedelta

try:
    import pymssql
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "pymssql 未安装",
        "message": "请运行: pip install pymssql (macOS 需先执行 brew install freetds)"
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


def execute_query(server: str, port: int, user: str, password: str, database: str, query: str) -> dict:
    """执行 SQL 查询"""
    try:
        connection = pymssql.connect(
            server=server,
            port=port,
            user=user,
            password=password,
            database=database,
            login_timeout=10
        )
        
        cursor = connection.cursor(as_dict=True)
        
        # 判断是否为 SELECT 查询
        query_upper = query.strip().upper()
        is_select = (
            query_upper.startswith("SELECT") or 
            query_upper.startswith("EXEC") or 
            query_upper.startswith("SP_") or
            query_upper.startswith("WITH")
        )
        
        cursor.execute(query)
        
        if is_select:
            rows = cursor.fetchall()
            # 获取列名
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
                    "affected_rows": affected_rows
                },
                "message": f"执行成功，影响 {affected_rows} 行"
            }
        
        cursor.close()
        connection.close()
        
        return result
    except pymssql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "SQL 执行失败"
        }


def main():
    parser = argparse.ArgumentParser(description="执行 MSSQL SQL 查询")
    parser.add_argument("--server", default="localhost", help="数据库服务器地址")
    parser.add_argument("--port", type=int, default=1433, help="数据库端口")
    parser.add_argument("--user", default="sa", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    parser.add_argument("--query", required=True, help="要执行的 SQL 语句")
    
    args = parser.parse_args()
    
    result = execute_query(
        server=args.server,
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
