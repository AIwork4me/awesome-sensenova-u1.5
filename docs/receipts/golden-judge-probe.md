# 判官金标准回归夹具

用途：每当 `scripts/judge-prompt.md`、schemas.py 评分逻辑或判官后端发生变更后，手工重跑一次双评审并以区间校验。

固定输入（两份都来自本机现存文件）：
- A 案：提示词=基础仓库 examples/posters-2026-08.jsonl 中含 KUNG FU 的行；图像=基础仓库 docs/results/gallery/posters/kungfu-girls.webp
- B 案：提示词=上游 data/cases.json 中 id=511 的 prompt；图像=third_party/ref/data/images/case511.jpg

流程：将 A/B 以中性编号交给判官（按 Task 12 操作手册派发一个子代理），收集两份 verdict。

验收区间（来自 2026-08-27 探针实测，verdict 凭据在本仓库 docs/receipts/judge-probe-verdict.json）：
- 五维均分：A ∈ [6.5, 8.5]，B ∈ [8.5, 10]
- A 的 hard_flags.small_text_quality 必须为 garbled
- B 的 hard_flags.display_text_correct 必须为 true 且 transcribed_text 包含坐标串 33.9249° S, 18.4241° E

区间外即判定回归失败：先查判官输出是否违规（身份推断/schema 缺陷），再查量规改动是否引入偏差；两者都不是则升级为议题讨论。
