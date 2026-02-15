# OptionsFlow

期权策略分析平台 - 集成 MCP 协议、Web 应用与 AI Agent，支持期权链、策略分析、Greeks 可视化及 LLM 对话分析。

## 功能概览

### Web 平台
- **期权链** - 查看股票期权链、到期日、Greeks
- **策略分析** - CCS/PCS/CSP/CC 策略分析、多策略对比、P&L 情景、推荐策略
- **Greeks 可视化** - 3D 希腊字母热力图
- **历史记录** - 分析记录保存与查询
- **AI 助手** - 支持 OpenAI、智谱 GLM、Ollama、vLLM，将期权分析作为 Agent 工具

### MCP 服务器
可作为 Claude Desktop 等 MCP 客户端的服务端，提供 `get_stock_info`、`get_option_chain`、`analyze_strategy` 等工具。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI, SQLite, JWT, yfinance, Black-Scholes |
| 前端 | React 18, TypeScript, Tailwind CSS, Zustand, Recharts, Plotly.js, react-markdown |
| 数据源 | Yahoo Finance（主）, MarketData.app, Alpha Vantage, AKShare（中国 ETF） |
| Agent | OpenAI 兼容 API（OpenAI/GLM/Ollama/vLLM） |

## 项目结构

```
mcp-optionsflow/
├── backend/                 # 后端 FastAPI
│   ├── main.py             # 入口
│   ├── config.py           # 配置
│   ├── database.py         # 数据库模型
│   ├── models/             # Pydantic 模型
│   ├── routers/            # API 路由（auth, options, strategies, agent）
│   ├── services/           # 业务逻辑
│   └── utils/              # 工具
├── frontend/               # React 前端
│   ├── src/
│   │   ├── components/     # 共享组件（strategy, agent, layout）
│   │   ├── pages/          # 页面
│   │   ├── services/       # API
│   │   ├── store/          # 状态
│   │   ├── locales/        # i18n（en/zh）
│   │   └── types/
│   └── package.json
├── providers/              # 多数据源（Yahoo, MarketData, AlphaVantage, AKShare）
├── optionsflow.py          # MCP 核心逻辑（可独立作为 MCP 服务）
├── requirements.txt
├── start.ps1               # PowerShell 启动
├── start.sh                # bash 启动
├── run.bat                 # Windows 批处理启动
└── QUICKSTART.md           # 快速开始
```

## 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd frontend && npm install
```

### 2. 启动

**Windows**
```powershell
.\start.ps1
# 或双击 run.bat
```

**Linux/macOS**
```bash
./start.sh
```

**手动启动**
```bash
# 后端
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 前端（另开终端）
cd frontend && npm run dev
```

### 3. 访问

- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 4. 使用 AI 助手

1. 注册/登录
2. 进入 **设置** 配置 LLM（OpenAI API Key、Ollama 地址等）
3. 进入 **AI 助手** 提问，如「分析 AAPL 的 PCS 策略」

## MCP 独立使用

将 `optionsflow.py` 作为 MCP 服务接入 Claude Desktop：

```json
{
  "mcpServers": {
    "optionsflow": {
      "command": "python",
      "args": ["path/to/optionsflow.py"]
    }
  }
}
```

## 环境变量（可选）

```bash
ALPHA_VANTAGE_API_KEY=xxx    # Alpha Vantage
MARKET_DATA_API_KEY=xxx      # MarketData.app
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)
