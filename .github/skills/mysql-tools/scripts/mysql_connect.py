#!/usr/bin/env python3
"""MySQL 数据库连接测试工具 (使用 PyMySQL)"""

import argparse
import json
import sys

try:
    import pymysql
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "pymysql 未安装",
        "message": "请运行: pip install pymysql"
    }, ensure_ascii=False))
    sys.exit(1)


def test_connection(host: str, port: int, user: str, password: str, database: str) -> dict:
    """测试 MySQL 数据库连接"""
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10
        )
        
        cursor = connection.cursor()
        
        # 获取服务器版本
        cursor.execute("SELECT VERSION()")
        server_version = cursor.fetchone()[0]
        
        # 获取当前数据库
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "server_version": server_version,
                "current_database": current_db,
                "host": host,
                "port": port,
                "user": user
            },
            "message": "数据库连接成功"
        }
    except pymysql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库连接失败"
        }


def main():
    parser = argparse.ArgumentParser(description="测试 MySQL 数据库连接")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = test_connection(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
