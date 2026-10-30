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
        （`0003` / `0004` / `0006` / `0010` / `0010z` / `0012` / `0028`），
        补丁被 `Skipping` 即失败
      - 重写补丁 `0012`（原先因 0003/0010z 的文件结构变化被静默跳过）：
        `arm_vm_init()` 在关掉 bootstrap TTBR0 之前，把早期控制台切到
        **同一物理帧的 physmap 别名**（查 `ptov_table`，要求整帧被同一段覆盖；
        不在 RAM 窗口则打印 `fb outside physmap` 后关闭，避免 fault），
        因此 `EARLY 8..19` 可见：8=切走前、9=physmap 生效、
        10..14=`arm_vm_init` 内部（TTBR0 关、指针重绑、`pmap_bootstrap`、
        I/O 页表）、15/16/19=`serial_init` 前后、17/18=fbcon 探测/映射；
        19 打过就关闭早期控制台，屏幕整块交给 fbcon（避免两套文字栅格互画）。
        physmap 是 cacheable，故打点后按 cache line 用 `dc cvac` 清到 PoC
      - `make-cepheus-adt.py` 的 fbcon 默认值改为设备树实测值，workflow 显式传参
      - 新增 `docs/device-capture-checklist.md`：七层信号、文字转写模板、判读表
      - CI 自身修掉一个假绿：`bash build.sh | tee build.log` 报的是 `tee` 的
        退出码，`0012` 第一版把 `arm64/cepheus_early.h` 引进 `pe_serial.c`
        （osfmk 头目录不在 pexpert 的 include path 上）导致编译失败，但 run
        仍然“成功”、产物里没有内核、release 步骤被静默跳过。现在 Build 步骤
        用 `set -o pipefail` 并断言 `fakeroot/.../kernel.*.cepheus` 真的存在；
        `pe_serial.c` 只前置声明 `cepheus_early_mark()`（`CEPHEUS_EARLY_MARK`）
      - 8796 CI run `40453235702`（commit `12cdc04`）从 Build 到 Publish 全部
        成功，release `k8796-40453235702`：`kernel.development.cepheus`
        17,256,384 B、`cust-payload.img` 67,108,864 B、`kernel.macho.adt`、
        `SHA256SUMS`、`xnu-8796-kernel.zip`
      - 产物侧抽样确认（`k8796-40449958126` 的内核，同一份 0012）：
        `llvm-nm` 有 `_cepheus_early_relocate` / `_cepheus_early_fb_phys` /
        `_cepheus_early_fb_bytes`，`strings` 有 `leaving bootstrap TTBR0`、
        `physmap framebuffer VA live`、`fb outside physmap; console off`；
        `arm_vm_init` 反汇编里能看到对上述函数的 `bl`。
