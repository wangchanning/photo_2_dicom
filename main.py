import os
import re
import random
from datetime import datetime
from time import sleep
from queue import Queue, Empty
import threading
import database
import photo2dicom
import setting
import tools
from log_config import log


# 全局退出事件
shutdown_event = threading.Event()

def producer():
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    while not shutdown_event.is_set():
        first_day = tools.get_first_day()
        task_sql = f"SELECT bindingID, exam_no, patientName,patientAge,sex,time,modify_flag,studyUid FROM EXAM.GNK_EQUIP_BIND_PATIENT WHERE (EXAMTIME >= TO_DATE('{first_day}', 'YYYY-MM-DD')  AND  studyUid IS NULL) OR (EXAMTIME >= TO_DATE('{first_day}', 'YYYY-MM-DD') AND modify_flag = '1')"
        results = oracle_conn.execute_query(task_sql)
        for result in results:
            if result[-2] == '1' and result[-1] is None:
                update_modify_flag_sql = f"UPDATE EXAM.GNK_EQUIP_BIND_PATIENT SET modify_flag = NULL WHERE bindingID = '{result[0]}'"
                oracle_conn.execute_update(update_modify_flag_sql)
                log.warning(f'非法的数据：bindingID = {result[0]}，已处理！')
            else:
                bind_id, exam_no, pat_name, pat_age, pat_sex, time, modify_flag, studyuid = result
                pat_id_sql = f"SELECT PATIENT_LOCAL_ID,DATE_OF_BIRTH FROM EXAM.EXAM_MASTER t WHERE EXAM_NO = '{exam_no}' AND RESULT_STATUS = '4' AND PATIENT_LOCAL_ID IS NOT NULL"
                [(pat_loc_id, birth,)] = oracle_conn.execute_query(pat_id_sql)

                if pat_loc_id is not None:

                    path_time = datetime.strftime(time, '%Y\\%m\\%d')
                    dir_path = str(os.path.join(setting.INPUT_BASE_PATH, path_time, bind_id))
                    try:
                        photo_list = os.listdir(dir_path)
                        if len(photo_list):
                            filtered_photos = [file for file in photo_list if not chinese_pattern.search(file)]
                            if len(filtered_photos):
                                pat_info_tup = (bind_id, exam_no, pat_name, pat_age, pat_sex, time, modify_flag,
                                                pat_loc_id, studyuid, birth if birth else '', dir_path, filtered_photos)
                            
                                if pat_info_tup not in q.queue:
                                    q.put(pat_info_tup, block=True)
                    except:
                        pass

        # 可中断的 sleep
        for _ in range(10):
            if shutdown_event.is_set():
                break
            sleep(1)


def consumer():
    while True:
        sleep(random.random())
        pat_info_tup = q.get(block=True)

        if pat_info_tup == "quit":
            q.task_done()
            log.info("消费者收到退出信号，正在退出...")
            return
    
        studyUid, modify_flag = (pat_info_tup[8], pat_info_tup[6])
        
        if (modify_flag != '1' and studyUid is None) or (modify_flag == '1' and studyUid is not None):

            try:
                dir_path = pat_info_tup[-2]
                photo_list = pat_info_tup[-1]
                todicom.to_dicom(pat_info_tup, dir_path, photo_list)
                q.task_done()

            except Exception as e:                
                q.task_done()

        else:
            q.task_done()

        if q.empty():
            print('当前任务队列为空，正在等待下发任务。。。\r', end='')


def signal_handler(signum, frame):
    log.warning('收到退出信号，正在关闭程序...')
    shutdown_event.set()  # 触发退出事件

    # 清空队列（丢弃所有待处理任务）
    while not q.empty():
        try:
            q.get_nowait()
        except Empty:
            break

    # 注入退出哨兵
    try:
        q.put_nowait("quit")
    except:
        pass  # 如果队列满（理论上不会，刚清空），忽略

    log.warning('退出哨兵已注入，消费者将尽快退出。')


q = Queue(maxsize=50)
# sqlserver_conn: database.MssqlDatabase = database.DatabaseFactory.create_database('sqlserver', setting.MS_CONF)
oracle_conn: database.OracleDatabase = database.DatabaseFactory.create_database('oracle', setting.ORA_CONF)
todicom = photo2dicom.Photo2Dicom(oracle_conn, setting)


if __name__ == '__main__':
    import signal
    import sys

    # 跨平台注册信号
    if sys.platform == "win32":
        signal.signal(signal.SIGINT, signal_handler)
        try:
            signal.signal(signal.SIGTERM, signal_handler)
        except OSError:
            pass
    else:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGHUP, signal_handler)

    log.info('程序正在启动...')
    sleep(1)

    # 启动线程
    prod_thread = threading.Thread(target=producer, daemon=True)
    cons_thread = threading.Thread(target=consumer, daemon=False)

    prod_thread.start()
    cons_thread.start()

    log.info('任务监听已启动...')

    # 主线程：等待退出信号（通过 shutdown_event）
    try:
        while not shutdown_event.is_set():
            cons_thread.join(timeout=2)
    except KeyboardInterrupt:
        shutdown_event.set()

    cons_thread.join(timeout=3)

    log.warning('程序正在退出。。。')
    sleep(2)


    # 关闭资源
    try:
        oracle_conn.close_connection()
    except Exception as e:
        log.error(f"关闭数据库失败: {e}")

    log.warning('程序已退出。')
    sys.exit()
