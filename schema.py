from pydantic import BaseModel, Field
from typing import Optional, List

class CatchDetail(BaseModel):
    species_raw_name: str = Field(description="報表中記錄的原始魚種名稱，例如：什 臭肚、如志")
    species_standard_name: str = Field(description="對齊臺灣魚類資料庫後的標準化中文名，例如：臭肚魚、加志")
    weight_kg: Optional[float] = Field(description="漁獲重量(公斤)，若無此資料請務必填 null。若原始單位為公克，請自動換算為公斤")
    count_individual: Optional[int] = Field(description="尾數/隻數，若無此資料請務必填 null")
    catch_properties: dict = Field(description="動態儲存特定生物量測指標的字典。若無額外指標，請務必填入空字典 {}。例如：{'fork_length_mm': 121.64}")

class FisheryLogSchema(BaseModel):
    vessel_name: str = Field(description="船名，例如：聖漁豐、小綿洋")
    log_date: str = Field(description="作業日期，統一標準化格式為 YYYY-MM-DD")
    gear_type: str = Field(description="漁法/調查類型，例如：拖網、釣具、生物學紀錄")
    gear_properties: dict = Field(description="動態儲存漁法參數的字典。若無額外參數，請務必填入空字典 {}。如拖網：{'mesh_size_inch': 2.0}")
    catch_records: List[CatchDetail] = Field(description="該次作業提取出的所有漁獲或單尾生物詳細紀錄列表")
