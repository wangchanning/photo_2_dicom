import os
import pydicom
import numpy as np
from datetime import datetime
from PIL import Image
from io import BytesIO
import tools
from time import sleep
from log_config import log


class Photo2Dicom:
    def __init__(self, db_connection, setting):
        self.db_connection = db_connection
        self.setting = setting

    def to_dicom(self, pat_info_tup, dir_path, photo_list):
        bind_id, exam_no, pat_name, pat_age, pat_sex, time, modify_flag, pat_loc_id, studyuid, birth, _, _ = pat_info_tup

        try:
            exam_time = datetime.strftime(time, '%Y%m%d')
            pat_name = tools.get_pinyin(pat_name)
        except Exception as e:
            log.error(e)
            return None

        if modify_flag == '1':
            study_uid = studyuid
        else:
            study_uid = pydicom.uid.generate_uid()  # 生成唯一的study_uid
        series_uid = pydicom.uid.generate_uid()  # 生成唯一的series_uid

        pat_sex = 'M' if pat_sex == '男' else 'F'

        data_dict = {"bind_id": bind_id,
                     "exam_no": exam_no,
                     "pat_name": pat_name,
                     "pat_age": pat_age,
                     "pat_loc_id": pat_loc_id,
                     "pat_sex": pat_sex,
                     "exam_time": exam_time,
                     "modify_flag": modify_flag,
                     "study_uid": study_uid,
                     "series_uid": series_uid,
                     "birth": birth,
                     'dir_path': dir_path,
                     'photo_list': photo_list
                     }

        self.process_photos(data_dict)

    def process_photos(self, data_dict: dict):
        bind_id = data_dict["bind_id"]
        modify_flag = data_dict["modify_flag"]
        photo_list = data_dict['photo_list']
        dir_path = data_dict['dir_path']
        number_of_photo = len(photo_list)

        if modify_flag == '1':
            for seq in range(number_of_photo):
                if bind_id in photo_list[seq]:
                    photo = str(os.path.join(dir_path, photo_list[seq]))
                    self.handle_modified_photo(photo, seq, data_dict)

        else:
            study_uid = data_dict['study_uid']
            series_uid = data_dict['series_uid']
            for seq in range(number_of_photo):
                photo = str(os.path.join(dir_path, photo_list[seq]))
                if bind_id in photo_list[seq]:
                    self.process_dicom(photo, seq, data_dict, flag=True)
                else:
                    self.process_dicom(photo, seq, data_dict, flag=False)

            sql = f"UPDATE EXAM.GNK_EQUIP_BIND_PATIENT SET studyUid = '{study_uid}', seriesUid = '{series_uid}' WHERE bindingID = '{bind_id}'"
            self.db_connection.execute_update(sql)

    def handle_modified_photo(self, photo: str, seq: int, data_dict: dict):
        bind_id = data_dict["bind_id"]
        instance_sql = f"SELECT instanceUid FROM EXAM.GNK_EQUIP_BIND_PATIENT WHERE bindingID = {bind_id}"
        [(instance_id,)] = self.db_connection.execute_query(instance_sql)
        status_code = tools.delete_dicom(self.setting.URL, instance_id)
        if status_code != 200:
            log.error(f'图像删除失败：{instance_id}，尝试更新数据！')
        else:
            log.info(f'图像删除成功：{instance_id}')
        self.process_dicom(photo, seq, data_dict, flag=True)

    def process_dicom(self, photo: str, seq: int, data_dict: dict, flag: bool):
        
        try:
            bind_id = data_dict['bind_id']
            instance_uid = pydicom.uid.generate_uid()
            ds = self.create_dicom_dataset(photo, data_dict, instance_uid, seq, flag)

            dicom_bytes = BytesIO()
            ds.save_as(dicom_bytes)
            dicom_bytes.seek(0)

            instance_id = tools.upload_dicom(self.setting.URL, dicom_bytes)
            
            while not instance_id:
                sleep(5)
                instance_id = tools.upload_dicom(self.setting.URL, dicom_bytes)
                

            if flag:
                sql = f"UPDATE EXAM.GNK_EQUIP_BIND_PATIENT SET instanceUid = '{instance_id}', modify_flag = NULL WHERE bindingID = '{bind_id}'"
                self.db_connection.execute_update(sql)

        except Exception as e:
            log.error(e)

    def create_dicom_dataset(self, photo, data_dict, instance_uid, seq, flag):
        img = Image.open(photo)
        img = img.convert("RGB")
        np_img = np.array(img)

        ds = pydicom.Dataset()
        ds.file_meta = pydicom.Dataset()
        ds.file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.6.1'
        ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds.file_meta.ImplementationClassUID = '1.2.276.0.7230010.3.0.3.6.6'
        ds.file_meta.ImplementationVersionName = 'OFFIS_DCMTK_366'

        ds.ImageType = ['ORIGINAL', 'PRIMARY', 'AXIAL']
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.6.1'
        ds.SOPInstanceUID = instance_uid
        ds.StudyDate = data_dict["exam_time"]
        ds.AccessionNumber = data_dict["exam_no"]
        ds.Modality = "US"
        ds.PatientName = data_dict["pat_name"]
        ds.PatientID = data_dict["pat_loc_id"]
        ds.PatientBirthDate = data_dict["birth"]
        ds.PatientSex = data_dict["pat_sex"]
        ds.StudyInstanceUID = data_dict["study_uid"]
        ds.SeriesInstanceUID = pydicom.uid.generate_uid() if flag else data_dict["series_uid"]
        ds.StudyID = "1"
        ds.SeriesNumber = "1" if flag else "2"
        ds.InstanceNumber = str(seq + 1)
        ds.SamplesPerPixel = 3
        ds.PhotometricInterpretation = "RGB"
        ds.PlanarConfiguration = 0
        ds.Rows, ds.Columns, _ = np_img.shape
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.PixelData = np_img.tobytes()

        return ds
