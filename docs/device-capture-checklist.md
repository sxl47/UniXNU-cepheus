# 真机采集清单（一次启动榨干信息）

> 目的：真机只有一两次机会时，用屏幕上的**分层信号**回答同一个问题——
> 内核到底走到哪一步、framebuffer 地址对不对。
>
> 适用：`Mu-cepheus-unixnu.img`（UEFI + DarwinBoot 诊断版）
> + 8796 `cust-payload.img`。

## 0. 安全边界

只做两件事：

```bash
fastboot flash cust cust-payload.img   # 只写 cust
fastboot boot Mu-cepheus-unixnu.img    # 临时引导，不写盘
```

不碰 `abl` / `xbl` / `bootloader` / `modem` / `persist` / `dtbo` / `vendor`。
卡死长按电源 10 秒强制重启回安卓。

## 1. 记录工具

- 另一台手机/相机拍**整屏**，重点再单独拍两张：
  - **顶部 1/3**（`CEPHEUS EARLY` 文字、内核日志）
  - **底部 100 px**（交接绿条、stage 色块、白色小方块）
- 本仓库的 agent 看不了图片，**必须文字转写**。按 §4 模板照抄即可。
- 录一段 60 秒视频更稳：色块是逐格增加的，静态照片可能只拍到最后一格。

## 2. 启动步骤

1. `fastboot boot Mu-cepheus-unixnu.img`。
2. UEFI 菜单出现后，用音量键/电源键选择 **UniXNU**。
3. 出现 DarwinBoot 日志后**不要按键**，让它自己走。
4. 观察 30–60 秒；画面不再变化再开始拍照/录像。
5. 若全黑超过 60 秒，长按电源重启。

## 3. 应该依次看到的七层信号

信号是**从早到晚**排列的；看到第 N 层就说明前 N 层全部成功。

| # | 画面 | 含义 | 地址来源 |
|---|---|---|---|
| A | UEFI 菜单 | 固件正常 | — |
| B | DarwinBoot 日志 + **屏幕最底部**一条绿色横条 | 交接桩执行到 `br x1` 之前 | `Video[0]`（UEFI GOP） |
| C | 屏幕**最左下角**一块 64×32 像素白色小方块 | 内核入口第一条指令执行了（`start.s`，无栈无页表） | `boot_args->Video`，无效才退回 `0x9c000000` |
| D | 顶部一行 `CEPHEUS EARLY 0: video pa=0x... w=1080 h=2340 row=4320` | `arm_init()` 已进入；左下角色块前 48 px 变绿，C 侧打点接管同一屏幕 | `boot_args->Video` |
| E | 底部 20 个 48 px 宽色块（stage 0..19），伴随 `CEPHEUS EARLY 0..19: <label>` | 内核逐段推进；停在第几格就是卡在第几个检查点之后 | 前 8 格 `boot_args->Video`，8 之后为同一物理帧的 physmap 别名 |
| F | 整屏**深蓝底** + `cepheus fbcon ready: pa=0x... WxH row N` | `serial_init()` 走到 framebuffer 控制台注册，之后的 kprintf 都可见 | `PE_state.video`，回退 ADT |
| G | 蓝底上的内核日志/panic 文本 | 正常启动或明确 panic | 同上 |

### 关键点

- **B 的绿条现在在底部**。以前在顶部，正好盖掉 DarwinBoot 打印的
  `video pa` / `entry pa` 两行——静默内核唯一的诊断依据。
- **C 和 D 是两道独立证明，且都读 `boot_args->Video`**：
  - C 是纯汇编，在 C 代码、页表、串口之前就画，证明**内核入口执行了**。
  - D 是 `arm_init()` 的第一件事，同时把 w/h/row 报出来，证明**早期 C 环境可用**。
  - 两者地址一致且可见 ⇒ UEFI 交接的 framebuffer 正确。
  - 若 D 显示 `... video BAD`，下一行是 `raw pa=0x... w=... h=... row=...` ⇒
    交接的 Video 不可用，内核退回了 `0x9c000000`；把 raw 值记下来就是下一版
    该修的地方。
  - `w` / `h` / `row` 是十进制像素/字节数，`pa` 是十六进制物理地址。
- **EARLY 8 → 9 是地址空间切换的证明**：
  - 8 写在 `arm_vm_init()` 关掉 bootstrap TTBR0 之前，仍走 VA=PA。
  - 9 写在切换到 physmap 别名之后；9 出现 ⇒ 内核已经用“能活到最后的映射”继续
    写屏幕，后面 `pmap_bootstrap` / `serial_init` 期间的打点都可信。
  - 只到 8 不到 9 ⇒ physmap 别名没命中；若 8 的标签正是
    `fb outside physmap; console off`，说明交接地址不在 RAM 映射窗口内。两种
    情况下内核都还在跑，问题只在早期控制台，不在启动流程本身。
