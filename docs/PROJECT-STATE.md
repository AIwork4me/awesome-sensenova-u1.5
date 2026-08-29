# 项目状态与交接文档（Project State & Handoff）

- 更新：2026-08-28 · main `37873fa`
- 用途：本文件是项目的完整状态快照与交接包。任何新会话/新任务（例如"写项目总结"）只需读通本文，即可在零上下文下准确引用全部数据、结论与凭据位置。文中每个数字都可在所引路径复核。

## 1. 项目一句话

awesome-sensenova-u1.5：把 [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) 的社区案例作为量化基线，在 AMD gfx1100 + ROCm 7.14.0 上用 SenseNova-U1.5-8B-MoT 同题复现，以 GLM 视觉判官双盲评分，自动迭代提示词三轮，开源提示词库、全部效果图与可溯源评审凭据。

## 2. 终局结果（S8，跨轮最优口径，已经两轮独立验核）

| 轮次 | 达标（win+parity） | 五维总均差 |
|---|---|---|
| R1 原题 | 15/30 | −0.46 |
| R2 策略改写 | 17/30 | −0.45 |
| R3 再改写+换种子 | 17/30 | −0.51 |
| **FINAL 跨轮最优** | **17/30（56.7%）** | **−0.32** |

- 构成：win 10（SenseNova 反超，最高 case78 +2.60）+ parity 7 + fail 13；目标 24/30（80%）未完全达成。
- fail 梯度：6 例差距 ≤0.6（case130 gap 0.0 仅缺一个文字元素、case17 −0.2）；深坑为 case167（−3.0）、case8（−2.0）、case1/3（−1.2~−1.6）。
- 数据文件：`results/comparisons/final/report.json`（终局）、`results/comparisons/round-{1,2,3}/report.json`（各轮）。

## 3. 三轮策略效果结论（改写策略库的实证答案）

1. **S1 删微缩文字**：8 例乱码硬伤全部消除（small_text_exempt 豁免机制关键），但均分追平有限——治标成功、追分不足。
2. **S2 简化大字**：最有效——case9 fail→win、case14 fail→parity、case13 在 R2 从 −2.4 收窄到 −1.0。
3. **S4 风格锚定**：净负效应（case2 −1.2→−2.6、case3、case25 均恶化）→ 催生 R18：同策略重复时不再叠加指令、改为同文本换种子重试。
4. **换种子方差**：同提示词不同种子有 ±0.4~1.0 波动，是 R3 无净增的主因——提示词层面收益边界已到。
5. **残余差距根因**：微缩文字渲染与复杂排版是模型能力项，非提示词可解——这是下一代模型或多模态编辑链路的份额。

## 4. 运行规模与可靠性凭据

- 生成：116 张（R1 60 / R2 30 / R3 26），**全程零 GPU 失败**；台账 `ledger/append.jsonl`（404 行事件，含全部 sha256）。
- 评审：**146 份盲评 verdict**（116 复现 + 30 基线），`results/judge/`；判官自身一致性抽检最大均差 1.40（阈值 2.0，零仲裁）。
- 测试：65 个（零 GPU 可跑），CI 已接线 `.github/workflows/ci.yml`。
- 判官：GLM-5.3-Flash 视觉，经本机子代理通道（零 API key）；量规移植 Qwen-Image-Bench 五维 + 文字渲染硬门槛，模板 `scripts/judge-prompt.md`，金标准夹具 `docs/receipts/golden-judge-probe.md`。

## 5. 画廊与展示（三处，口径不同）

1. **发布画廊**（主仓库 README.md）：29 例左右对比（case3 因真实人物肖像按 spec §12 撤除，脚注注明），渲染器 `scripts/render_gallery.py --final`，规格化同画布 + width=420 + 双列 details 提示词 + `results/gallery/cmp/NOTICE.md`。
2. **R1 快照**：`results/gallery/wip-round1/`（60 张时代存档）。
3. **R3 实况**：`results/gallery/wip-round3/`（v3 最新提示词 vs 基线，13 迭代中案例，R2→R3 迁移逐例标注）。

呈现规范已固化为强制标准：工作区 AGENTS.md「图像对比画廊呈现规范」+ spec §12/§12.1。

## 6. 关键决策记录（摘要）

- 版权政策修订（2026-08-27 用户决策）：GPT-Image-2 参考图随画廊重分发，条件 = 逐例署名回链 + 目录 NOTICE（非商业评测、侵权即删）；`fetch-reference.sh` 锁 commit `9a7b2e9c…` + cases.json sha256 校验保留。
- case3 教训：策展人工目检漏掉真实人物肖像（Bastoni），发布层已撤除并记入 spec §12；策展排除依赖标题关键词不可靠，M5 需图像级审查。
- 盲性判定标准（R15）：禁止非对称侧信息；提示词固有 token（如 case10 题干自带 "GPT-Image-2"）不算泄露。
- 泄露扫描两级修正（R16/R17）：transcribed_text 豁免 + 题面豁免（token 出现在提示词原文中即属忠实度描述）。
- 重试语义（R10）：GPU 硬失败记录→对账→自动续跑，不中止整批。
- 台账去重（R13）：按 (type,idem)，防跨事件类型吞事件。
- 改写防呆（R14/R18）：同轮重跑守卫；同策略重复改写=同文本换种子。

## 7. 已知边界与 parked 项

- 对外 git push 在本沙箱代理下不可用，全部推送走 GitHub REST API（contents/blob→tree→commit→ref，树哈希断言）；仓库外部作者需标准 git 流程。
- ledger 健壮性小项（O(n) 扫描、秒级 ts）、run_judge_api 的 IncompleteRead 未捕获、manifest.orig_image 语义——均为 parked 的 Minor，见各任务评审记录（SDD 工作区已清理，要点已吸收进本文）。
- 一次性定时任务（CronCreate）在本环境两次未触发——长任务接力不要依赖它，用轮询或人工触发。
- 本地 feat/pipeline 分支保留（含 R16/R17/R18 原始提交历史，内容已重落 main），未推送远程；删除与否由作者决定。

## 8. 下一步选项（供总结的"展望"节引用）

1. **M5 扩批**：从 30 例扩至全量 535 例纯文生图案例（先修策展的肖像图像级审查）。
2. **edit 链路**：上游大量编辑型案例（需输入图），v2 支持后可评测图像编辑能力。
3. **模型升级重跑**：管线全自动化，新模型/新驱动仅需替换推理触点即可全量重跑对比。
4. **趋势发布**：当前 README 已是数据化战报形态，配合三轮策略效果链可直接作为发布叙事。

## 9. 复现指引

```bash
cd /workspace/awesome-sensenova-u1.5
bash scripts/setup.sh                 # 环境四断言 + 取参考数据 + 建目录
bash scripts/generate.sh 1            # GPU 批量生成（约 300s/张）
.venv-test/bin/pytest tests/ -q       # 65 个零 GPU 测试
.venv-test/bin/python scripts/compare_parity.py --final   # 跨轮最优终局计分
```

评审管线操作协议（含判官派发模板与一致性抽检规则）：`docs/operator-loop.md`。设计 spec：`docs/superpowers/specs/2026-08-27-awesome-sensenova-u15-design.md`；实施计划：`docs/superpowers/plans/2026-08-27-awesome-sensenova-u15.md`。
