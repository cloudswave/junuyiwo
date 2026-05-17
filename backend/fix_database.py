import pymysql
from app.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def fix_daily_characters_table():
    try:
        # 连接数据库
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor()
        
        # 检查是否存在 character 列
        cursor.execute("DESCRIBE daily_characters")
        columns = [col[0] for col in cursor.fetchall()]
        
        if 'character' not in columns:
            # 添加缺失的 character 列
            alter_sql = """
            ALTER TABLE daily_characters 
            ADD COLUMN `character` VARCHAR(10) NOT NULL COMMENT '生字' AFTER record_date
            """
            cursor.execute(alter_sql)
            connection.commit()
            print("成功添加 character 列")
        else:
            print("character 列已存在")
        
        # 检查是否需要添加索引
        cursor.execute("SHOW INDEX FROM daily_characters")
        indexes = [idx[4] for idx in cursor.fetchall()]
        if 'character' not in indexes:
            cursor.execute("ALTER TABLE daily_characters ADD INDEX idx_character (`character`)")
            connection.commit()
            print("成功添加 character 索引")
        else:
            print("character 索引已存在")
            
    except Exception as e:
        print(f"修复过程中发生错误: {e}")
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    fix_daily_characters_table()
