"""
补传单个患者数据使用
"""

import os
import re
from datetime import datetime
from time import sleep
from queue import Queue
import database
import photo2dicom
import setting
from log_config import log


def producer():
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    while True:
        binding_id = input("请输入binding_id(退出程序输入 q )：")
        if binding_id == 'q':
            break
        task_sql = f"SELECT bindingID, exam_no, patientName,patientAge,sex,time,modify_flag,studyUid FROM EXAM.GNK_EQUIP_BIND_PATIENT WHERE bindingID = '{binding_id}'"
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

        pat_info_tup = q.get(block=True)
        studyUid, modify_flag = (pat_info_tup[8], pat_info_tup[6])

        if (modify_flag != '1' and studyUid is None) or (modify_flag == '1' and studyUid is not None):

            try:
                dir_path = pat_info_tup[-2]
                photo_list = pat_info_tup[-1]
                todicom.to_dicom(pat_info_tup, dir_path, photo_list)
                q.task_done()

            except Exception as e:
                q.task_done()



q = Queue(maxsize=50)
# sqlserver_conn: database.MssqlDatabase = database.DatabaseFactory.create_database('sqlserver', setting.MS_CONF)
oracle_conn: database.OracleDatabase = database.DatabaseFactory.create_database('oracle', setting.ORA_CONF)
todicom = photo2dicom.Photo2Dicom(oracle_conn, setting)

if __name__ == '__main__':
    log.info('程序正在启动...')
    sleep(1)

    producer()

    # 关闭资源
    try:
        oracle_conn.close_connection()
    except Exception as e:
        log.error(f"关闭数据库失败: {e}")

    log.warning('程序正在退出。。。')
    sleep(2)
    log.warning('程序已退出。。。')
