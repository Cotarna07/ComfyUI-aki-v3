#!/usr/bin/env python3
"""达梦数据库 DM8 表结构查询工具 (使用 jaydebeapi JDBC 驱动)"""

import argparse
import json
import sys
import os
from decimal import Decimal
from datetime import datetime, date

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
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
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


def get_table_schema(host: str, port: int, user: str, password: str, table: str, 
                     database: str = None, schema: str = None) -> dict:
    """获取指定表的结构信息"""
    try:
        connection = get_connection(host, port, user, password, database)
        cursor = connection.cursor()
        
        if not schema:
            cursor.execute("SELECT USER FROM DUAL")
            schema = cursor.fetchone()[0]
        
        # 查询表结构
        columns_query = """
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                DATA_PRECISION,
                DATA_SCALE,
                NULLABLE,
                DATA_DEFAULT
            FROM ALL_TAB_COLUMNS 
            WHERE OWNER = ? AND TABLE_NAME = ?
            ORDER BY COLUMN_ID
        """
        cursor.execute(columns_query, [schema.upper(), table.upper()])
        col_names = ['column_name', 'data_type', 'data_length', 'data_precision', 'data_scale', 'is_nullable', 'default_value']
        columns = [dict(zip(col_names, row)) for row in cursor.fetchall()]
        
        # 查询主键信息
        pk_query = """
            SELECT cc.COLUMN_NAME
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc ON c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME 
                AND c.OWNER = cc.OWNER
            WHERE c.OWNER = ? 
                AND c.TABLE_NAME = ? 
                AND c.CONSTRAINT_TYPE = 'P'
            ORDER BY cc.POSITION
        """
        cursor.execute(pk_query, [schema.upper(), table.upper()])
        pk_columns = [row[0] for row in cursor.fetchall()]
        
        for col in columns:
            col['is_primary_key'] = 'YES' if col['column_name'] in pk_columns else 'NO'
        
        # 查询索引信息
        indexes_query = """
            SELECT 
                ai.INDEX_NAME,
                ai.UNIQUENESS,
                aic.COLUMN_NAME
            FROM ALL_IND_COLUMNS aic
            JOIN ALL_INDEXES ai ON aic.INDEX_NAME = ai.INDEX_NAME AND aic.INDEX_OWNER = ai.OWNER
            WHERE aic.TABLE_OWNER = ? AND aic.TABLE_NAME = ?
            ORDER BY aic.INDEX_NAME, aic.COLUMN_POSITION
        """
        cursor.execute(indexes_query, [schema.upper(), table.upper()])
        indexes_rows = cursor.fetchall()
        
        index_map = {}
        for row in indexes_rows:
            idx_name = row[0]
            if idx_name not in index_map:
                index_map[idx_name] = {
                    "name": idx_name,
                    "unique": row[1] == 'UNIQUE',
                    "columns": []
                }
            index_map[idx_name]["columns"].append(row[2])
        
        # 查询表信息
        table_info_query = """
            SELECT NUM_ROWS, LAST_ANALYZED
            FROM ALL_TABLES 
            WHERE OWNER = ? AND TABLE_NAME = ?
        """
        cursor.execute(table_info_query, [schema.upper(), table.upper()])
        table_info_row = cursor.fetchone()
        table_info = None
        if table_info_row:
            table_info = {
                'row_count': table_info_row[0],
                'last_analyzed': str(table_info_row[1]) if table_info_row[1] else None
            }
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "table": table,
                "schema": schema,
                "columns": columns,
                "indexes": list(index_map.values()),
                "table_info": table_info
            },
            "message": f"表 {schema}.{table} 结构查询成功"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"查询表 {table} 结构失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看达梦数据库表结构")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=5236, help="数据库端口")
    parser.add_argument("--user", default="SYSDBA", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", default=None, help="数据库名称（可选）")
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--schema", default=None, help="Schema 名称（默认为当前用户）")
    
    args = parser.parse_args()
    
    result = get_table_schema(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        table=args.table,
        database=args.database,
        schema=args.schema
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2, cls=CustomJSONEncoder))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
