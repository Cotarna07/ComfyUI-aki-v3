#!/usr/bin/env python3
"""MSSQL 数据库表列表查询工具"""

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


def list_tables(server: str, port: int, user: str, password: str, database: str) -> dict:
    """列出数据库中的所有表"""
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
        
        # 查询所有表和视图
        query = """
            SELECT 
                t.TABLE_SCHEMA as schema_name,
                t.TABLE_NAME as table_name,
                t.TABLE_TYPE as table_type,
                ISNULL(p.rows, 0) as row_count,
                CAST(ROUND((SUM(a.total_pages) * 8) / 1024.0, 2) AS DECIMAL(18,2)) as data_size_mb
            FROM INFORMATION_SCHEMA.TABLES t
            LEFT JOIN sys.tables st ON t.TABLE_NAME = st.name AND t.TABLE_SCHEMA = SCHEMA_NAME(st.schema_id)
            LEFT JOIN sys.partitions p ON st.object_id = p.object_id AND p.index_id IN (0,1)
            LEFT JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE t.TABLE_CATALOG = %s
            GROUP BY t.TABLE_SCHEMA, t.TABLE_NAME, t.TABLE_TYPE, p.rows
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """
        cursor.execute(query, (database,))
        tables = cursor.fetchall()
        
        # 转换 Decimal 类型
        for table in tables:
            if table.get('data_size_mb') is not None:
                table['data_size_mb'] = float(table['data_size_mb'])
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "database": database,
                "table_count": len(tables),
                "tables": tables
            },
            "message": f"找到 {len(tables)} 个表"
        }
    except pymssql.Error as e:
        return {
            "success": False,
            "error": str(e),
            "message": "查询表列表失败"
        }


def main():
    parser = argparse.ArgumentParser(description="列出 MSSQL 数据库中的所有表")
    parser.add_argument("--server", default="localhost", help="数据库服务器地址")
    parser.add_argument("--port", type=int, default=1433, help="数据库端口")
    parser.add_argument("--user", default="sa", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", required=True, help="数据库名称")
    
    args = parser.parse_args()
    
    result = list_tables(
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
