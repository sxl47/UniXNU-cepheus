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
| C0 | 底部绿条上被挖出一块 **280×200 的黑色缺口**（约占屏宽 1/4、高 200 px） | stage 0 的**黑底铺垫**：后面前有所有色带都画在这块黑底上。看到它就说明 stage 0 已经走到画白块之前 | `boot_args->Video`，无效才退回 `0x9c000000` |
| C | 黑底**最下沿**一块 64×32 像素白色小方块 | 内核入口第一条指令执行了（`start.s`，无栈无页表） | 同上 |
| C1–C4 | 白色方块**正上方**依次冒出的 4 条 64×8 色带：红 / 绿 / 蓝 / 品红 | 汇编检查点 A–D，把「白块 → 跳进 C」之间切成 5 段；最下面出现到哪一条，就是死在那一条**之后** | 四条都读 `boot_args->Video`（`rowBytes` / `height` 也取自 Video） |
| C5 | 黑底上、隔开一段空白之后的两块**大方块**：下面 **160×24 纯白**、上面 **200×24 纯黄** | `arm_init()` 入口的裸写测试（不经过 `cepheus_early.c`）。白块＝硬编码 `0x90000000/4320/2340` 能写；黄块＝`args->Video` 能解引用 | 白块为常量，黄块取自 `args->Video` |
| D | 顶部一行 `CEPHEUS EARLY 0: video pa=0x... w=1080 h=2340 row=4320` | `arm_init()` 已进入；左下角色块前 48 px 变绿，C 侧打点接管同一屏幕 | `boot_args->Video` |
| E | 底部 20 个 48 px 宽色块（stage 0..19），伴随 `CEPHEUS EARLY 0..19: <label>` | 内核逐段推进；停在第几格就是卡在第几个检查点之后 | 前 8 格 `boot_args->Video`，8 之后为同一物理帧的 physmap 别名 |
| F | 整屏**深蓝底** + `cepheus fbcon ready: pa=0x... WxH row N` | `serial_init()` 走到 framebuffer 控制台注册，之后的 kprintf 都可见 | `PE_state.video`，回退 ADT |
| G | 蓝底上的内核日志/panic 文本 | 正常启动或明确 panic | 同上 |

### 关键点

- **C1–C4 的判读**：四条色带从下往上的顺序就是执行顺序
  白（stage 0）→ 红（A）→ 绿（B）→ 蓝（C）→ 品红（D）。
  - 只有白色：死在 stage 0 之内（`boot_args->Video` 读到的地址不可写，或越界）。
  - 红出现、绿不出现：死在 `create_bootstrap_mapping` 之后、
    `b common_start` 之前，即建页表这一段。
  - 绿出现、蓝不出现：死在 `common_start` 里，MMU 打开之前
    （TCR/TTBR/MAIR/VBAR 任一处）。
  - 蓝出现、品红不出现：MMU 已经打开，死在 `MSR_SCTLR_EL1_X0`
    之后到 `ret` 之间（TPIDR/CPACR 或 physmap 访问）。
  - 四条全出现、但没有 D 行的 `CEPHEUS EARLY 0`：汇编段全通，
    问题在 `arm_init()` 入口或 C 侧打点本身（先怀疑字符绘制用它自己
    解析的 depth，而不是 stage 0 硬编码的 32bpp）。
  - 色带**宽度只有预期的一半**或颜色整体偏（红蓝互换）⇒ 通道顺序是
    BGRA 而非 ARGB；颜色名以实际照片为准，位置顺序不变。
  - **C/D 必须也读 `boot_args->Video`**：它们在 MMU 打开之后写，走的是 V=P
    identity 映射；如果只给设备树的 `0x9c000000` 建 NC block，而交接的
    framebuffer 在 `0x90000000`（真机实测值），C/D 会写进另一块 RAM 的
    write-back 缓存，屏幕上什么都不出现。这是 2026-10-30 之前蓝/品红时有时无
    （要等 cache 被自然换出才看得到）的原因。

  - **C5 判读**（两块大方块在黑底上方，与下面四条色带之间隔着一段纯黑）：
    - 白 + 黄都有 ⇒ 进了 `arm_init()`，`args` 也可用 ⇒ 黑屏的原因在
      `cepheus_early_video()` / `cepheus_early_mark()` 内部，不在入口。
    - 只有白 ⇒ 进了 `arm_init()`，但 `args->Video` 解引用就挂 ⇒ 交接的 boot_args
      指针不可用，回头查 `x0`。
    - 两块都没有（只有黑底 + 四条色带）⇒ `start.s` 的 `ret` 没落到 `arm_init()`
      ⇒ 查 `lr` 的值与 KVA 映射。
  - **为什么要黑底**：真机上 UEFI 在屏幕底部留了一条**通栏绿条**，早先那版
    青色/淡黄 64×8 色带正好压在这条绿条上，"绿底画青"肉眼和照片都分不出来，
    一度被误判成"标记没出现"。现在 stage 0 先铺一块 280×200 的纯黑，范围覆盖
    C0 到 C5 全部标记，色带一律黑底。绿条上那块黑色缺口本身就是 C0 信号。
  - 黑底与色带都是**纯色块**，不画字符，所以不受 depth/通道顺序影响；
    颜色名只作辅助，判读以**位置和块宽**为准。

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
- **色块颜色只有绿→黄**：C 侧第 n 格是 `0xff00ff00 | ((n & 7) * 32 << 16)`，即绿到黄；
  `start.s` 的白块是纯白，检查点固定为红/绿/蓝/品红。除此之外的纯红/纯蓝/粉色
  一定来自开机图 / UEFI logo 残留，不要当成进度信号。

### 实测备忘：2026-10-30 的“内核全黑”

那一版屏幕上有 B 的绿条、有 C 的白块，但 D/E 一个字都没有。原因是 UEFI 交接的
`video pa` 是 `0x90000000`（不是设备树的 `0x9c000000`），而它落在 RAM 的 V=P identity
映射里，属性是 Normal **write-back**；早期控制台只给 `0x9c000000` 建了 NC block，于是
所有 C 侧打点（以及 MMU 打开后的检查点 C/D）都停在 cache 里，显示控制器扫 DRAM 什么也
看不到。修复是 `0010z`（NC block 和检查点 C/D 都跟着 `boot_args->Video`）+ `0012`
（打点后无条件 `dc cvac`）。**看到白块却没有 D 行，且 `video pa` 不是 `0x9c000000`，
就是这一类问题。**

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
| 有白块和红/绿，但没有蓝/品红，也没有 D | MMU 打开后的写入落在 write-back 缓存里 | 确认 release 含 `0010z`+`0012`；对比 B 的 `video pa` 与 `0x9c000000` |
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
