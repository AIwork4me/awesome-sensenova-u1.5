# 评审操作手册：无人值守运行协议

本手册是任何无人值守会话（本机 ZCode 定时会话、未来 cron 化的判官代理）驱动完整评测闭环的唯一操作依据：从 GPU 生成、盲评判官派发、判定采集到打平比较与提示词改写循环，全部步骤无需人工介入即可照做。两条铁律先于一切步骤：所有命令一律以仓库根 `/workspace/awesome-sensenova-u1.5` 为工作目录执行；`git push` 永远由人类执行，自动化会话在任何情形下都不得代劳。判官协议正文见 `scripts/judge-prompt.md`，金标准回归夹具见 `docs/receipts/golden-judge-probe.md`，打平标准的定义与错误处理/幂等语义分别见设计文档 `docs/superpowers/specs/2026-08-27-awesome-sensenova-u15-design.md` §8（打平标准）与 §10（错误处理与幂等）。

## 1. 一轮的定义

一轮（round）是状态机的一次完整推进，六步固定顺序、缺一不可：

1. `bash scripts/generate.sh ROUND` —— 唯一 GPU 触点；内部先跑 `env-check.sh`，再按台账增量组装批单、调基础仓库 run-task 生成、对账落账本，整轮最多 3 次 attempt，无 pending 时短路退出。
2. `.venv-test/bin/python scripts/build_judge_tasks.py --round ROUND` —— 组装本轮盲评队列到 `runs/judge-queue/round-N/`（entries/prompts/verdicts 三目录加 manifest.json 与 tasks.jsonl），参考图首轮后经 `_baseline` 缓存不再重复入队。队列按轮号确定性乱序（seed = sha256("queue-ROUND")），entry_id 为图像内容 sha256 前 8 位的中性编号，原始文件名与来源元数据不进入判官上下文——这是 source-blind 协议（判官对图像来源盲）的实现载体。
3. 判官批阅 —— 按 §2 的派发模板把 tasks.jsonl 分批交给子代理，直至每个 verdict_path 都已落盘。
4. `.venv-test/bin/python scripts/collect_verdicts.py --round ROUND` —— schema 校验 + 身份泄漏扫描，合格 verdict 加信封写入 `results/judge/{entry_id}.json`，非法文件移入 `verdicts-invalid/` 并记 `judge_failed` 台账事件（走 run_judge_api 判定的批次须按 §3 传 `--backend glm_api`）。
5. `.venv-test/bin/python scripts/compare_parity.py --round ROUND` —— 对照参考基线做打平判定，产出 `runs/comparisons/round-N/report.json` 与 `compared` / `status_parity` 台账事件（T13 交付；`status_capped` 由第 6 步的 rewrite_prompts 封顶时落账，compare 本身不写）。每份 report 都是累计视图：上轮已判而本轮没有新决策的案例（通常是已被冻结、不再产生批单）会以 `carried_from_round` 字段结转进 per_case 并计入 milestone 分母。
6. 若 report 存在 fail 案例且 ROUND < MAX_REWRITE_ROUNDS(=3)：`.venv-test/bin/python scripts/rewrite_prompts.py --round ROUND` 应用改写策略生成 `adapted-v{ver}.md`（T14 交付），然后回到第 1 步——下一轮的 generate 只会为失败案例产生 pending 批单行，已达标的案例自动出局。注意 rewrite_prompts 的接口只有 `--round`（int）与可选 `--ledger`，并没有 `--report` 参数：报告路径固定由轮次推导为 `runs/comparisons/round-{ROUND}/report.json`，且 `--round` 必须显式给出——缺省 None 会去读不存在的 round-None 路径直接报错；同一轮的重跑防重守卫同样靠这个显式 `--round` 生效。

无人值守执行块（每轮开始前把 JROUND 的 `<当前轮>` 占位替换为实际轮号，逐段原样投喂；本手册所有片段统一只用这一个轮次变量）：

```bash
JROUND="<当前轮>"
bash scripts/generate.sh "$JROUND"
.venv-test/bin/python scripts/build_judge_tasks.py --round "$JROUND"
# → 执行 §2 判官派发，直到该队列无缺失 verdict → 执行 §3 抽检 → 然后才继续：
.venv-test/bin/python scripts/collect_verdicts.py --round "$JROUND"
if [ -f scripts/compare_parity.py ]; then .venv-test/bin/python scripts/compare_parity.py --round "$JROUND"; else echo "[skip] compare_parity 尚未交付(T13)，本轮不判定"; fi
```

