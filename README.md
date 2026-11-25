# 字幕交付校对册

字幕编辑核对公映版切段、供应商字幕与 24 fps 目标。网格按原行、入出帧与原因定位交付风险。

## 启动与演示

`docker compose up --build` 后打开 `http://localhost:18465`。本机安装 `requirements.txt` 后可运行 `flask --app app.main run -p 18465`。用 `pytest -q` 执行测试。归档目录默认 `var/cuts`，由 `CAPTION_ARCHIVE` 配置。

- 首页检查 C101 跨三段，C103 在 B-01 与 B-02 间留下 200 源帧缺证。网格支持方向键和鼠标选格。
- 帧率校核查 C105 的非法丢帧号。冲突定位查三条字幕同占 28 个目标帧，覆盖账中重叠另外记录。
- 文件采信可提交自有 CSV。归档校对后，在版本归档复算，在交付签发下载一份 JSON 证据包。
- 版权方可撤回某句字幕的部分源帧：提交 `withdrawals` 后只为未受限画面重签新包，旧包在禁播帧未剪掉时停止下载。

## API

`POST /api/runs` 接受 `{"sample":"dirty"}`、`{"sample":"clean"}` 或含 `cues` 与 `cuts` CSV 文本的 JSON。追加 `withdrawals`（JSON 数组或 `cue_id,track,start,end` CSV）可提交撤回并重签。`GET /api/check/<sheet>` 查 `source`、`clock`、`edits`、`overlaps`、`balance`，用 `run` 查询归档或用 `sample` 预览。归档详情 `GET /api/runs/<id>`，复算 `POST /api/runs/<id>/repeat`，下载 `GET /api/delivery/<id>/export`（含禁播帧的旧包返回 409 `WITHDRAWN`）。

[数据定义](docs/DATA-DICTIONARY.md) · [深度登记](docs/DEPTH.md) · [复算例](docs/FRAME-EXAMPLE.md)

前五张业务页也可用 `POST /api/check/<sheet>` 直接提交样例或原件，只试跑到选中的校对阶段。
