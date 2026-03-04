from typing import Any
import requests
from io import BytesIO
from xpinyin import Pinyin
from datetime import datetime, timedelta
from log_config import log
import setting


def upload_dicom(url: str, dicom_byt: BytesIO) -> bool | None | Any:
    try:
        res = requests.post(url=url, data=dicom_byt, auth=(str(setting.User), str(setting.Password)))

        if res.status_code == 200:
            ID = res.json().get('ID')
            log.info(f'上传成功,Instance: {ID}')
            return ID
    except Exception as e:
        log.error(f'图像上传失败，5秒后重试！')
        return False


def delete_dicom(url: str, instance_id: str) -> int:
    try:
        url = url + '/' + instance_id
        respones = requests.delete(url=url, auth=(str(setting.User), str(setting.Password)))
        status_code = respones.status_code
        return status_code
    except Exception as e:
        log.error(e)



def get_pinyin(name: str) -> str:
    p = Pinyin()
    pat_name = p.get_pinyin(name).upper().replace('-', ' ')
    return pat_name


def get_first_day() -> str:
    # 获取当前日期
    today = datetime.today()
    # 获取上个月的第一天
    first_day_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    # 格式化为字符串
    return first_day_of_last_month.strftime('%Y-%m-%d')