第 6 步的条件分支独立成块，仅当 report 中有 fail 且未达轮次上限时执行：

```bash
# 仅当 runs/comparisons/round-$JROUND/report.json 含 fail 且 $JROUND < 3 时执行：
.venv-test/bin/python scripts/rewrite_prompts.py --round "$JROUND"
# → 回到 bash scripts/generate.sh "$((JROUND+1))"
```

## 2. 判官派发模板

主代理（或定时会话里的代理）读取 `runs/judge-queue/round-N/tasks.jsonl`，每批 ≤6 个 entry，构造派发消息 = `scripts/judge-prompt.md` 全文原样粘贴 + 本批清单（逐条列出 image_path / prompt_path / verdict_path 三个绝对路径），经控制器代理的子代理工具发出。tasks.jsonl 里记录的是相对仓库根的路径，派发前必须解析成绝对路径再写进任务书——judge-prompt.md 明确要求子代理严格按任务书路径落盘。分批清单可这样生成（自本节起，文档内所有队列清点/抽检/收采片段统一使用轮次变量 JROUND——把 `<当前轮>` 替换为实际轮号即可原样投喂，后续各节不再重复说明）：

```bash
JROUND="<当前轮>"
PYTHONPATH=scripts .venv-test/bin/python - "$JROUND" <<'PY'
import json, os, sys
root = os.path.abspath(".")
rows = [json.loads(l) for l in open(f"runs/judge-queue/round-{sys.argv[1]}/tasks.jsonl") if l.strip()]
for r in rows:
    print(r["entry_id"], *(root + "/" + r[k] for k in ("image_path", "prompt_path", "verdict_path")))
PY
```

派发消息模板（变量只有 entry 批次路径本身，其余文字一字不改）：

```text
{{scripts/judge-prompt.md 全文原样粘贴于此}}

以下为本批 entry 任务书（共 K 条，K ≤ 6），路径均为绝对路径，verdict 一律写到任务书给出的 verdict_path：
1. image_path={{绝对路径}} prompt_path={{绝对路径}} verdict_path={{绝对路径}}
2. image_path={{绝对路径}} prompt_path={{绝对路径}} verdict_path={{绝对路径}}
…（直到第 K 条）
```

子代理回复后必须核对每一个 verdict_path 已真实落盘（不信任口头确认）；缺失者用同一模板补派一次，补派仍缺失即视为该 entry 进入 §4 非法输出协议处理。核对命令：

```bash
JROUND="<当前轮>"
PYTHONPATH=scripts .venv-test/bin/python - "$JROUND" <<'PY'
import json, pathlib, sys
rows = [json.loads(l) for l in open(f"runs/judge-queue/round-{sys.argv[1]}/tasks.jsonl") if l.strip()]
missing = [r["entry_id"] for r in rows if not pathlib.Path(r["verdict_path"]).exists()]
print("dispatch complete" if not missing else f"re-dispatch once: {missing}")
PY
```

## 3. 一致性抽检

collect 之前（或之后立刻、且在 compare 之前均可，但必须在 compare 使用数据前完成裁决回写）：随机抽取 ceil(entries×0.1) 个已判 entry 作为盲样重走一次 §2 派发，第二次评审判定写成新文件放到同一队列目录的 `verdicts-resample/` 下（其余两个路径不变，样本选择与批次划分都不得让判官知道是复评）。抽取数量计算：

```bash
JROUND="<当前轮>"
PYTHONPATH=scripts .venv-test/bin/python - "$JROUND" <<'PY'
import json, math, sys
from lib.constants import ARBITER_MEAN_DIFF, RESAMPLE_RATE   # 2.0 / 0.1
m = json.load(open(f"runs/judge-queue/round-{sys.argv[1]}/manifest.json"))
print("entries =", len(m), "-> resample_n =", math.ceil(len(m) * RESAMPLE_RATE))
PY
```

