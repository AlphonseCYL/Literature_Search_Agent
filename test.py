from ElasticSearch.ES_conn import ESConnection
from db_utils import DB_NAME, TABLE_NAME, get_mysql_server_connection

es_client = ESConnection()
init_response = es_client.init_index()
print(init_response)



db_client = get_mysql_server_connection()
cursor = db_client.cursor()
response = cursor.execute(f"SELECT * FROM {DB_NAME}.{TABLE_NAME} LIMIT 5")
print(response)

literature_tuple = cursor.fetchall()
print(literature_tuple[0])
print(literature_tuple[0][1])




