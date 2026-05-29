#!/usr/bin/env python3
"""MSSQL 数据库信息查询工具"""

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


def get_database_info(server: str, port: int, user: str, password: str, database: str) -> dict:
    """获取数据库详细信息"""
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
        
        # 获取服务器版本信息
        cursor.execute("SELECT @@VERSION as version")
        version_row = cursor.fetchone()
        server_version = version_row['version'].split('\n')[0] if version_row else "Unknown"
        
        # 获取服务器名称
        cursor.execute("SELECT @@SERVERNAME as server_name")
        server_name = cursor.fetchone()['server_name']
        
        # 获取数据库大小信息
        size_query = """
            SELECT 
                DB_NAME() as db_name,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE') as table_count,
                (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'VIEW') as view_count,
                CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(18,2)) as total_size_mb
            FROM sys.database_files
        """
        cursor.execute(size_query)
        size_info = cursor.fetchone()
        
        # 获取数据库属性
        db_info_query = """
            SELECT 
                d.collation_name,
                d.recovery_model_desc as recovery_model,
                d.state_desc as state,
                d.create_date
            FROM sys.databases d
            WHERE d.name = DB_NAME()
        """
        cursor.execute(db_info_query)
        db_props = cursor.fetchone()
        
        # 获取连接数信息
        cursor.execute("""
            SELECT 
                COUNT(*) as current_connections
            FROM sys.dm_exec_sessions 
            WHERE database_id = DB_ID()
        """)
        conn_info = cursor.fetchone()
        
        # 获取最大连接数
        cursor.execute("SELECT @@MAX_CONNECTIONS as max_connections")
        max_conn = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "server": {
                    "version": server_version,
                    "name": server_name,
                    "host": server,
                    "port": port
                },
                "database": {
                    "name": database,
                    "collation": db_props['collation_name'] if db_props else None,
                    "recovery_model": db_props['recovery_model'] if db_props else None,
                    "state": db_props['state'] if db_props else None,
                    "create_date": str(db_props['create_date']) if db_props and db_props.get('create_date') else None,
                    "table_count": size_info['table_count'] if size_info else 0,
                    "view_count": size_info['view_count'] if size_info else 0,
                    "total_size_mb": float(size_info['total_size_mb']) if size_info and size_info.get('total_size_mb') else 0
                },
                "connections": {
                    "current": conn_info['current_connections'] if conn_info else 0,
                    "max": max_conn['max_connections'] if max_conn else 0
                }
            },
            "message": "数据库信息查询成功"
        }
    except pymssql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库信息查询失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看 MSSQL 数据库信息")
    parser.add_argument("--server", default="localhost", help="数据库服务器地址")
    parser.add_argument("--port", type=int, default=1433, help="数据库端口")
    parser.add_argument("--user", default="sa", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = get_database_info(
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
