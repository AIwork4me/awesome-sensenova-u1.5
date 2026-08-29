# Changelog

## Unreleased

- 新增双语画廊与结论表渲染脚本 scripts/render_gallery.py（发布收口）。
- 文档口径收紧（第二轮 hardening）：primary 定名 **original-prompt result**（15/30；显式披露 best-of-2 确定性种子协议与 GPT 侧参考图采样预算未知），17/30 定名 **prompt-adapted best observed**（含 task-relaxing 排版策略，衡量实践可用性而非同任务能力）；改写策略库标注 requirement_preserving 分类；新增 `results/judge/JUDGE-RUN-MANIFEST.json`（历史判官运行溯源：GLM-5.3-Flash agent backend、判官提示词 sha256、自洽 1.40 = 盲样复评最大五维均值差、复评存档仅 round-1 队列 9/90）；`build_judge_tasks.py --isolated` 将 manifest 移出判官可见目录（future source-isolated workspace，`collect_verdicts.py` 兼容回退），`run_judge_api.py` 启动打印 judge model 并在与发布判官不同时告警。原始 JSON/verdict/台账/图片/分数未做任何改动。
- 文档口径收紧（第一轮）：结果两级表述；`双盲` 统一改称 source-blind；GPT-Image-2 参考统一表述为 frozen/curated community reference outputs；失败根因表述降级为"已测策略范围内主要聚集"。

## 0.1.0 (2026-08-27)

- 项目立项；设计 spec 与实施计划入库。
