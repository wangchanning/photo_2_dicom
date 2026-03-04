import pyodbc
import oracledb
from dbutils.pooled_db import PooledDB
from abc import ABC, abstractmethod
from typing import Union
from log_config import log


class Database(ABC):
    @abstractmethod
    def _create_connection(self):
        pass

    @abstractmethod
    def execute_query(self, sql):
        pass

    @abstractmethod
    def execute_update(self, sql):
        pass

    @abstractmethod
    def close_connection(self):
        pass


class MssqlDatabase(Database):
    def __init__(self, conn_conf):
        self.conn_conf = conn_conf
        self._pool = self._create_connection()

    def _create_connection(self):
        pool = PooledDB(
            creator=pyodbc,
            mincached=3,
            maxcached=5,
            maxconnections=5,
            blocking=True,
            **self.conn_conf
        )
        return pool

    def execute_query(self, sql):
        conn = self._pool.connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

    def execute_update(self, sql):
        conn = self._pool.connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.commit()
        cursor.close()
        conn.close()
        log.info(f'数据库更新成功： {sql}')

    def close_connection(self):
        self._pool.close()


class OracleDatabase(Database):

    def __init__(self, conn_conf):
        oracledb.init_oracle_client(lib_dir='instantclient_11_2')
        self._conn_conf = conn_conf
        self._pool = self._create_connection()

    def _create_connection(self):
        pool = oracledb.create_pool(**self._conn_conf,
                                    min=1,
                                    max=3,
                                    increment=1)
        return pool

    def execute_query(self, sql):
        conn = self._pool.acquire()
        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        cursor.close()
        self._pool.release(conn)
        return result if result else [(None, None)]

    def execute_update(self, sql):
        conn = self._pool.acquire()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
            conn.commit()
            log.info(f'数据库更新成功：{sql}')
        except Exception as e:
            conn.rollback()
            log.error(f'数据库更新失败：{sql}', exc_info=True)
            raise
        finally:
            self._pool.release(conn)

    def close_connection(self):
        self._pool.close()


class DatabaseFactory:

    @staticmethod
    def create_database(db_type, conn_conf) -> Union[OracleDatabase, MssqlDatabase]:
        factory = {
            'sqlserver': MssqlDatabase,
            'oracle': OracleDatabase
        }
        db_class = factory.get(db_type)
        if db_class is None:
            raise ValueError(f"Unsupported database type: {db_type}")
        return db_class(conn_conf)
