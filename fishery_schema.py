from typing import List, Optional

from pydantic import BaseModel, Field


class OperationLocation(BaseModel):
    location_role: str = Field(description="位置角色，例如 set_point、haul_point、spot_1、spot_2。")
    sequence_no: Optional[int] = Field(default=None, description="位置順序。")
    location_name: Optional[str] = Field(default=None, description="地點名稱。")
    latitude: Optional[float] = Field(default=None, description="緯度。")
    longitude: Optional[float] = Field(default=None, description="經度。")
    depth_m: Optional[float] = Field(default=None, description="水深(公尺)。")
    extra_properties: dict = Field(default_factory=dict, description="其他位置補充欄位。")


class CatchDetail(BaseModel):
    species_raw_name: str = Field(description="表單原始魚種名稱。")
    species_standard_name: str = Field(description="標準化後魚種名稱。")
    weight_kg: Optional[float] = Field(default=None, description="重量(公斤)。")
    count_individual: Optional[int] = Field(default=None, description="尾數。")
    size_bucket: Optional[str] = Field(default=None, description="尺寸分級，例如大、中、小。")
    remarks: Optional[str] = Field(default=None, description="明細備註。")
    catch_properties: dict = Field(default_factory=dict, description="其他漁獲明細動態欄位。")


class FisheryLogSchema(BaseModel):
    database_type: str = Field(description="使用者在 UI 選擇的資料庫類型名稱。")
    form_template_code: Optional[str] = Field(default=None, description="表單母版代碼。")
    vessel_name: str = Field(description="船名。")
    vessel_registration_no: Optional[str] = Field(default=None, description="船編或船籍編號。")
    owner_name: Optional[str] = Field(default=None, description="船主。")
    observer_name: Optional[str] = Field(default=None, description="填表人、調查人或觀測員。")
    log_date: str = Field(description="作業日期，格式 YYYY-MM-DD。")
    departure_time: Optional[str] = Field(default=None, description="出港時間。")
    return_time: Optional[str] = Field(default=None, description="進港時間。")
    start_time: Optional[str] = Field(default=None, description="作業開始時間。")
    end_time: Optional[str] = Field(default=None, description="作業結束時間。")
    gear_type: str = Field(description="漁法或漁具類型。")
    remarks: Optional[str] = Field(default=None, description="作業主檔備註。")
    gear_properties: dict = Field(default_factory=dict, description="漁具與作業背景動態欄位。")
    operation_locations: List[OperationLocation] = Field(default_factory=list, description="作業位置資訊。")
    catch_records: List[CatchDetail] = Field(description="漁獲明細。")


class FisheryLogBatchSchema(BaseModel):
    logs: List[FisheryLogSchema] = Field(description="一次解析出的多筆漁撈作業日誌。")


class BiologicalParameterRecord(BaseModel):
    form_template_code: Optional[str] = Field(default=None, description="表單母版代碼。")
    collection_date: str = Field(description="採樣日期，格式 YYYY-MM-DD。")
    collection_id: str = Field(description="採樣批次或樣本編號。")
    port: str = Field(description="港口或地點。")
    vessel_name: str = Field(description="船名。")
    form_code: str = Field(description="原始表單代碼。")
    species_name: str = Field(description="原始魚種名稱。")
    species_standard_name: Optional[str] = Field(default=None, description="標準化魚種名稱。")
    sequence_no: Optional[int] = Field(default=None, description="個體順序編號。")
    specimen_no: Optional[str] = Field(default=None, description="樣本編號。")
    net_group: Optional[str] = Field(default=None, description="內網、外網等分組。")
    net_set_no: Optional[str] = Field(default=None, description="第幾網。")
    site_name: Optional[str] = Field(default=None, description="作業地點名稱。")
    fork_length_mm: Optional[float] = Field(default=None, description="尾叉長(mm)。")
    total_length_mm: Optional[float] = Field(default=None, description="全長(mm)。")
    weight_g: Optional[float] = Field(default=None, description="重量(g)。")
    sex: Optional[str] = Field(default=None, description="性別。")
    maturity: Optional[str] = Field(default=None, description="成熟度。")
    gsi: Optional[float] = Field(default=None, description="生殖腺指數。")
    total_weight_kg: Optional[float] = Field(default=None, description="該批次總重量。")
    discard_weight_kg: Optional[float] = Field(default=None, description="該批次拋棄重量。")
    remarks: Optional[str] = Field(default=None, description="備註。")
    background_properties: dict = Field(default_factory=dict, description="其他背景補充欄位。")


class BiologicalParameterBatch(BaseModel):
    records: List[BiologicalParameterRecord] = Field(description="一次解析出的生物學量測紀錄。")
