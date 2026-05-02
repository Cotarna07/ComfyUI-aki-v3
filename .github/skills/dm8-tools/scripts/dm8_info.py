#!/usr/bin/env python3
"""达梦数据库 DM8 信息查询工具 (使用 jaydebeapi JDBC 驱动)"""

import argparse
import json
import sys
import os
from decimal import Decimal

try:
    import jaydebeapi
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "jaydebeapi 未安装",
        "message": "请运行: pip install jaydebeapi JPype1"
    }, ensure_ascii=False))
    sys.exit(1)


class CustomJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def find_dm_jdbc_driver() -> str:
    """查找达梦 JDBC 驱动路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    possible_paths = [
        os.path.join(script_dir, "..", "assets", "DmJdbcDriver18.jar"),
        os.path.join(script_dir, "DmJdbcDriver18.jar"),
        "/opt/dmdbms/drivers/jdbc/DmJdbcDriver18.jar",
        os.path.expanduser("~/dmdbms/drivers/jdbc/DmJdbcDriver18.jar"),
        "C:\\dmdbms\\drivers\\jdbc\\DmJdbcDriver18.jar",
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'dmdbms', 'drivers', 'jdbc', 'DmJdbcDriver18.jar'),
    ]
    
    dm_home = os.environ.get('DM_HOME')
    if dm_home:
        possible_paths.insert(0, os.path.join(dm_home, "drivers", "jdbc", "DmJdbcDriver18.jar"))
    
    for path in possible_paths:
        normalized_path = os.path.normpath(path)
        if os.path.exists(normalized_path):
            return normalized_path
    return None


def get_connection(host: str, port: int, user: str, password: str, database: str = None):
    """获取数据库连接"""
    jdbc_driver_path = find_dm_jdbc_driver()
    if not jdbc_driver_path:
        raise Exception("未找到达梦 JDBC 驱动 (DmJdbcDriver18.jar)")
    
    jdbc_url = f"jdbc:dm://{host}:{port}"
    if database:
        jdbc_url += f"/{database}"
    
    return jaydebeapi.connect(
        "dm.jdbc.driver.DmDriver",
        jdbc_url,
        [user, password],
        jdbc_driver_path
    )


def get_database_info(host: str, port: int, user: str, password: str, database: str = None) -> dict:
    """获取数据库详细信息"""
    try:
        connection = get_connection(host, port, user, password, database)
        cursor = connection.cursor()
        
        # 获取服务器版本信息
        cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
        version_row = cursor.fetchone()
        server_version = version_row[0] if version_row else "Unknown"
        
        # 获取实例名称
        try:
            cursor.execute("SELECT INSTANCE_NAME FROM V$INSTANCE")
            instance_row = cursor.fetchone()
            instance_name = instance_row[0] if instance_row else "Unknown"
        except Exception:
            instance_name = "Unknown"
        
        # 获取数据库名称
        try:
            cursor.execute("SELECT NAME FROM V$DATABASE")
            db_row = cursor.fetchone()
            db_name = db_row[0] if db_row else "Unknown"
        except Exception:
            db_name = "Unknown"
        
        # 获取当前用户
        cursor.execute("SELECT USER FROM DUAL")
        current_user = cursor.fetchone()[0]
        
        # 获取表和视图数量
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM ALL_TABLES WHERE OWNER = USER),
                (SELECT COUNT(*) FROM ALL_VIEWS WHERE OWNER = USER)
            FROM DUAL
        """)
        count_row = cursor.fetchone()
        table_count = count_row[0] if count_row else 0
        view_count = count_row[1] if count_row else 0
        
        # 获取会话数
        try:
            cursor.execute("SELECT COUNT(*) FROM V$SESSIONS")
            session_row = cursor.fetchone()
            current_sessions = session_row[0] if session_row else 0
        except Exception:
            current_sessions = 0
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "server": {
                    "version": server_version,
                    "instance_name": instance_name,
                    "host": host,
                    "port": port,
                    "driver": "jaydebeapi (JDBC)"
                },
                "database": {
                    "name": db_name,
                    "current_user": current_user,
                    "table_count": table_count,
                    "view_count": view_count
                },
                "sessions": {
                    "current": current_sessions
                }
            },
            "message": "数据库信息查询成功"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库信息查询失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看达梦数据库信息")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=5236, help="数据库端口")
    parser.add_argument("--user", default="SYSDBA", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", default=None, help="数据库名称（可选）")
    
    args = parser.parse_args()
    
    result = get_database_info(
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