比对两次 verdict 的五维分逐维求均差；任一维度差值 > `ARBITER_MEAN_DIFF`（=2.0，取自 `scripts/lib/constants.py`，勿手抄数字）就追加第三次仲裁评审，然后三个结果逐维取中位数作为最终分数，以编辑文件的方式直接修正正式 verdict（保持 JSON 结构与文件路径不变），并在台账追加一条注释事件说明校正原因与本组三份原始分。这一仲裁步骤无脚本承载，属代理手工操作；三次评分的分歧本身记入 `judge_failed` 类注释事件（idem 用 `{entry_id}#resample-arbiter` 形式，避免与 collect 的同名键去重冲突）。resample 文件永不进入 `results/judge/` 正式集合。走 run_judge_api 判定的批次收采时必须传 `--backend glm_api`：`.venv-test/bin/python scripts/collect_verdicts.py --round "$JROUND" --backend glm_api`（或事先导出 `JUDGE_BACKEND=glm_api`；缺省记 agent），否则信封会把云端判定误标成代理判官，污染后续审计。

## 4. 非法输出协议

collect 报 invalid 后，非法文件已在 `runs/judge-queue/round-N/verdicts-invalid/` 且台账已有对应 `judge_failed`（payload 含前 3 条校验错误），读出 invalid 文件定位问题。属可修复格式类（markdown fence 包裹、尾随逗号等纯语法瑕疵）时，由评审代理修正内容并重交：把修好的 JSON 写回该 entry 的正式 `verdicts/{entry_id}.json` 路径后重跑一次第 1 节第 4 步的 collect——collect 对已存在信封的 entry 会跳过（幂等），因此只会补收这批修复件。修正+重交只允许一次；第二次仍然校验失败就把该 entry 标记跳过（不再派发），并在当轮 report 中如实记入 caveat 条目，不得静默丢弃。

```bash
JROUND="<当前轮>"
ls "runs/judge-queue/round-$JROUND/verdicts-invalid/" 2>/dev/null; echo "(空目录 = 本轮无非法输出)"
```

## 5. 终止条件与发布边界

整个循环的终止条件二选一：(a) 最新 report 中没有任何 fail 案例，**且**最新 report 的 milestone.total > 0（即 per_case 非空——首轮尚未产出任何判定、或整体全 deferred 的轮次不构成可发布终止态，不允许拿空报告收口发布）；(b) 所有未达标案例都已达到 MAX_REWRITE_ROUNDS=3 轮上限（上限值同样从 `scripts/lib/constants.py` 读取）。达标部分进入 PUBLISH：由 Task 16 的渲染脚本 `scripts/render_gallery.py` (T16 提供) 把获胜图复制进画廊、替换 README 占位符、生成双语结论表与 CHANGELOG 发行小节；跑满上限仍未达标的案例保留最佳版本，结论表如实标注 gap——诚实报告优先于好看的数据。渲染脚本永远不会触碰远端：发布收口的最后一步 `git push` 是纯人类动作，任何会话、任何定时器、任何"顺手"都不得执行。

## 6. 成本护栏与 GPU 节奏

单轮判官 token 预算 ≈ entries×40k（探针实测单张严格评审约 40k 子代理 token；entries 计 manifest 全量含 resample 复评）。连续两轮超出预算 50% 以上时立即暂停循环并审计批阅是否有重复派发——查法是统计台账 judged 事件数与各队列 tasks.jsonl 行数的差、并核对是否存在被绕过去重而重复派发的批次：

```bash
PYTHONPATH=scripts .venv-test/bin/python - <<'PY'
import collections, json
c = collections.Counter()
for line in open("ledger/append.jsonl"):
    ev = json.loads(line)
    if ev["type"] == "judged":
        c[ev["idem"]] += 1
dups = {k: v for k, v in c.items() if v > 1}
print(dups if dups else "no duplicate judged events")
PY
```

GPU 侧事实基准：2048² balanced 档单张约 320–355 秒（口径见台账 ops 实测记录）；一轮 60 张全量生成约 5.3 小时——永远安排过夜时段运行，无人值守期间以 ≥90 秒间隔轮询 `runs/genlogs/` 下的日志，禁止更高频率的探询循环。

## 7. 金标准回归门槛

凡量规、`scripts/judge-prompt.md` 模板或判官后端的任何变更，合入前必须按 `docs/receipts/golden-judge-probe.md` 重跑双案评审并通过其验收区间（A 案五维均分 ∈ [6.5, 8.5] 且 small_text_quality=garbled；B 案 display_text_correct=true 且转写出开普敦坐标串；B ∈ [8.5, 10]）。夹具的固定输入在本仓库之外：A 案取自基础仓库 posters jsonl 与画廊 webp，B 案取自 `third_party/ref/data/images/case511.jpg`。开跑前先验证三份输入全部在场：

