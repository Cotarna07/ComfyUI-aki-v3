#!/usr/bin/env python3
"""MSSQL 数据库表结构查询工具"""

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


def get_table_schema(server: str, port: int, user: str, password: str, database: str, table: str, schema: str = "dbo") -> dict:
    """获取指定表的结构信息"""
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
        
        # 查询表结构
        columns_query = """
            SELECT 
                c.COLUMN_NAME as column_name,
                c.DATA_TYPE as data_type,
                c.CHARACTER_MAXIMUM_LENGTH as max_length,
                c.NUMERIC_PRECISION as precision,
                c.NUMERIC_SCALE as scale,
                c.IS_NULLABLE as is_nullable,
                c.COLUMN_DEFAULT as default_value,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'YES' ELSE 'NO' END as is_primary_key
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku 
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA 
                AND c.TABLE_NAME = pk.TABLE_NAME 
                AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = %s AND c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
        """
        cursor.execute(columns_query, (schema, table))
        columns = cursor.fetchall()
        
        # 查询索引信息
        indexes_query = """
            SELECT 
                i.name as index_name,
                i.is_unique,
                COL_NAME(ic.object_id, ic.column_id) as column_name
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = %s AND t.name = %s AND i.name IS NOT NULL
            ORDER BY i.name, ic.key_ordinal
        """
        cursor.execute(indexes_query, (schema, table))
        indexes_rows = cursor.fetchall()
        
        # 整理索引信息
        index_map = {}
        for idx in indexes_rows:
            idx_name = idx['index_name']
            if idx_name not in index_map:
                index_map[idx_name] = {
                    "name": idx_name,
                    "unique": idx['is_unique'],
                    "columns": []
                }
            index_map[idx_name]["columns"].append(idx['column_name'])
        
        # 查询表信息
        table_info_query = """
            SELECT 
                p.rows as row_count,
                CAST(ROUND((SUM(a.total_pages) * 8) / 1024.0, 2) AS DECIMAL(18,2)) as total_size_mb,
                t.create_date,
                t.modify_date
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
            LEFT JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE s.name = %s AND t.name = %s
            GROUP BY p.rows, t.create_date, t.modify_date
        """
        cursor.execute(table_info_query, (schema, table))
        table_info = cursor.fetchone()
        
        if table_info:
            table_info['total_size_mb'] = float(table_info['total_size_mb']) if table_info.get('total_size_mb') else 0
            table_info['create_date'] = str(table_info['create_date']) if table_info.get('create_date') else None
            table_info['modify_date'] = str(table_info['modify_date']) if table_info.get('modify_date') else None
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "table": table,
                "schema": schema,
                "database": database,
                "columns": columns,
                "indexes": list(index_map.values()),
                "table_info": table_info
            },
            "message": f"表 {schema}.{table} 结构查询成功"
        }
    except pymssql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"查询表 {table} 结构失败"
        }


def main():
    parser = argparse.ArgumentParser(description="查看 MSSQL 表结构")
    parser.add_argument("--server", default="localhost", help="数据库服务器地址")
    parser.add_argument("--port", type=int, default=1433, help="数据库端口")
    parser.add_argument("--user", default="sa", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    parser.add_argument("--table", required=True, help="表名")
    parser.add_argument("--schema", default="dbo", help="Schema 名称")
    
    args = parser.parse_args()
    
    result = get_table_schema(
        server=args.server,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        table=args.table,
        schema=args.schema
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
