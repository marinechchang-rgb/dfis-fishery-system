# DFIS Streamlit Community Cloud 部署說明

## 1. GitHub

部署來源為：

- Repository：`marinechchang-rgb/dfis-fishery-system`
- 主程式：`app.py`
- Python 依賴：`requirements.txt`

建議先將版本分支部署為測試 App，確認後再合併到 `main` 作為正式 App。

## 2. 建立 Streamlit App

1. 登入 [Streamlit Community Cloud](https://share.streamlit.io/)。
2. 選擇 **Create app**。
3. 選取 GitHub repository `marinechchang-rgb/dfis-fishery-system`。
4. Branch 選擇欲部署的版本分支或 `main`。
5. Main file path 填入 `app.py`。
6. 建立 App 前開啟 Advanced settings，貼上下一節的 Secrets。

## 3. Secrets

在 App settings → Secrets 設定：

```toml
GEMINI_API_KEY = "你的 Gemini API Key"
OPENAI_API_KEY = "你的 OpenAI API Key"
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DATABASE"
```

至少設定一個 AI 服務金鑰。若兩者皆設定，使用者可在側欄切換。`DATABASE_URL` 強烈建議使用 Supabase 或其他受管 PostgreSQL；若未設定，資料會寫入 Community Cloud 執行個體的 SQLite，重新部署或休眠後可能遺失。

請勿把金鑰寫進 GitHub、`README.md` 或 `.streamlit/secrets.toml.example`。

## 4. 部署後驗證

1. 首頁可正常開啟，側欄沒有 Python 例外。
2. 「系統金鑰與模型設定」可在 Gemini／OpenAI 間切換。
3. 分別以一張測試影像執行兩種 AI 解析。
4. 人工覆核後入庫，再重新整理確認資料仍存在。
5. 測試魚種、船隻、港口參數頁與 CSV 匯出。
6. 到 App logs 確認沒有把 API Key 或資料庫密碼印出。

## 5. 更新與回滾

- Streamlit Community Cloud 會在 GitHub 分支更新後重新部署。
- 正式版應使用受保護的 `main`，以 Pull Request 合併。
- 發版前建立 Git tag；若部署失敗，可將部署分支回到上一個通過驗證的 commit。
