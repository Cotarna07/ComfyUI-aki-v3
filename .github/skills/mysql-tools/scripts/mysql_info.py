#!/usr/bin/env python3
"""MySQL 数据库信息查询工具 (使用 PyMySQL)"""

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


def get_database_info(host: str, port: int, user: str, password: str, database: str) -> dict:
    """获取数据库详细信息"""
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
        
        # 获取服务器版本信息
        cursor.execute("SELECT VERSION()")
        server_version = cursor.fetchone()['VERSION()']
        
        # 获取数据库大小信息
        size_query = """
            SELECT 
                TABLE_SCHEMA as db_name,
                COUNT(*) as table_count,
                ROUND(SUM(DATA_LENGTH) / 1024 / 1024, 2) as data_size_mb,
                ROUND(SUM(INDEX_LENGTH) / 1024 / 1024, 2) as index_size_mb,
                ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) as total_size_mb
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s
            GROUP BY TABLE_SCHEMA
        """
        cursor.execute(size_query, (database,))
        size_info = cursor.fetchone()
        
        # 获取数据库字符集和排序规则
        charset_query = """
            SELECT 
                DEFAULT_CHARACTER_SET_NAME as charset,
                DEFAULT_COLLATION_NAME as collation
            FROM information_schema.SCHEMATA 
            WHERE SCHEMA_NAME = %s
        """
        cursor.execute(charset_query, (database,))
        charset_info = cursor.fetchone()
        
        # 获取服务器状态信息
        cursor.execute("SHOW STATUS LIKE 'Uptime'")
        uptime_row = cursor.fetchone()
        uptime_seconds = int(uptime_row['Value']) if uptime_row else 0
        
        # 获取连接数信息
        cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
        threads_row = cursor.fetchone()
        threads_connected = int(threads_row['Value']) if threads_row else 0
        
        # 获取最大连接数
        cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
        max_conn_row = cursor.fetchone()
        max_connections = int(max_conn_row['Value']) if max_conn_row else 0
        
        cursor.close()
        connection.close()
        
        # 格式化运行时间
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_formatted = f"{days}天 {hours}时 {minutes}分"
        
        return {
            "success": True,
            "data": {
                "server": {
                    "version": server_version,
                    "host": host,
                    "port": port,
                    "uptime": uptime_formatted,
                    "uptime_seconds": uptime_seconds
                },
                "database": {
                    "name": database,
                    "charset": charset_info.get('charset') if charset_info else None,
                    "collation": charset_info.get('collation') if charset_info else None,
                    "table_count": size_info.get('table_count') if size_info else 0,
                    "data_size_mb": float(size_info.get('data_size_mb') or 0) if size_info else 0,
                    "index_size_mb": float(size_info.get('index_size_mb') or 0) if size_info else 0,
                    "total_size_mb": float(size_info.get('total_size_mb') or 0) if size_info else 0
                },
                "connections": {
                    "current": threads_connected,
                    "max": max_connections
                }
            },
            "message": "数据库信息查询成功"
        }
    except pymysql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库信息查询失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看 MySQL 数据库信息")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=3306, help="数据库端口")
    parser.add_argument("--user", default="root", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = get_database_info(
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
