#!/usr/bin/env python3
"""MSSQL 数据库连接测试工具"""

import argparse
import json
import sys

try:
    import pymssql
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "pymssql 未安装",
        "message": "请运行: pip install pymssql (macOS 需先执行 brew install freetds)"
    }, ensure_ascii=False))
    sys.exit(1)


def test_connection(server: str, port: int, user: str, password: str, database: str) -> dict:
    """测试 MSSQL 数据库连接"""
    try:
        connection = pymssql.connect(
            server=server,
            port=port,
            user=user,
            password=password,
            database=database,
            login_timeout=10
        )
        
        cursor = connection.cursor()
        
        # 获取服务器版本
        cursor.execute("SELECT @@VERSION")
        version_row = cursor.fetchone()
        server_version = version_row[0].split('\n')[0] if version_row else "Unknown"
        
        # 获取当前数据库
        cursor.execute("SELECT DB_NAME()")
        current_db = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "server_version": server_version,
                "current_database": current_db,
                "server": server,
                "port": port,
                "user": user
            },
            "message": "数据库连接成功"
        }
    except pymssql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库连接失败"
        }


def main():
    parser = argparse.ArgumentParser(description="测试 MSSQL 数据库连接")
    parser.add_argument("--server", default="localhost", help="数据库服务器地址")
    parser.add_argument("--port", type=int, default=1433, help="数据库端口")
    parser.add_argument("--user", default="sa", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = test_connection(
        server=args.server,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
