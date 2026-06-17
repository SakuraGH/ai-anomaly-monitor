# AI 异常监控与归因系统

接入数据即可自动监控指标异常、多维下钻归因、生成 AI 分析报告。

## 核心能力

| 能力 | 说明 |
|------|------|
| 自动发现异常 | 同比/环比/Z-score/移动平均 多方法联合检测 |
| 多维下钻归因 | 从总量逐层下钻到具体维度值，计算贡献占比 |
| AI 生成报告 | 基于结构化证据生成摘要、假设和排查建议 |
| 知识库检索 | 存储历史案例，检索相似异常供参考 |

## 四层架构

```
数据接入层  →  指标口径层  →  异常检测层  →  归因下钻层  →  AI 总结层
(CSV/DB/API)   (统一口径)     (同比/Z-score)  (贡献度计算)   (LLM 报告)
```

## 使用流程

### 1. 配置 LLM（可选）

编辑 `config/llm_config.yaml`，设置 API key 和模型。不配置也能用，系统会降级为规则摘要。

```yaml
# 示例：使用 DeepSeek
deepseek:
  api_key: "${DEEPSEEK_API_KEY}"   # 设置环境变量，或直接填 key
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"

active_provider: "deepseek"        # 选择 provider
```

支持 Claude / OpenAI / DeepSeek / 通义千问等兼容 OpenAI 接口的模型。

### 2. 注册指标

编辑 `config/metrics_registry.yaml`，定义你要监控的指标：

```yaml
metrics:
  - metric_id: "my_metric"
    metric_name: "日销售额"
    formula: "SUM(sales_amount) WHERE date=today"
    data_source:
      type: "csv"
      path: "data/my_data.csv"
      date_column: "date"
      value_column: "sales"
    dimensions:
      - name: "channel"
        label: "渠道"
      - name: "region"
        label: "地域"
    priority: "P0"
```

也可以通过 API 在线管理：`POST /api/metrics`

### 3. 接入数据

三种方式：

| 方式 | 适用场景 |
|------|----------|
| CSV/Excel 上传 | 快速试用、一次性分析 |
| 数据库连接 | 生产持续监控 |
| HTTP API | 对接已有数据服务 |

**上传文件一键导入：**

```bash
curl -X POST http://localhost:8000/api/datasource/auto-import \
  -F "file=@你的数据.xlsx" \
  -F "metric_name=销售额"
```

系统会自动识别日期列、数值列、维度列，注册指标，并立即触发监控。

### 4. 触发监控

```bash
# 全量检测
curl -X POST http://localhost:8000/api/monitor/run

# 单指标检测
curl -X POST "http://localhost:8000/api/monitor/run/my_metric?target_date=2026-06-12"
```

系统默认每天 09:00 自动运行（可在 `config/settings.yaml` 修改）。

### 5. 查看结果

```bash
# 异常事件列表（支持分页和筛选）
curl "http://localhost:8000/api/anomalies?severity=high&page=1"

# 完整归因报告（含 AI 摘要 + 多层下钻）
curl "http://localhost:8000/api/reports/my_metric"

# 搜索历史相似案例
curl "http://localhost:8000/api/knowledge/search?q=销售额下降"
```

分析报告会自动保存到 `reports/` 目录。

## API 速查

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/datasource/auto-import` | POST | 上传文件 → 注册指标 → 跑监控（一键） |
| `/api/datasource/upload` | POST | 上传数据文件 |
| `/api/metrics` | GET/POST | 指标管理 |
| `/api/monitor/run` | POST | 全量触发监控 |
| `/api/monitor/run/{id}` | POST | 单指标触发 |
| `/api/anomalies` | GET | 异常事件列表 |
| `/api/reports` | GET | 报告列表 |
| `/api/reports/{id}` | GET | 查看完整归因报告 |
| `/api/knowledge/search` | GET | 搜索历史案例 |

## 目录结构

```
ai-anomaly-monitor/
├── config/
│   ├── settings.yaml              # 全局配置
│   ├── llm_config.yaml            # LLM 配置
│   └── metrics_registry.yaml      # 指标注册表
├── data/
│   ├── sample_metrics.csv         # 示例数据
│   ├── activity_calendar.csv      # 活动日历
│   └── uploads/                   # 上传文件
├── reports/                       # 自动生成的 Markdown 报告
├── src/
│   ├── data_source/               # 数据接入（CSV/DB/API）
│   ├── metrics/                   # 指标口径管理
│   ├── detection/                 # 异常检测
│   ├── attribution/               # 归因下钻
│   ├── llm/                       # LLM 适配层
│   ├── agents/                    # Agent 编排
│   ├── knowledge/                 # 知识库 RAG
│   ├── scheduler/                 # 定时调度
│   ├── api/                       # FastAPI 接口
│   └── models/                    # 数据模型
└── tests/
```

## 示例

完整示例见 `reports/零售数据异常分析完整示例.md`，展示了对 4 万行零售数据的完整分析流程：

- 上传 → 自动注册 → 异常检测 → 五层下钻 → 定位到单门店单 SKU → AI 生成排查建议

## 运行测试

```bash
python -m pytest tests/ -v
```

## 设计原则

- **辅助分析，不是自动决策** — AI 输出是初步判断，最终结论需分析师审核
- **证据驱动** — LLM 只处理结构化证据的摘要组织，不做原始数据的猜测
- **区分事实与假设** — 报告明确标注「已验证的事实」「可能的原因」「排查建议」「需补充的数据」

## 技术栈

Python / FastAPI / pandas + scipy / ChromaDB / APScheduler / 可插拔 LLM
