# 项目状态与交接文档（Project State & Handoff）

- 更新：2026-08-28 · main `37873fa`
- 术语与口径更新（2026-08-29，第二次收紧）：结果两级表述定名——primary = **original-prompt result**（R1 原始提示词 **15/30**；best-of-2 确定性种子/案例，GPT 侧参考图采样预算未知），secondary = **prompt-adapted best observed**（跨轮最优 **17/30**；含 task-relaxing 排版策略，衡量实践可用性而非同任务能力）；`双盲` 统一改称 **source-blind**（source-hidden task context：中性内容哈希 entry ID、来源元数据不进判官任务上下文、队列按轮号确定性乱序、落盘前泄漏扫描；单侧盲，非 A/B 成对比较；历史运行未做文件系统级隔离——manifest 与台账保留 entry→来源映射，未来运行用 `--isolated` 做 **provenance-separated judge queue**，非权限级隔离）。判官运行溯源：`results/judge/JUDGE-RUN-MANIFEST.json`（含 1.40 精确定义：盲样复评最大五维均值差；仲裁阈值作用于五维均值差而非单维度；复评存档仅 round-1 队列 9/90）。生成侧溯源：`results/generation/GENERATION-RUN-MANIFEST.json`（模型 revision/权重校验和 = not_recorded；wrapper 6a5785d + 上游 checkout 76c32c2f 可证；选择先于生成冻结：pilot lock 751986b @ 04:11:05Z < 首生成 04:52:26Z）。历史文档（spec/plans）保留原始术语，以其日期为准。
- 用途：本文件是项目的完整状态快照与交接包。任何新会话/新任务（例如"写项目总结"）只需读通本文，即可在零上下文下准确引用全部数据、结论与凭据位置。文中每个数字都可在所引路径复核。

## 1. 项目一句话

awesome-sensenova-u1.5：把 [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) 的社区案例冻结为精选参考集（curated GPT-Image-2 community reference outputs），在 AMD gfx1100 + ROCm 7.14.0 上用 SenseNova-U1.5-8B-MoT 同题复现，以 GLM 视觉判官 source-blind（判官对图像来源盲）评分，自动迭代提示词三轮，开源提示词库、全部效果图与可溯源评审凭据。

## 2. 结果（S8，已经两轮独立验核；自 2026-08-29 起按两级口径表述）

**Primary（original-prompt result）**：R1 原始提示词直出 **15/30**（Δ −0.46；提示词文本未改，每案例 2 枚确定性种子取优）——最少适配的 SenseNova 条件；GPT 侧参考为社区精选输出，原始采样预算未知。
**Secondary（prompt-adapted best observed）**：R2/R3/跨轮最优衡量**已测适配策略**下的实践可用性——部分策略刻意简化/放宽排版要求，不能解读为同任务模型能力或同等预算基准。

| 轮次 | 达标（win+parity） | 五维总均差 |
|---|---|---|
| R1 原题（primary, original-prompt） | 15/30 | −0.46 |
| R2 策略改写 | 17/30 | −0.45 |
| R3 再改写+换种子 | 17/30 | −0.51 |
| **FINAL 跨轮最优（prompt-adapted best observed）** | **17/30（56.7%）** | **−0.32** |

- 构成（FINAL）：win 10（SenseNova 反超，最高 case78 +2.60）+ parity 7 + fail 13；目标 24/30（80%）未完全达成。
- fail 梯度：6 例差距 ≤0.6（case130 gap 0.0 仅缺一个文字元素、case17 −0.2）；深坑为 case167（−3.0）、case8（−2.0）、case1/3（−1.2~−1.6）。
- 数据文件：`results/comparisons/final/report.json`（终局）、`results/comparisons/round-{1,2,3}/report.json`（各轮）。

## 3. 三轮策略效果结论（改写策略库的实证答案）

1. **S1 删微缩文字**：8 例乱码硬伤全部消除（small_text_exempt 豁免机制关键），但均分追平有限——治标成功、追分不足。
2. **S2 简化大字**：最有效——case9 fail→win、case14 fail→parity、case13 在 R2 从 −2.4 收窄到 −1.0。
3. **S4 风格锚定**：净负效应（case2 −1.2→−2.6、case3、case25 均恶化）→ 催生 R18：同策略重复时不再叠加指令、改为同文本换种子重试。
4. **换种子方差**：同提示词不同种子有 ±0.4~1.0 波动，是 R3 无净增的主因——在已测策略范围内，提示词改写的进一步收益有限（观察性结论，非普遍证明）。
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
