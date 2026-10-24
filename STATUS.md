# 状态快照（cepheus）

> 本仓库从 nabu 移植骨架改造而来（2026-10-23）。nabu 的原始状态记录在 `docs/nabu-reference/STATUS.md`。

## 当前状态：骨架完成，待真机实测

- [x] 从 nabu 复制并重命名：configs / kits / scripts / CI workflow
- [x] 83 个 XNU 补丁内容统一改名（cepheus-fbcon / cepheus_early 符号链自洽）
- [x] `scripts/make-cepheus-adt.py` 完成（含 /cepheus-fbcon 节点，本地验证通过）
- [x] workflow MACHINE_CONFIG 改为 CEPHEUS（匹配补丁 0006 的 MASTER.arm64.cepheus）
- [x] board.toml 改为 cepheus（TODO_MEASURE 占位）
- [x] TODO-MEASURE.md 实测清单
- [ ] 克隆 Lux12138/UniXNU fork，取 make-nabu-adt.py 做底本 → make-cepheus-adt.py
- [ ] 真机实测：DRAM / userdata / fbcon 地址（见 TODO-MEASURE.md）
- [ ] 首轮 CI 内核构建跑通（不需要真机！push 后手动触发 workflow_dispatch）
      - CI 修复进度：ipsw pin → hostcompat env → iig 声明（v1，方向错误）→
        **v2（当前）**：Xcode 26.6 的 iig 生成 `UserSetProperties(OSContainer*, OSDispatchMethod = NULL)`
        两参声明；fork 的 out-of-line 定义重签为两参形式，弃用手写声明（会和生成声明
        构成歧义重载）。补丁 `patches/macos-iig-forwarder-decls.patch` 仅含
        IOService.h typedef + IOUserServer.cpp 签名修正。
- [ ] UEFI 仓库 `uefi-cepheus`（参照 uefi-sheng + nabu firmware-patches.md）
- [ ] 阶段 1-7 bring-up（见 ../notes/cepheus-plan.md §5）
