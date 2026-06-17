---
name: ai-anomaly-monitor
description: |
  AI 异常监控与归因系统。接入数据即可自动监控指标异常、多维下钻归因、
  生成 AI 分析报告。适用于数据分析师日常监控核心业务指标。
triggers:
  - "异常监控"
  - "异常检测"
  - "归因分析"
  - "指标监控"
  - "数据波动"
  - "异动分析"
  - "anomaly"
  - "数据上传"
  - "导入数据"
---

# AI 异常监控与归因系统

接入数据 → 自动监控 → 多维归因 → AI 生成报告。

## 启动服务

```bash
cd ai-anomaly-monitor
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

启动后访问 http://localhost:8000/docs 使用 Swagger API。

## 核心能力

1. **上传数据** — `POST /api/datasource/auto-import` 上传 CSV/Excel，自动识别日期列、指标列、维度列，注册指标并立刻运行监控
2. **触发监控** — `POST /api/monitor/run` 对全量指标执行异常检测
3. **查看异常** — `GET /api/anomalies` 筛选和分页查询异常事件
4. **归因报告** — `GET /api/reports/{metric_id}` 获取完整归因分析（维度下钻 + AI 摘要）
5. **知识库** — `GET /api/knowledge/search?q=xxx` 检索历史相似案例

## 配置 LLM

编辑 `config/llm_config.yaml`：

```yaml
deepseek:
  api_key: "${DEEPSEEK_API_KEY}"  # 设环境变量或直接填 key
active_provider: "deepseek"
```

支持 Claude / OpenAI / DeepSeek / 国产模型。

## 测试

```bash
python -m pytest tests/ -v
```

## 项目结构

```
src/
├── data_source/     # 数据接入（CSV/数据库/API）
├── metrics/         # 指标口径管理
├── detection/       # 异常检测（同比/Z-score/日历修正）
├── attribution/     # 归因下钻（贡献度计算/多层下钻）
├── llm/             # LLM 适配层
├── agents/          # Agent 编排（监控→归因→报告）
├── knowledge/       # 知识库 RAG
├── api/             # FastAPI 接口
├── notification/    # 消息推送
└── scheduler/       # 定时调度
```
