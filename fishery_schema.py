from pydantic import BaseModel, Field
from typing import Optional, List

class CatchDetail(BaseModel):
    species_raw_name: str = Field(description="報表中記錄的原始魚種名稱，例如：什 臭肚、如志。")
    species_standard_name: str = Field(description="對齊臺灣魚類資料庫後的標準化中文名，例如：臭肚魚、加志。")
    weight_kg: Optional[float] = Field(description="漁獲重量(公斤)，若無此資料請務必填 null。")
    count_individual: Optional[int] = Field(description="尾數/隻數，若無此資料請務必填 null。")
    catch_properties: dict = Field(description="動態儲存特定生物量測指標的字典（如叉長、總重等）。若無額外指標，請務必填入空字典 {}。")

class FisheryLogSchema(BaseModel):
    database_type: str = Field(description="資料庫分類類型。必須為以下之一：'生物學參數資料庫'、'拖網類漁業報表資料庫'、'刺網類漁業報表資料庫'、'釣具類漁業報表資料庫'。如果是其他新型態，請填入最合適的分類。")
    vessel_name: str = Field(description="船名，例如：聖漁豐、小綿洋。")
    log_date: str = Field(description="作業日期，統一標準化格式為 YYYY-MM-DD。")
    gear_type: str = Field(description="漁法/調查類型，例如：拖網、釣具、生物學紀錄。")
    gear_properties: dict = Field(description="動態儲存漁法參數的字典。若無額外參數，請務必填入空字典 {}。")
    catch_records: List[CatchDetail] = Field(description="該次作業提取出的所有漁獲或單尾生物詳細紀錄列表。")

class FisheryLogBatchSchema(BaseModel):
    logs: List[FisheryLogSchema] = Field(description="從上傳的文件或圖片中提取出的所有航次與每日作業紀錄列表。")
