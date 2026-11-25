# 深度登记 字幕交付校对册

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 字幕文件采信 | 核对逐行隔离与重复字幕 | `/sheet/source` `/api/check/source` | `app/modules/source/service.py` | `tests/test_source.py` |
| M2 帧率与丢帧约束 | 复查非法标签与精确换算 | `/sheet/clock` `/api/check/clock` | `app/modules/clock/timecode.py` | `tests/test_clock.py` |
| M3 切版段映射 | 按切版重建目标帧 | `/` `/api/check/edits` | `app/modules/edits/contract.py` `app/modules/edits/mapping.py` | `tests/test_edits.py` |
| M4 字幕冲突定位 | 定位同轨重叠帧与原行组 | `/sheet/overlaps` `/api/check/overlaps` | `app/modules/overlaps/service.py` | `tests/test_overlaps.py` |
| M5 时长与丢段对账 | 查看并集覆盖守恒 | `/sheet/balance` `/api/check/balance` | `app/modules/balance/service.py` | `tests/test_balance.py` |
| M6 批次留档复跑 | 保存原件并逐值复算 | `/sheet/runs` `POST /api/runs` | `app/modules/runs/files.py` `app/modules/runs/service.py` | `tests/test_runs.py` |
| M7 交付证据签发 | 下载经散列核验的交付证据 | `/sheet/delivery` `/api/delivery/<key>/export` | `app/modules/delivery/checks.py` | `tests/test_delivery.py` |
| M8 撤回许可重签 | 撤回部分源帧并按新许可重签 | `POST /api/runs` `withdrawals` | `app/modules/licensing/service.py` `app/modules/licensing/ledger.py` | `tests/test_licensing.py` `tests/test_revocation.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | 脏字幕首列 BOM | 首列无效 | 去首 BOM | `app/modules/source/reader.py` | `tests/test_source.py::test_bom_and_alias` |
| TRAP-04 | 脏字幕重复表头 | 当成字幕计算 | 单列分段 | `app/modules/source/reader.py` | `tests/test_source.py::test_repeated_header` |
| TRAP-05 | C112 多余列 | 文本错位 | 保留整行隔离 | `app/modules/source/reader.py` | `tests/test_source.py::test_width_and_missing` |
| TRAP-07 | C110 时码 N/A | 当成零帧 | 隔离必填空值 | `app/modules/source/service.py` | `tests/test_source.py::test_width_and_missing` |
| TRAP-09 | 9007199254740993 | 浏览器数值吞位 | 字符串保形 | `app/modules/source/service.py` | `tests/test_source.py::test_string_identity` |
| TRAP-10 | C104 使用分数帧率 | 假设 30 或先舍入 | 保留端点有理数至最后 | `app/modules/clock/timecode.py` | `tests/test_clock.py::test_exact_rate` |
| TRAP-14 | C111 内容相撞 | 后稿静默覆盖 | 同号矛盾整组隔离 | `app/modules/source/service.py` | `tests/test_source.py::test_conflicting_revision` |
| TRAP-17 | `legacy_id` 旧表头 | 硬读当前字段失败 | 按列别名迁移 | `app/modules/source/service.py` | `tests/test_source.py::test_bom_and_alias` |
| TRAP-23 | C115 与 C116 首尾相接 | 共同边界算重叠 | 半开区间扫线 | `app/modules/overlaps/sweep.py` | `tests/test_overlaps.py::test_touch_is_not_overlap` |
| TRAP-24 | 撤回只覆盖一句的部分源帧 | 整句删掉留下缺词，或复用旧包播到禁播帧 | 仅裁命中源帧并重签，旧包按台账拦下载 | `app/modules/edits/mapping.py` `app/modules/delivery/checks.py` | `tests/test_licensing.py::test_withdraw_parts_of_a_sentence_keeps_the_rest` |
| TRAP-25 | 禁播段只与另一句撞帧 | 直接从交付扣减，破坏守恒 | 撞帧消除但获准帧仍计交付，仅无他句覆盖才入撤回 | `app/modules/balance/service.py` | `tests/test_licensing.py::test_banned_frames_still_counted_when_another_cue_covers` |
| TRAP-26 | 撤回只落在已剪掉画面 | 仍然拒发旧包 | 按 KEEP 片段交集判定，旧包照常下载 | `app/modules/delivery/checks.py` | `tests/test_revocation.py::test_banned_frames_only_on_cut_footage_keep_old_package` |
| TRAP-27 | 重签失败后重试同次撤回 | 重复签发或旧包仍可下载 | 先落台账再签，按内容去重 | `app/modules/licensing/ledger.py` `app/modules/runs/service.py` | `tests/test_revocation.py::test_retry_after_failed_signing_is_idempotent` |

## 守恒与范围

脏样例 1140 源帧 = 740 交付 + 200 移除 + 200 待证。65 个重叠目标帧独立记录，5 条隔离记录无法量化。原件为带格式列的供应商抽取 CSV，DF 参数固定为 29.97，目标固定 24 fps。

撤回一个只与他句撞帧的整句（如 C113 的 35 源帧）不改动交付覆盖与守恒，只从撞帧扫描中移除该句；撤回 10 个无他句覆盖的交付源帧（如 C104）则交付降为 730、许可撤回 10，总账仍为 1140。撤回分桶与交付并集互斥，任何源帧都不会被重复计入。
