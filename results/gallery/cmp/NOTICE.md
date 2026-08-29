# 版权与使用声明（NOTICE）

本目录中的 `case{id}.webp` 为参考基线显示副本（规格化：长边 1200、WebP q88），源自 [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2)（MIT 协议仓库）收录的社区案例效果图，原始创作者见 README 各例的来源链接（署名与溯源逐例保留）。这些图片**仅用于本项目的非商业性生成质量评测对比**，著作权归各自创作者所有；各图来源与再分发权利状态可能不同，本仓库不因上游仓库的开源协议而主张任何再分发权利，权利人可随时要求移除。长期更优的架构是 manifest + URL + SHA256 + 拉取脚本——`scripts/fetch-reference.sh` 已锁定上游 commit 并做校验和验证；仓库内提交的显示副本仅为冻结审计结果的可复现性而保留。

`case{id}-winner.webp` 为本仓库管线在 AMD ROCm 7.14.0 上由 SenseNova-U1.5-8B-MoT 生成的复现图显示副本（与参考副本同画布规格化），按确定性种子可复现（seed 见 README 各例复现参数行与台账）。
