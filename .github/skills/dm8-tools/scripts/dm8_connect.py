#!/usr/bin/env python3
"""达梦数据库 DM8 连接测试工具 (使用 jaydebeapi JDBC 驱动)"""

import argparse
import json
import sys
import os

try:
    import jaydebeapi
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "jaydebeapi 未安装",
        "message": "请运行: pip install jaydebeapi JPype1"
    }, ensure_ascii=False))
    sys.exit(1)


def find_dm_jdbc_driver() -> str:
    """查找达梦 JDBC 驱动路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    possible_paths = [
        # 标准位置：assets 目录
        os.path.join(script_dir, "..", "assets", "DmJdbcDriver18.jar"),
        # 兼容位置
        os.path.join(script_dir, "DmJdbcDriver18.jar"),
        # Linux/macOS 系统位置
        "/opt/dmdbms/drivers/jdbc/DmJdbcDriver18.jar",
        os.path.expanduser("~/dmdbms/drivers/jdbc/DmJdbcDriver18.jar"),
        # Windows 常见位置
        "C:\\dmdbms\\drivers\\jdbc\\DmJdbcDriver18.jar",
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'dmdbms', 'drivers', 'jdbc', 'DmJdbcDriver18.jar'),
    ]
    
    # 检查环境变量
    dm_home = os.environ.get('DM_HOME')
    if dm_home:
        possible_paths.insert(0, os.path.join(dm_home, "drivers", "jdbc", "DmJdbcDriver18.jar"))
    
    for path in possible_paths:
        normalized_path = os.path.normpath(path)
        if os.path.exists(normalized_path):
            return normalized_path
    
    return None


def test_connection(host: str, port: int, user: str, password: str, database: str = None) -> dict:
    """测试达梦数据库连接"""
    try:
        jdbc_driver_path = find_dm_jdbc_driver()
        if not jdbc_driver_path:
            return {
                "success": False,
                "error": "未找到达梦 JDBC 驱动 (DmJdbcDriver18.jar)",
                "message": "请将驱动放置在 assets/ 目录下，或设置 DM_HOME 环境变量"
            }
        
        jdbc_url = f"jdbc:dm://{host}:{port}"
        if database:
            jdbc_url += f"/{database}"
        
        connection = jaydebeapi.connect(
            "dm.jdbc.driver.DmDriver",
            jdbc_url,
            [user, password],
            jdbc_driver_path
        )
        
        cursor = connection.cursor()
        
        # 获取版本信息
        cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
        version_row = cursor.fetchone()
        server_version = version_row[0] if version_row else "Unknown"
        
        # 获取当前用户
        cursor.execute("SELECT USER FROM DUAL")
        current_user = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return {
            "success": True,
            "data": {
                "server_version": server_version,
                "current_user": current_user,
                "host": host,
                "port": port,
                "driver": "jaydebeapi (JDBC)",
                "jdbc_driver_path": jdbc_driver_path
            },
            "message": "数据库连接成功"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库连接失败"
        }


def main():
    parser = argparse.ArgumentParser(description="测试达梦数据库连接")
    parser.add_argument("--host", default="localhost", help="数据库主机地址")
    parser.add_argument("--port", type=int, default=5236, help="数据库端口")
    parser.add_argument("--user", default="SYSDBA", help="数据库用户名")
    parser.add_argument("--password", required=True, help="数据库密码")
    parser.add_argument("--database", default=None, help="数据库名称（可选）")
    
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