- **10..14** 在 `arm_vm_init` 内部（TTBR0 关闭、physmap 指针重绑、`pmap_bootstrap`、
  I/O 页表）；**15/16** 在 `serial_init()` 两侧；**17/18** 在 fbcon 探测/映射处；
  **19** 在 `serial_init()` 返回之后；19 一出现、fbcon 已注册，就把整个屏幕交给
  fbcon（同一物理帧上的两套文字栅格继续互画只会互相覆盖）。
- **F 的蓝底**是“内核 fbcon 真的接管了屏幕”的照相级信号；黑底继续滚字说明还在用早期打点。

## 4. 文字转写模板

逐项照抄，未知写 `?`，不要省略 0x 前缀和大小写。

```text
[A] UEFI 菜单选项：
[B] DarwinBoot 最后 12 行（含底部绿条上方）：
    video    pa 0x________________  ____x____  row ____ bytes  __ bpp
    entry    pa 0x________________
    entry words ________________ ________________ ________________ ________________
    CurrentEL _  SCTLR_EL1 0x________  TCR_EL1 0x________________
    ID_AA64MMFR0_EL1 0x________
    ID_AA64PFR0_EL1  0x________
    其他行：____________________________________________
[C] 左下角白色/绿色小方块：有 / 无
[D] 顶部 EARLY 0 整行原文（应为一行，含 w=/h=/row=）：________________
    是否出现 "BAD"：是 / 否（若是，再抄下一行 raw pa=/w=/h=/row=）
    ______________________________________
[E] 底部色块点亮到第几格（0..19，每格 48 px）：____
    每个 EARLY 行原文：
    ______________________________________
    ______________________________________
    是否出现 "fb outside physmap"：是 / 否
[F] 背景色：黑 / 深蓝 / 其他____
    cepheus fbcon ready 行原文：__________________________________
[G] 其余可见文字（尽量多抄）：
    ______________________________________
    ______________________________________
```

## 5. 判读表

| 观察 | 结论 | 下一步 |
|---|---|---|
| A 都进不去 | 问题在 UEFI 镜像/按键 | 换镜像，查 UEFI CI 日志 |
| 有 B，底部无 C、无 D | 内核入口未执行 | 对比 `entry pa` 与内核实际 load address；查交接参数 |
| 有 C，无 D，无其它 | 执行了内核第一条指令，但 `arm_init()` 未到 | 查异常向量/栈/重定位 |
| 有 D 且带 `BAD` | `boot_args->Video` 不可用，已退回 `0x9c000000` | 把 `raw pa` / `w` / `h` / `row` 记录下来 |
| 有 D，`pa` 与 B 的 `video pa` 不同 | 交接的 Video 与 UEFI 打印的不一致 | 记录两个 pa，作为下一版默认值 |
| 有 D，停在 EARLY n | 卡在第 n 个检查点之后 | 记 n，查该检查点对应函数 |
| 停在 EARLY 8，且标签是 `fb outside physmap` | 交接 framebuffer 不在 RAM 窗口内，早期控制台已关闭 | 记录 `EARLY 0` 的 `pa`，改用别的映射方案 |
| 停在 EARLY 8，标签是 `leaving bootstrap TTBR0` | 切到 physmap 别名时挂了 | 记录 0..8，重点查 physmap 覆盖范围 |
| 停在 EARLY 10..14 | `arm_vm_init` 内某段挂了 | 记 n：10 关 TTBR0、12/13 pmap_bootstrap、14 I/O 页表 |
| 停在 EARLY 15/16 | `arm_vm_init` 已返回，卡在 `serial_init()` 入口或内部 | 对照 17/18 判断是否进到 fbcon 探测 |
| 停在 EARLY 17/18 | fbcon 配置读了、`ml_io_map_wcomb` 没返回或注册失败 | 记录它的 pa 与 ADT 值 |
| 出现 EARLY 19 且有蓝屏 | `serial_init()` 已返回并交给 fbcon | 继续看后续 kprintf |
| 出现 `CEPHEUS EARLY PANIC:` | 直接读 panic 文本 | 按文本修 |
| 出现 F 蓝屏 | `serial_init()` 成功，fbcon 接管 | 继续看后续 kprintf |
| 蓝屏后停在 `launchd` 相关行 | Stage 6（无 root 卷镜像）预期行为 | 需要 iOS 16.x root 卷 |

## 6. 失败时保留的产物

- `fastboot boot` 之后的完整屏幕视频（最有用）。
- 若 UEFI 有串口/日志到 `/efi` 的选项，一并带上。
- 本次启动用的 `Mu-cepheus-unixnu.img` 的 CI run id 与 `cust-payload.img` 的
  `SHA256SUMS`，确保复现的是同一份产物。