```bash
test -f /workspace/SenseNova-U1.5-ROCm/examples/posters-2026-08.jsonl && test -f /workspace/SenseNova-U1.5-ROCm/docs/results/gallery/posters/kungfu-girls.webp && test -f third_party/ref/data/images/case511.jpg && echo golden-probe-inputs-present
```

任一缺失先恢复环境（基础仓库 checkout 或重跑 fetch-reference 流程）再谈回归，绝不允许用替身图片代替固定输入。

## 附录 A. 成员资格权威与台账幂等键

案例成员资格的唯一权威是 `configs/pilot.lock.json`；台账里出现已被后续锁定结果取代的 `sel-*` 事件属于设计内现象（append-only 账本不改历史），以 lock 文件为准，不要试图"清理"它们。全部事件类型的幂等键如下（自 R13 起 dedupe 以 (type,idem) 复合键判断，跨类型同 id 不再互相压制）：

| 事件 | 幂等键 | 说明 |
|---|---|---|
| generated | tag | 如 `case511-r2-s1`，同 tag 视为已完成 |
| gen_failed | tag#attemptN | 同一 tag 各 attempt 各记一条，互不去重 |
| case_selected | sel-{id} | 取代关系由 lock 权威裁定 |
| ref_fetched | commit 前 12 位 hex | 锁定上游 commit |
| judged / judge_failed | entry_id | 采集与一致性抽检共用前缀约束见 §3 |
| rewritten | rw-{case}-{ver} | T14 提供的事件面 |
| compared / status_parity | cmp-{R}-{case} | 唯一写入方是 compare_parity.py（T13 事件面） |
| status_capped | cap-{case} | 唯一写入方是 rewrite_prompts.py 的封顶路径（达 MAX_REWRITE_ROUNDS 后再遇 fail 时追加，幂等去重保证只记一条） |

## 附录 B. 锁文件演练安全规则

给 select-pilot/make_gen_jsonl/build_judge_tasks 写冒烟演练时，切不可想着"把目标改名为 pilot.lock.smoke.json 再靠环境变量指过去"——这套环境变量覆盖机制目前并不存在，三个消费方与生成方都硬编码 `configs/pilot.lock.json` 这一个路径。因此演练必须遵循复制-恢复 + 首次快速轮询纪律：备份真实 lock → 用冒烟 lock 覆盖硬编码路径 → 目标命令以后台方式启动 → 60–90 秒内完成首次轮询 → 发现 pending 数超过计划冒烟数立即 kill → 无条件恢复真实 lock 并 diff 确认。

```bash
cp configs/pilot.lock.json /tmp/drill-real-lock.json            # 1. 备份权威 lock（恢复源）
printf '{"upstream_commit": "drill", "size": 2, "cases": []}' > /tmp/drill-smoke-lock.json
cp /tmp/drill-smoke-lock.json configs/pilot.lock.json           # 2. 冒烟 lock 覆盖硬编码路径
# 3. 此处后台启动被演练命令（run_in_background 或 nohup … &）
sleep 75                                                        # 4. 60–90 秒窗口内的首次轮询占位
# pending > 计划冒烟数 ⇒ 立即 kill 目标进程；无论如何接着执行：
cp /tmp/drill-real-lock.json configs/pilot.lock.json            # 5. 无条件恢复
diff -q /tmp/drill-real-lock.json configs/pilot.lock.json       # 6. 确认恢复无差异（应无输出）
rm -f /tmp/drill-real-lock.json /tmp/drill-smoke-lock.json
```

kill 逃逸的最后防线是把第 5 步设为陷阱兜底（trap on EXIT），演练会话无论正常结束还是被打断都必须以恢复动作收尾；演练结束取走的证据只允许指向 /tmp 或 runs/，不允许改写 configs/ 的最终状态。

## 附录 C. 脚本撰写约定

管线脚本必须是 import-safe 的：模块导入零副作用（不建目录、不读写 ledger、不发网络请求），入口逻辑一律置于 `if __name__ == "__main__":` 守卫之下——因为 `tests/conftest.py` 会对 scripts/ 下所有带连字符的脚本做 eager 导入注册，任何导入期副作用都会污染测试收集甚至误触生产路径。新增脚本沿用现有形态：argparse 于 main() 内构建、路径常量集中头部、批量副作用显式传参。
