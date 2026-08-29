# Changelog

## Unreleased

- 新增双语画廊与结论表渲染脚本 scripts/render_gallery.py（发布收口）。
- 文档口径收紧：结果改为两级表述（primary = R1 原始提示词 15/30；optimization ceiling = 跨轮最优 17/30）；`双盲` 统一改称 source-blind 并在 README/操作手册写明协议实现（中性内容哈希 entry ID、来源元数据不进判官上下文、队列按轮号确定性乱序、泄漏扫描）；GPT-Image-2 参考统一表述为 frozen/curated community reference outputs；失败根因表述降级为"已测策略范围内主要聚集于微缩文字/复杂排版/中文字形"。原始 JSON/verdict/台账/图片未做任何改动。

## 0.1.0 (2026-08-27)

- 项目立项；设计 spec 与实施计划入库。