- [x] 2026-10-30 真机实测：framebuffer 实测地址 `0x90000000`，定位“内核无输出”
      - 刷机包报的是 `k8796-40453235702`（commit `12cdc04`）；但底部同时出现
        **白/红/绿/蓝/品红**五种颜色，与检查点 A–D 的配色（白 stage0、红 A、绿 B、
        蓝 C、品红 D）完全对应，实际刷的可能是 `k8796-40703834057`
        （commit `7310028`，含检查点的最新 release）。两种情况下结论一致，
        只是 C/D 要靠 cache 被自然换出才偶尔可见
      - DarwinBoot 转写到的关键值：`video pa 0x90000000 1080x2340 row 4320
        bytes 32 bpp`、`entry pa 0xC4C30488`、
        `entry words 14000719 D503201F D503201F D503201F`、
        `CurrentEL 1 SCTLR_EL1 0xC01800? TCR_EL1 0x280803518`、
        `ID_AA64MMFR0_EL1 0x101122`、`ID_AA64PFR0_EL1 0x11112222`、
        `SecurityLock::LockType: SOFTWARE_LOCK...`、`App Log Flush : 0 ms`
      - 屏幕现象：底部绿条 + 我们的 64×32 白色 stage-0 方块（切表前 MMU-off 直写，
        所以可见），**没有任何 `CEPHEUS EARLY` 文字**；其余部分黑底
      - 根因：交接的 Video 是 `0x90000000`，不是设备树的 `0x9c000000`。该地址落在
        6 GB RAM 的 V=P identity 映射内，属性是 `ARM_TTE_BOOT_BLOCK`
        =`CACHE_ATTRINDX_WRITEBACK`；`0010` 只把硬编码的 `0x9c000000` 改成 NC block，
        于是 C 侧所有打点（以及 MMU 打开后的检查点 C/D，它们当时也硬编码
        `0x9c000000`）都写进 cache，显示控制器扫 DRAM 看不到，只有切表前的白块和
        A/B 两条色带能看见 ⇒ 内核入口执行过，问题在映射属性，不在启动流程
      - 修复 `0010z`：`start.s` 的 NC block 物理基址改为 `ldr x10, [x20,
        BA_VIDEO_BASE]`（为 0 才退回 `MOV64 0x9c000000`）；检查点 C/D 也从
        `MOV64 0x9c000000 + N*4320` 改为按 Video 的 base/rowBytes/height 计算，
        Video 无效时整段跳过（避免写到未映射地址）。注释里写明 write-back 陷阱
      - 修复 `0012`：`cepheus_early_sync()` 改为**无条件**按 64 字节 cache line
        `dc cvac`（删除 `early_cached` 标志及其在 `cepheus_early_relocate()` 里的
        赋值）。NC 映射下该指令是无害 no-op，WB 映射下是唯一能让像素落到 DRAM 的
        兜底；靠“自认为知道当前映射是不是 cacheable”来判断，正是这次全黑的来源
      - 验证：干净上游树（`xnu-8796.141.3`）按真实 apply 顺序
        `0003 → 0004 → 0008(start.s) → 0010 → 0010z → 0011 → 0012 → 0017(protos.h)`
        依次 `git apply` 全通过，结果与编辑树逐文件 `diff` 一致；两个补丁均无 CRLF。
        （只 apply 0003/0010/0010z 会失败：`0010z` 的检查点 C hunk 上下文里含有
        0004 改过的 `#if !VMAPPLE && !defined(CEPHEUS)`，所以验证树必须带上
        0004/0008）
      - 判读补充：C 侧色块只会是绿→黄（`0xff00ff00 | (stage&7)*32<<16`），
        `start.s` 另外画纯白 + 红/绿/蓝/品红四条检查点色带；除此之外的纯红/纯蓝/粉色
        一定来自开机图/logo 残留
- [x] 2026-10-30 晚真机实测：**四个汇编检查点全部出现**（红/绿/蓝/品红），死点越过
      - 现象：白 stage-0 块之外，红（A）、绿（B）、蓝（C）、品红（D）四条 64×8
        色带全部可见，位置与 `start.s` 中 `H-40 / H-48 / H-56 / H-64` 的计算一致
      - 结论：`start_first_cpu` 从 stage 0 一路执行到 `ret`，**`ret` 已经跳进
        `arm_init()`**。C/D 两条色带可见同时证明两件事：`0010z` 把 NC block 建在
        `boot_args->Video`（`0x90000000`）上生效了，且 MMU 打开后按 Video 的
        `rowBytes/height` 计算地址是对的。此前"有白块、无 D"的 write-back 陷阱
        已经解决
      - 因此死点被压缩到 `arm_init()` 函数体最前面这一段：从 `ret` 落地到
        `cepheus_early_mark(1, ...)`（`DTEntry chosen = NULL;` 之后）之间，或者
        `cepheus_early_video()` / `cepheus_early_mark()` 自身写屏失败
      - 下一步判据：顶部有没有 `CEPHEUS EARLY 0: video pa=0x...` 那一行字。
        有 ⇒ 汇编与 C 都健康，直接看 EARLY 停在几；没有 ⇒ 在 `arm_init` 入口加
        一条不依赖 `cepheus_early.c` 任何状态的青色彩带（裸内联汇编），把"C 侧画字坏"
        与"没进 arm_init"彻底分开

- [ ] 真机实测 fbcon 物理地址 / 面板 / 触摸 IC（地址已由设备树确认，运行期以
      `boot_args->Video` 为准；仍缺真机确认）
- [ ] UEFI 仓库 `uefi-cepheus`（已能出 UniXNU 镜像并推送诊断补丁，待真机验证）
- [ ] 阶段 1-7 bring-up（见 ../notes/cepheus-plan.md §5）
