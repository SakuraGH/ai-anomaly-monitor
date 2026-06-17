"""数据源管理 API — 支持文件上传与真实连接测试。"""

import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

router = APIRouter(prefix="/api/datasource", tags=["数据源管理"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_store: list[dict] = [
    {"id": "csv-1", "name": "快购示例CSV", "type": "csv",
     "path": "data/sample_metrics.csv", "enabled": True,
     "createdAt": "2026-06-12"},
]


def _find(ds_id: str):
    for d in _store:
        if d["id"] == ds_id:
            return d
    return None


@router.get("")
def list_datasources():
    return {"datasources": _store}


@router.post("")
def add_datasource(data: dict):
    ds_id = data.get("id", f"ds-{uuid.uuid4().hex[:8]}")
    item = {
        "id": ds_id,
        "name": data.get("name", ""),
        "type": data.get("type", "csv"),
        "path": data.get("path", ""),
        "enabled": True,
        "createdAt": data.get("createdAt", ""),
    }
    _store.append(item)
    return item


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(""),
):
    """上传 CSV/Excel 文件作为数据源。"""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(400, "仅支持 .csv / .xlsx / .xls 文件")

    ds_id = f"ds-{uuid.uuid4().hex[:8]}"
    save_path = UPLOAD_DIR / f"{ds_id}{suffix}"
    content = await file.read()
    save_path.write_bytes(content)

    # 自动检测列
    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(save_path)
        else:
            df = pd.read_csv(save_path, encoding="utf-8-sig")
        columns = list(df.columns)
        row_count = len(df)
        preview = df.head(5).to_dict(orient="records")
    except Exception as e:
        columns = []
        row_count = 0
        preview = []
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, f"文件解析失败: {e}")

    item = {
        "id": ds_id,
        "name": name or file.filename,
        "type": "csv",
        "path": str(save_path),
        "enabled": True,
        "columns": columns,
        "rowCount": row_count,
        "preview": preview,
        "createdAt": "",
        "fileSize": len(content),
    }
    _store.append(item)
    return item


@router.post("/{ds_id}/test")
def test_datasource(ds_id: str):
    item = _find(ds_id)
    if not item:
        raise HTTPException(404, "数据源不存在")

    path = item.get("path", "")
    full = Path(path)
    if not full.exists():
        return {"connection": "failed", "error": f"文件不存在: {path}"}

    try:
        suffix = full.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(full)
        else:
            df = pd.read_csv(full, encoding="utf-8-sig")
        return {
            "connection": "ok",
            "columns": list(df.columns),
            "rowCount": len(df),
        }
    except Exception as e:
        return {"connection": "failed", "error": str(e)}


@router.delete("/{ds_id}")
def delete_datasource(ds_id: str):
    item = _find(ds_id)
    if item:
        pass
    global _store
    _store = [d for d in _store if d["id"] != ds_id]
    return {"deleted": True}


# ── 一键导入：上传 + 自动注册指标 + 立即监控 ──────────────

@router.post("/auto-import")
async def auto_import_and_monitor(
    file: UploadFile = File(...),
    metric_name: str = Form(""),
    date_col: str = Form(""),
    value_col: str = Form(""),
    dimension_cols: str = Form(""),  # 逗号分隔
):
    """上传数据文件，自动注册指标并运行监控管道。"""
    from src.api.deps import get_state
    from src.models.metric import MetricDefinition, MetricDimension, AlertThreshold, MetricDataSource

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(400, "仅支持 .csv / .xlsx / .xls 文件")

    ds_id = f"ds-{uuid.uuid4().hex[:8]}"
    save_path = UPLOAD_DIR / f"{ds_id}{suffix}"
    content = await file.read()
    save_path.write_bytes(content)

    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(save_path)
        else:
            df = pd.read_csv(save_path, encoding="utf-8-sig")
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, f"文件解析失败: {e}")

    all_columns = list(df.columns)

    # 自动推断列
    if not date_col:
        for c in all_columns:
            if c.lower() in ("date", "dt", "日期", "时间"):
                date_col = c
                break
        date_col = date_col or all_columns[0]

    if not value_col:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        value_col = numeric_cols[0] if numeric_cols else all_columns[-1]

    dims = [d.strip() for d in dimension_cols.split(",") if d.strip()]
    if not dims:
        dims = [c for c in all_columns if c not in (date_col, value_col, "metric_id")][:5]

    # 1. 添加数据源
    ds_item = {
        "id": ds_id, "name": metric_name or file.filename,
        "type": "csv", "path": str(save_path), "enabled": True,
        "columns": all_columns, "rowCount": len(df),
        "createdAt": "",
    }
    _store.append(ds_item)

    # 2. 自动注册指标
    mid = metric_name.replace(" ", "_") if metric_name else ds_id
    metric = MetricDefinition(
        metric_id=mid,
        metric_name=metric_name or file.filename,
        description=f"从 {file.filename} 自动导入",
        data_source=MetricDataSource(
            type="csv", path=str(save_path),
            date_column=date_col, value_column=value_col,
        ),
        dimensions=[MetricDimension(name=d, label=d) for d in dims],
        priority="P1",
    )
    state = get_state()
    try:
        state.registry.add_metric(metric)
    except ValueError:
        state.registry.update_metric(mid, {
            "data_source": metric.data_source.model_dump(),
            "dimensions": [d.model_dump() for d in metric.dimensions],
        })

    # 3. 立即运行监控
    target_date = df[date_col].iloc[-1] if date_col in df.columns else None
    if hasattr(target_date, "strftime"):
        target_date = target_date.date() if hasattr(target_date, "date") else target_date

    result = state.orchestrator.run_single(mid, target_date)

    # 4. 返回完整结果
    return {
        "datasource": ds_item,
        "metric": metric.model_dump(),
        "auto_detected": {
            "date_column": date_col,
            "value_column": value_col,
            "dimension_columns": dims,
        },
        "pipeline": result.model_dump(),
        "summary": (
            f"上传成功！检测到 {result.anomaly_count} 个异常。"
            if result.anomaly_count > 0
            else "上传成功！当前数据未检测到异常。"
        ),
    }
