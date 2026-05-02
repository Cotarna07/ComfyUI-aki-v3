#!/usr/bin/env python3
"""达梦数据库 DM8 表列表查询工具 (使用 jaydebeapi JDBC 驱动)"""

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


def list_tables(host: str, port: int, user: str, password: str, database: str = None, schema: str = None) -> dict:
    """列出数据库中的所有表"""
    try:
        connection = get_connection(host, port, user, password, database)
        cursor = connection.cursor()
        
        if not schema:
            cursor.execute("SELECT USER FROM DUAL")
            schema = cursor.fetchone()[0]
        
        query = """
            SELECT 
                OWNER as schema_name,
                TABLE_NAME as table_name,
                'TABLE' as table_type,
                NUM_ROWS as row_count
            FROM ALL_TABLES 
            WHERE OWNER = ?
            UNION ALL
            SELECT 
                OWNER as schema_name,
                VIEW_NAME as table_name,
                'VIEW' as table_type,
                NULL as row_count
            FROM ALL_VIEWS 
            WHERE OWNER = ?
            ORDER BY 2
        """
        cursor.execute(query, [schema.upper(), schema.upper()])
        
        columns = ['schema_name', 'table_name', 'table_type', 'row_count']
        tables = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "schema": schema,
                "table_count": len(tables),
                "tables": tables
            },
            "message": f"找到 {len(tables)} 个表"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "查询表列表失败"
        }


def main():
    parser = argparse.ArgumentParser(description="列出达梦数据库中的所有表")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=5236, help="数据库端口")
    parser.add_argument("--user", default="SYSDBA", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", default=None, help="数据库名称（可选）")
    parser.add_argument("--schema", default=None, help="Schema 名称（默认为当前用户）")
    
    args = parser.parse_args()
    
    result = list_tables(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        schema=args.schema
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
