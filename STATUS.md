# 状态快照（cepheus）

> 本仓库从 nabu 移植骨架改造而来（2026-10-23）。nabu 的原始状态记录在 `docs/nabu-reference/STATUS.md`。

## 当前状态：两条 CI 线都能出可刷产物，待真机 bring-up

| 线 | 内核基线 | CI 产物 | 触发 |
|---|---|---|---|
| 10063（`build-kernel.yml`） | xnu-10063（iOS 17 / macOS 14 世代） | kernel + payload + userdata 镜像 + `cust-payload.img` | 手动 `workflow_dispatch` |
| 8796（`build-kernel-8796.yml`） | xnu-8796（iOS 16 / macOS 13.5 世代） | `kernel.development.cepheus` + `kernel.macho.adt` + `cust-payload.img`（release 里同时给 `xnu-8796-kernel.zip`） | push `xnu-8796/patches/**` 或本 workflow，也可手动 |

## 已完成

- [x] 从 nabu 复制并重命名：configs / kits / scripts / CI workflow
- [x] XNU 补丁内容统一改名（cepheus-fbcon / cepheus_early 符号链自洽）
- [x] `scripts/make-cepheus-adt.py` 完成（含 /cepheus-fbcon、/cepheus-ufs；本地验证通过）
      - 2026-10-26 增加 `--iphone-identity`：根 `model=iPhone10,3`、首条
        `compatible=D22AP`，匹配补丁 0059（`hw.machine`/`hw.model`）与 0061
        （1125x2436 逻辑面板）的 iPhone X 用户态预期；8796 线使用它，
        10063 线仍用 `--ipad-identity`
- [x] workflow MACHINE_CONFIG 改为 CEPHEUS（匹配补丁 0006 的 MASTER.arm64.cepheus）
- [x] board.toml 改为 cepheus（fbcon 地址等仍为 TODO_MEASURE）
- [x] TODO-MEASURE.md 实测清单
- [x] 82 个 XNU 补丁 + 3 个 stage 脚本（2026-10-26 删除
      `0082-nabu-ufs-aes-board.patch`：它是 nabu 时代机械改名的合并残片，
      整补丁因 start.s / cepheus_early.c 的旧面板尺寸 hunk 在 CI 里被跳过；
      其中唯一仍有效的 IOFindBSDRoot 命令行日志和空 `rd` 兜底已并入 0028）
- [x] 首轮 CI 内核构建跑通（不需要真机）
      - 8796：macos-14 + Xcode 15，`blacktop/darwin-xnu-build`，出 arm64 内核
      - 10063：macos-26 + Xcode 26.6，走 `Lux12138/UniXNU` 的
        defconfig → fetch → tree → build kernel → build payload 流程
- [x] 8796 线补上 payload：`make-cepheus-adt.py` + `make-cepheus-cust-payload.sh`
      生成 64 MiB FAT16 `cust-payload.img`（kernel + ADT + 空 ramdisk + unixnu.toml），
      release 同时发布 `xnu-8796-kernel.zip`（artifact 同布局）和散文件
- [x] 真机实测 DRAM（6GB 变体 `0x180000000`）和 userdata 分区几何
      （`0x7C000`–`0x1C47FFA`，4K LBA）
- [x] 2026-10-27 诊断改造（无真机阶段，把一次启动的信息量拉满）
      - `uefi-cepheus` commit `e5cd141`：DarwinBoot 交接绿条从顶部移到**底部**，
        并重复打印 `video pa` / `entry pa`；CI 去掉 `continue-on-error`，
        改用 `git apply --check` 强校验
      - 补丁 `0003` 重写：fbcon **优先用 `PE_state.video`**（= `boot_args->Video`，
        UEFI 真实 GOP 地址），ADT `cepheus-fbcon` 仅回退；背景改深蓝
        `0xff003060`；注册成功打印 `cepheus fbcon ready: pa=0x... WxH row N`
      - 新增补丁 `0010z`：`start.s` 的 stage-0 方块和 `arm_init()` 的早期打点
        都改为**直接读 `boot_args->Video`**（`genassym.c` 新增 `BA_VIDEO_*`
        偏移；无效才退回设备树地址），白块证明入口汇编执行、变绿证明
        `arm_init()` 进入；`CEPHEUS EARLY 0` 行打印 pa / w / h / row，
        Video 不可用时打印 `BAD` 与原始值。后缀用 `z` 而不是 `a`：
        补丁按 locale 排序，`0010a-` 在 en_US/zh_CN 下会排到 `0010-` **前面**，
        那样补丁会静默 `Skipping`
      - `build-kernel-8796.yml` 新增“关键补丁必须应用”断言
        （`0003` / `0004` / `0006` / `0010` / `0010z` / `0028`），
        补丁被 `Skipping` 即失败
      - `make-cepheus-adt.py` 的 fbcon 默认值改为设备树实测值，workflow 显式传参
      - 新增 `docs/device-capture-checklist.md`：七层信号、文字转写模板、判读表
- [ ] 真机实测 fbcon 物理地址 / 面板 / 触摸 IC（地址已由设备树确认，运行期以
      `boot_args->Video` 为准；仍缺真机确认）
- [ ] UEFI 仓库 `uefi-cepheus`（已能出 UniXNU 镜像并推送诊断补丁，待真机验证）
- [ ] 阶段 1-7 bring-up（见 ../notes/cepheus-plan.md §5）
