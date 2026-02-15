# OptionsFlow 快速开始

## 项目概述

OptionsFlow 是期权策略分析平台，支持 Web 界面与 AI 助手，采用前后端分离架构。

## 技术栈

- **后端**: FastAPI, SQLite, JWT, yfinance, 多数据源
- **前端**: React 18, TypeScript, Tailwind, Recharts, Plotly.js, react-markdown

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend && npm install
```

### 2. 启动

**Windows**: `.\start.ps1` 或双击 `run.bat`  
**Linux/macOS**: `./start.sh`

**手动启动**:
```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

### 3. 访问

- 前端: http://localhost:5173
- API 文档: http://localhost:8000/docs

## 功能模块

- **用户认证**: 注册/登录，JWT 认证
- **期权链**: 股票信息、期权链、到期日
- **策略分析**: CCS/PCS/CSP/CC，多策略对比，P&L 情景，推荐策略
- **Greeks 可视化**: 3D 热力图
- **历史记录**: 分析保存与查询
- **AI 助手**: 支持 OpenAI/GLM/Ollama/vLLM，在设置中配置后即可使用

## API 端点

### 认证
- `POST /api/v1/auth/register` `POST /api/v1/auth/login` `POST /api/v1/auth/refresh`

### 期权
- `GET /api/v1/options/stock/{symbol}` `GET /api/v1/options/expirations/{symbol}` `GET /api/v1/options/chain/{symbol}`

### 策略
- `POST /api/v1/strategies/analyze` `POST /api/v1/strategies/compare` `POST /api/v1/strategies/find-best` `POST /api/v1/strategies/pnl-scenarios`

### Agent
- `GET/PUT /api/v1/agent/config` `POST /api/v1/agent/chat` (SSE 流式)

## 开发注意事项

1. 数据库 `optionsflow.db` 会自动创建
2. 数据源支持 Yahoo Finance、MarketData.app、Alpha Vantage、AKShare
3. 生产部署请修改 `backend/config.py` 中的 `SECRET_KEY`

## 许可证

MIT License
