import configparser


MS_CONF = {
    'driver': '{SQL Server}',
    'server': '192.168.10.83',
    'port': '1433',
    'uid': 'sa',
    'pwd': 'honlivhp',
    'database': 'GNKDB',
    'charset': 'utf8'

}

ORA_CONF = {
    'user': 'system',
    'password': 'manager',
    'dsn': '192.168.10.42' + ':' + '1521' + '/' + 'oracle10'
}

# 创建配置解析器对象
config = configparser.ConfigParser()

# 读取配置文件
config.read('config.ini')


# 读取文件路径配置
INPUT_BASE_PATH = config.get('Paths', 'InputBasePath')


# 读取文件上传 URL 配置
URL = config.get('PACS', 'Url')

User = config.get('PACS', 'User')

Password = config.get('PACS', 'Password')
