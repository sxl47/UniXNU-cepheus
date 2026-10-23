# 状态快照（cepheus）

> 本仓库从 nabu 移植骨架改造而来（2026-10-23）。nabu 的原始状态记录在 `docs/nabu-reference/STATUS.md`。

## 当前状态：骨架完成，待真机实测

- [x] 从 nabu 复制并重命名：configs / kits / scripts / CI workflow
- [x] board.toml 改为 cepheus（TODO_MEASURE 占位）
- [x] TODO-MEASURE.md 实测清单
- [ ] 克隆 Lux12138/UniXNU fork，取 make-nabu-adt.py 做底本 → make-cepheus-adt.py
- [ ] 真机实测：DRAM / userdata / fbcon 地址（见 TODO-MEASURE.md）
- [ ] 首轮 CI 内核构建跑通（不需要真机！push 后手动触发 workflow_dispatch）
- [ ] UEFI 仓库 `uefi-cepheus`（参照 uefi-sheng + nabu firmware-patches.md）
- [ ] 阶段 1-7 bring-up（见 ../notes/cepheus-plan.md §5）
