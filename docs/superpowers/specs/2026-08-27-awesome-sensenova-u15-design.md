# awesome-sensenova-u1.5 设计文档

- 日期：2026-08-27
- 状态：已获口头批准的完整设计（待作者审阅本 spec 后转入实施计划）
- 上游依赖：[SenseNova-U1.5-ROCm](https://github.com/AIwork4me/SenseNova-U1.5-ROCm)（推理管线）、[freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2)（案例与参考基线）
- 相关背景：作者的 SenseNova-U1 上游 PR [OpenSenseNova/SenseNova-U1#260](https://github.com/OpenSenseNova/SenseNova-U1/pull/260) 已合并

> **术语与口径注记（2026-08-29）**：本文为历史设计记录，保留原始措辞。文中的「双盲」此后统一改称 **source-blind**（判官对图像来源盲：中性内容哈希 entry ID、来源元数据不进判官上下文、队列按轮号确定性乱序、落盘前泄漏扫描）——本协议是单侧盲（仅判官盲），非双方互盲，也非 A/B 成对比较（每 entry 独立打分）。结果表述自 2026-08-29 起分两级：primary = R1 原始提示词 15/30（original-prompt result）；跨轮最优 17/30 = prompt-adapted best observed（初称 optimization ceiling）。

## 0. 摘要

本项目把 awesome-gpt-image-2 的 535 个社区案例作为量化基线，建立一个**全自动评测闭环**：在单卡 AMD gfx1100（48 GB）上以 ROCm 7.14.0 全栈运行 SenseNova-U1.5-8B-MoT 同题生成图像，由 GLM-5.3-Flash 视觉判官对双方图片做双盲结构化评分，未达标的案例按失败归因自动改写提示词并重生成，直至满足打平标准或到达轮次上限；最终开源经过验证的提示词库、全部效果图和完整评审凭据。首发范围为 Pilot 30 例（覆盖上游全部分类），目标 80% 案例达到 parity。

## 1. 背景与动机

awesome-gpt-image-2 以"Prompt as Code"理念和 500+ 案例画廊登上 Trending 榜，但它交付的是提示词与闭源模型（GPT-Image-2）的效果图——读者只能看，无法复现。与此同时 SenseNova-U1.5-ROCm 已在 gfx1100 上完整验证了统一多模态模型的本地文生图管线（含 ROCm 7.14 全栈模式与逐字符海报文字验证），具备把"同题对比 + 可复现证据链"做成开源项目的全部前提。

两者结合即是本项目的差异化定位：**上游只有"别人的图"，我们额外交付可复现的本地图形栈证据链与量化对比结论**——这是 SenseNova-U1.5-ROCm 仓库 receipts 哲学的自然延伸，也是开源社区目前缺失的内容。

## 2. 目标与非目标

### 目标（v1）

1. 基于 SenseNova-U1.5-ROCm 构建，全程在 ROCm 7.14.0 栈上运行（硬件 gfx1100）。
2. 建立全自动闭环：取题 → 生成 → 盲评 → 归因 → 改写 → 复评，无人工介入跑通。
3. 判官必须使用 GLM-5.3-Flash 视觉能力（本机经子代理通道实现，已实测验证）。
4. 开源成果：打平的提示词库（原题+改写版+seed+provenance）、SenseNova 效果图、评审 JSON 凭据、双语 README 画廊与结论表。

### 非目标（v1 明确不做）

- 图像编辑型案例（上游大量案例需要上传输入图）→ 记入 v2 edit 队列。
- Web 前端 / 在线服务 / API（upstream 有 Vercel 站点，我们 v1 只交付纯仓库形态）。
- 全量 535 例与多 GPU 并行；Pilot 30 例达标后再决策扩批。
- 非 gfx1100 硬件的适配声明；gfx1151 等平台的报告欢迎但不承诺。

## 3. 已验证的技术前提（2026-08-27 实测）

| 前提 | 结论 | 凭据 |
|---|---|---|
| 推理环境 | `/workspace/venv-torch212` 内 torch `2.12.0+rocm7.14.0` 且 GPU 设备初始化成功，满足"必须在 ROCm 7.14.0 运行" | 本机可直接复验 |
| 主代理视觉 | GLM-5.3-Flash（本会话）真实读图并完成字符级转写、细节检查、量规评分演练 | 会话记录；发现的《功夫女足》小字乱码问题与基础仓库 README 记述一致 |
| 子代理判官 | general-purpose 子代理双盲评审两张匿名图（同题不同源），返回严格 schema 的判定并写盘；区分度符合预期（SenseNova 五维 7/8/7/7/8，GPT-Image-2 参考图 9/9/9/10/9） | `/tmp/judge_probe/verdict.json`（sha256 `811f2aed…`）；candidate_A 即基础仓库 `docs/results/gallery/posters/kungfu-girls.webp`（sha256 `235fd210…` 字节一致） |
| 云端 API 可达性 | `api.z.ai/api/paas/v4/chat/completions` 网络可达，无凭证返回 401（端点存在、仅需 key） | 本会话探测输出 |
| 参考资产 | 上游 `data/cases.json` 含 535 案例（13 分类、prompt 全文、styles/scenes 元数据），`data/images/` 含 538 张 GPT-Image-2 参考图共 157 MB | 已克隆于 `/tmp/awesome-gpt-image-2` |
| 评分量规母本 | Qwen-Image-Bench 五维 L1 维度 + L2/L3 检查清单 + 0/1/2/N/A 逐项打分法 | `/workspace/Qwen-Image-Bench/checklists.py` |

## 4. 架构

### 4.1 仓库结构

```
awesome-sensenova-u1.5/
├── README.md / README_CN.md        # 双语：画廊 + 对比结论表 + 快速复现
├── LICENSE                         # Apache-2.0（与基础仓库一致）
├── scripts/                        # 全部自动化入口
│   ├── env-check.sh                # 环境四项断言（§9），一切入口的第一步
│   ├── setup.sh                    # 自检 + 软链编排（镜像重建后一键恢复）
│   ├── fetch-reference.sh          # 锁定 commit 拉取上游 → third_party/ref/ + manifest 校验
│   ├── select-pilot.py             # 分类分层抽样 30 例 + 纯文生图过滤
│   ├── make-gen-jsonl.py           # 台账 → run-task.sh 的 --jsonl 批单
│   ├── generate.sh                 # 包装基础仓库 run-task.sh（唯一 GPU 触点）
│   ├── build-judge-tasks.py        # 组装双盲评审队列（中性编号+乱序）
│   ├── judge-prompt.md             # 判官系统提示词模板
│   ├── run-judge-api.py            # 后端 B：智谱 OpenAI 兼容 API 调 GLM 视觉
│   ├── collect-verdicts.py         # schema 校验 → 写台账
│   ├── compare-parity.py           # 打平规则判定（§8）
│   ├── rewrite-prompts.py          # 失败归因 → 策略库改写（§7）
│   └── render-gallery.py           # 终稿渲染双语 README 画廊区块
├── cases/pilot/case-{id}/          # base.md / adapted-v{N}.md / provenance.json
├── results/gallery/                # 我们的 SenseNova 出图（提交进仓库）
├── results/judge/                  # 全部评审 verdict JSON 凭据（提交进仓库）
├── ledger/append.jsonl             # 只追加事件账本（状态机唯一事实来源）
└── third_party/ref/                # gitignore；fetch 脚本产物，不重分发
```

### 4.2 组件职责与接口边界

依赖关系单向、每层可用一个文件理解：账本（append.jsonl）是各脚本唯一的共享状态；GPU 只有 `generate.sh` 一个触点；上游参考数据只有 `fetch-reference.sh` 一个触点；判官只通过队列目录与 verdict 文件交互，不直接读台账。每个脚本独立可运行、`--help` 可查，组合起来即全流程。

## 5. 评测闭环状态机

七个阶段，由账本事件驱动，任意步骤崩溃后可断点重跑：

1. **SELECT 策展**：从 13 个分类按比例抽 Pilot 30 例（Posters & Typography 权重最高——它是上游最大分类且文字渲染挑战最有说服力）；过滤编辑型案例进 v2 队列，并排除涉及真人肖像或品牌标识的案例（与 §12 发布边界一致）。产出 `cases/pilot/case-{id}/base.md` 与 provenance（回链 case id + sourceUrl）。
2. **GENERATE 生成**：每例每轮 N=2 个确定性种子；分辨率走模型最优 bucket；预算约 30 例 × 2 张 × 1–3 分钟 ≈ 每轮 1.5–3 小时。
3. **JUDGE 评审**：本轮 SenseNova 图与其对应参考图统一改为中性编号（如 `entry-{sha8}`）并乱序入队；判官对每张图独立盲评（不做 pairwise 以避免位置偏差）；子代理后端下并行派多个判官代理分批领任务。
4. **COMPARE 判定**：按 §8 规则产出每例 `parity | fail | win` 与未遵循项清单。
5. **REWRITE 改写**：仅对 fail 案例按失败类别选策略（§7）生成 `adapted-v{N+1}.md`，回到第 2 步且只重跑失败案例。
6. **收敛**：同一案例最多 3 轮改写；达成 §8 打平即冻结进入 PUBLISH 集；跑满上限仍未达标的保留最佳版本并在 README 如实标注分差——诚实报告是项目生命力，"未打平"本身就是有价值的数据点。
7. **PUBLISH 发布**：渲染双语 README（并排画廊：提示词 + 我们的图 + 上游回链）、结论汇总表、CHANGELOG；由作者执行 git push（对外发布动作永远留给人工触发）。

生成与改写事件的幂等键为 `(case_id, round, seed)`；判官事件以 `entry_id` 为幂等键（映射表保证 entry ↔ 来源唯一）；账本事件含时间戳与脚本版本号。

算力与成本预估（Coding Plan 口径）：第一轮盲评约 90 张图（60 张我们的双种子 + 30 张参考图；参考图评分全项目只做一次并可复用），探针实测单张严格评审约 40k 子代理 token，后续每迭代轮约 60 张；整个 Pilot 收敛期预计总消耗千万级子代理 token——在方案选型时已知悉并由订阅承担。

## 6. 判官协议（GLM-5.3-Flash）

### 6.1 量规

移植 Qwen-Image-Bench 的五维体系并适配为本项目 0–10 分制：Quality（物理逻辑/材质/边缘/噪点/AI 感/分辨率）、Aesthetics（构图/色彩/光影氛围/解剖学/情绪/风格还原）、Alignment（数量颜色形状材质匹配/动作/空间布局/场景）、Real-world Fidelity（地标与文化元素真实性/公平性/合规）、Creative Generation（想象力/融合无缝度/设计信息层级/镜头语言）。在其 L2/L3 清单基础上新增本项目特有的文字渲染硬门槛字段。

### 6.2 双盲机制

判官收到的任务只含：中性编号的图片路径 + 该图的生成提示词 + 量规 + 输出 schema；不含模型来源、不含其他候选的信息、不含任何历史评分。映射表（entry_id ↔ 来源）仅存于队列 manifest 与台账。判官须完成：五维打分及理由、全部可见文字逐字转写（伪字符区标 GARBLED 并估数）、硬门槛字段、`unfulfilled_requirements` 软性未遵循清单。

### 6.3 双后端（同量规、同 schema）

- **agent 后端（默认，v1 实际运行通道）**：主代理派发 general-purpose 子代理读图写 verdict 文件。零外部依赖，使用 Coding Plan 订阅算力，已实测通过。
- **glm_api 后端（随仓发布，供他人复现与 CI）**：调用智谱 OpenAI 兼容端点 `/api/paas/v4/chat/completions` 的视觉模型，key 由使用者自备注入环境变量；本项目自身运行不依赖此通道。
- 两后端使用同一份 `judge-prompt.md` 模板与校验器，保证可比性。

### 6.4 一致性保障

10% 样本做第二次独立盲评；两次五维均分差 > 2.0 的样本追加第三次仲裁评审，采信中位数语义（三评中位数）。schema 校验失败的 verdict 自动作废重派一次，再失败标记 `judge_failed` 由人工队列处理。

verdict JSON 完整 schema 见附录 B；判官输出之外的字段（case 关联、耗时、token 用量）由采集器补全后落盘到 `results/judge/`。

## 7. 提示词调试策略库

REWRITE 按 COMPARE 的失败归因选择策略，规则式优先以保证确定性与可审计性：

| 失败归因 | 策略 |
|---|---|
| 小字乱码 | 删除或大幅简化微缩文字要求（如职员表块 → 一行日期文案）；实测这是 SenseNova 相对 GPT-Image-2 的最大差距点，策略性回避优于硬刚 |
| 大字错误 | 缩短文案降低字形复杂度、明确逐字拼写、或改排为无文字主视觉版式 |
| 数量/布局未遵循 | 隐含描述改显式编号（"exactly three…"）、补充空间锚点词 |
| 风格差距 | 注入更强风格锚点（媒介术语、流派/画家、时代特征） |
| 解剖缺陷 | 构图规避（远景/背影/手部遮挡/道具遮挡指令） |

每次改写在 `provenance.json` 记录：原句、新句、策略名、触发原因、该版本得分——这套记录本身即是开源方法论贡献（"如何在 8B 统一模型上逼近闭源旗舰"的实战经验库）。改写器预留可选的 LLM 改写插件接口（调 GLM 文本模式），但 v1 默认规则式。

## 8. 打平标准（形式化）

单案例达标（parity）须同时满足以下五条，对照其配对的 GPT-Image-2 参考图评分：

(a) 五维均分 ≥ 参考图均分 − 0.5；
(b) `display_text_correct == true`；
(c) `small_text_quality != garbled`（若最新版本的提示词已按 §7 策略移除微缩文字需求则此项豁免，豁免事件计入 provenance）；
(d) `text_miss_count == 0`；
(e) 无画面级硬伤（解剖崩坏、结构性畸变等）。

里程碑：Pilot 30 例中 ≥ 24 例（80%）parity 且全部案例的五维总均差 ≥ −0.5，即可宣称"Pilot 批次打平"。multi-seed 取每例两枚种子的较优者进入判定（best-of-N 是合法的提示词工程实践，seeds 全部披露）。结果无论好坏均进 README 结论表。

## 9. 运行环境规范（ROCm 7.14.0）

一切脚本入口先执行 `env-check.sh`，断言四件事：`torch.__version__ == 2.12.0+rocm7.14.0`（复用本机已验证的 `/workspace/venv-torch212`，不新建虚拟环境，遵守 AGENTS.md 的 20 GB 容量纪律）；`HSA_OVERRIDE_GFX_VERSION=11.0.0` 已设置；SenseNova-U1.5-ROCm 仓库就位且 checkpoint manifest 校验通过（SHA256 清单沿用基础仓库机制）；ROCm 7.14 全栈组件可用（用户态安装沿基础仓库 `scripts/install-rocm-7.14-gfx110x.sh` 文档路径）。所有持久化路径位于 `/workspace` 下；`setup.sh` 一键自检并软链基础仓库路径，镜像重建后一条命令恢复全套能力，系统级重装命令一律写成仓库内脚本而非散落在 shell 历史。

## 10. 错误处理与幂等

- GPU 生成失败（OOM/驱动抖动）：整批最多复跑 2 次（种子不变，适配瞬时故障；确定性种子是复现性的根基，不因失败换种），仍失败的图记 `gen_failed` 跳出本轮，账本留痕，下轮自动补跑；确认是特定触发词导致算子缺陷时按案例手工调整种子参数并在 provenance 记录。
- 判官输出不合法：schema 校验拒绝后重派一次，再失败进人工处理队列。
- 上游漂移：fetch 锁 commit + manifest sha256 校验；升级 lockfile 属显式操作，需重跑受影响对比。
- 断点续跑：账本是唯一事实来源，任何脚本崩溃重跑均从最后事件续传；所有事件操作以幂等键去重。

## 11. 测试策略

- **判官协议金标准回归**：以本次探针的两张图与其已知评分区间做夹具，`judge-prompt.md` 或 schema 变更时必须复跑且分数区间相符。
- **compare-parity 单元测试**：合成 verdict 覆盖全部边界——恰好 −0.5 差、(c) 豁免逻辑、win/fail 分类、best-of-N 取优。
- **schema 校验器畸形样本测试**：缺字段、错类型、分数越界、非 JSON 输出。
- **端到端冒烟**：单案例单轮 dry-run（判官后端可 mock、生成跳过 GPU），不动显卡即可验证管线连通性，供 CI 使用。

## 12. 发布形态与版权边界（2026-08-27 用户决策修订）

我们的仓库提交自有资产：改写后的提示词（基于上游 MIT 协议文本的演绎，注明归属）、SenseNova 生成的图片、评审 JSON、全部脚本。

**参考图重分发政策（修订版，替代最初"不二次分发"决策）**：GPT-Image-2 参考案例图随对比画廊进入仓库，条件为——逐例附来源回链署名、目录内置 NOTICE（仅用于非商业评测对比、版权归原创作者、侵权即删）；`fetch-reference.sh` 锁 commit 机制保留，third_party/ref/ 仍是管线工作副本来源。涉及真人肖像或品牌标识的上游案例在 SELECT 阶段排除（2026-08-27 复盘：case3 的球员肖像属漏网，M4 发布集必须复核剔除）。

### 12.1 对比画廊呈现规范（定稿，与工作区 AGENTS.md 同步）

1. 左右对照表：左 = 参考基线（效果图+原提示词），右 = SenseNova 复现（效果图+执行提示词），每例一节；2. 复现图每例 1 张（确定性种子 k=0，其余种子目录内存档）；3. 两列图规格化为同一画布纵横比（参考图纵横比为基准、长边 1200、衬底取参考图四角均色）并以相同 width 渲染，左右等大；4. 提示词左右分列、各自 details 折叠全文，未改写轮次注明两侧同题；5. 逐例署名 + NOTICE；6. 每例附复现参数行；7. 页顶标注评分状态，判分后回填结论表。已上线实现样例：`results/gallery/wip-round1/`（46f403d）；`render_gallery.py` 的 M4 升级必须遵循本节。

## 13. 里程碑规划

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M0 | 仓库脚手架 + fetch/select/env-check | 冒烟测试过，30 例 base.md 就位 |
| M1 | GENERATE 接通 run-task.sh | 1 例端到端 dry-run + 1 例真机出图 |
| M2 | JUDGE+COMPARE 全 Pilot 第一轮 | 约 90 张图盲评完成（含参考图基线分），首轮结论表产出 |
| M3 | REWRITE 循环迭代至收敛 | 达成 §8 打平标准或如实报告差距 |
| M4 | PUBLISH 渲染 + 文档完善 | 双语 README 成品，作者审阅后 push |
| M5 | 扩批决策 | Pilot 数据复盘后另行立项 |

## 附录 A. 探针实测记录（2026-08-27）

双盲评审探针设计：《功夫女足》海报（SenseNova-U1.5 经基础仓库管线生成）与上游 case511《CAPE TOWN》字体嵌景海报（GPT-Image-2 参考图）分别改名 `candidate_A/B`，连同各自原始提示词交子代理盲评。结论：子代理完成字符级转写核查（确认功夫女足大字三处逐字正确、职员表约 80–110 字符为伪汉字乱码；case511 连路牌小字与开普敦真实经纬度坐标全对）、抓出软性未遵循项（"humorous"基调缺席、"subtle dragon"过于显眼）、区分度合理的五维评分。判定文件 sha256 `811f2aed44bec4e8174c1078a9d956f52af225f72a7090ec87b1a903222f9029`；candidate_A 与基础仓库画廊 `kungfu-girls.webp` 字节一致，sha256 `235fd2109c708284930e35cbe4ba99d18067e4fea498237ef2d280655197a939`；candidate_B（上游参考图）sha256 `cfdecfee76d725ba586e9d02a35d38ef53ca45d6a6c0c4e6bc233062df83dc6a`。证据链闭合。工程教训：判官任务的文件命名必须与任务描述严格一致（本次出现 A/B 与 1/2 不一致仍被正确处理，但不能依赖这种容错）。

## 附录 B. verdict JSON Schema

信封层由采集器构造，判官只产生 `verdict` 体：

```json
{
  "schema_version": "1.0",
  "entry_id": "entry-1a2b3c4d",
  "backend": "agent | glm_api",
  "judged_at": "2026-08-27T00:00:00Z",
  "verdict": {
    "scores": {
      "quality": "int 0-10",
      "aesthetics": "int 0-10",
      "alignment": "int 0-10",
      "real_world_fidelity": "int 0-10",
      "creative_generation": "int 0-10"
    },
    "score_reasons": { "<上述五键>": "string" },
    "unfulfilled_requirements": ["string"],
    "transcribed_text": ["string"],
    "hard_flags": {
      "display_text_correct": "bool",
      "small_text_quality": "correct | mildly_deformed | garbled",
      "text_miss_count": "int >= 0",
      "visual_defects": "bool"
    }
  }
}
```

采集器校验通过后组装完整信封落盘 `results/judge/{entry_id}.json`，字段为：schema_version / entry_id / backend / judged_at / source / case_id / round / seed / verdict；latency 与 tokens 属尽力而为字段（glm_api 后端记录响应耗时与用量，agent 后端记录派发耗时），缺失不阻塞校验；参考图条目同时写入 `_baseline/` 目录供各轮比较复用。台账追加 `judged` 事件。禁止判官输出中出现模型身份推断；一旦发现由采集器判废。

本设计已获批并转入实施：实现计划见 `docs/superpowers/plans/2026-08-27-awesome-sensenova-u15.md`（任务级步骤与其对应）。
