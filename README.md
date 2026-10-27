# UniXNU on Xiaomi Mi 9 (cepheus / SM8150)

在 **小米 9（cepheus，骁龙 855）** 上通过 UEFI 启动 **苹果 XNU 内核** 的设备仓库。

> **状态：骨架 + CI 产物阶段。** 本仓库从 [Lux12138/unixnu-nabu](https://github.com/Lux12138/unixnu-nabu)（小米平板 5，同 SM8150，内核已走到 `execve("/sbin/launchd")`）改造而来。DRAM 与 userdata 已在真机实测；fbcon 地址、面板/触摸仍以 `TODO_MEASURE` 标注，开始实测前请读 `TODO-MEASURE.md` 与 `STATUS.md`。

## 两条内核线 / 产物

| 线 | 内核 | 产物 |
|---|---|---|
| `build-kernel.yml` | xnu-10063（iOS 17 世代，配 iPadOS 17.7.11） | kernel + payload + userdata + `cust-payload.img` |
| `build-kernel-8796.yml` | xnu-8796（iOS 16 世代，配 iPhone X 身份/显示） | `kernel.development.cepheus` + `kernel.macho.adt` + `cust-payload.img`（`xnu-8796-kernel.zip`） |

## 启动链

```
Android boot image → BootShim → Mu-Silicium UEFI → DarwinBoot → XNU
```

## 拿最新 8796 产物

每次 `build-kernel-8796.yml` 成功都会建一个 release，标签就是 run id：

```bash
gh release list                       # 或看 Actions 页面最后一次成功的 run
gh release download k8796-<run_id> -D out
# 公开直链（无需 token）：
#   https://github.com/sxl47/UniXNU-cepheus/releases/download/k8796-<run_id>/cust-payload.img
```

`xnu-8796-kernel.zip` 与 Actions artifact 同布局（`out/` + `dxb/build.log`），
解压后可以用 `sha256sum -c SHA256SUMS` 校验。最近一次全绿：
run `40449958126`（commit `0b65004`）。

## 仓库关系

| 仓库 | 作用 |
|---|---|
| 本仓库 `UniXNU-cepheus` | 设备描述：board.toml / defconfig / kit / payload 脚本 / CI |
| `Lux12138/UniXNU`（fork） | UniXNU 构建+驱动 fork，**内含 `scripts/make-nabu-adt.py`（ADT 生成器底本）**，CI 里 clone |
| `penYo22` 已消失的 raphael 仓库 | SM8150 实测情报已存档于工作区 `notes/raphael-intel.md` |

## 需要实测的值（全部标 TODO_MEASURE）

1. ~~DRAM 容量与 base~~（已实测 2026-10-24：6GB 变体，`dram_size = 0x180000000`）
2. ~~userdata 分区 first_lba / last_lba~~（已实测：`0x7C000`–`0x1C47FFA`，4K LBA）
3. ~~面板 framebuffer 地址~~（设备树已确认：`cont_splash_region@9c000000`，
   `reg = <0x9c000000 0x2400000>`，1080×2340，stride 4320；运行期内核优先用
   `boot_args->Video`，ADT 值只作回退）
4. OS 卷 vol_uuid（换 IPSW 后从 dmg 读）
5. 面板/触摸驱动适配（小米 9：Samsung s6e3fc2x01 面板、触控 IC 待查）

## 一次启动能看到什么（诊断链）

从早到晚共七层信号，看到第 N 层就说明前 N 层都成功了：

| # | 画面 | 说明 |
|---|---|---|
| A | UEFI 菜单 | 固件正常 |
| B | DarwinBoot 日志 + **底部**绿条 | 交接桩执行；`video pa` / `entry pa` 不再被绿条遮住 |
| C | 左下角 64×32 白/绿小方块 | `start.s` 第一条指令执行（无栈无页表；直接读 `boot_args->Video`，无效才退回 `0x9c000000`） |
| D | `CEPHEUS EARLY 0: video pa=0x... w=1080 h=2340 row=4320`（一行） | `arm_init()` 已进入，C 侧打点接管同一块屏幕 |
| E | 底部 21 格 48 px 色块 + `CEPHEUS EARLY 0..20` | 内核逐段推进，停在第几格就是卡在哪个检查点；8/9 之间是 TTBR0 → physmap 的切换 |
| F | 深蓝底 + `cepheus fbcon ready: pa=0x...` | `serial_init()` 注册 framebuffer 控制台成功 |
| G | 蓝底内核日志/panic | 后续输出可见 |

真机操作与文字转写模板见 [`docs/device-capture-checklist.md`](docs/device-capture-checklist.md)。
CI 现在会断言 `0003` / `0004` / `0006` / `0010` / `0010z` / `0012` / `0028` 七个关键补丁
**确实被应用**，不会再出现“补丁静默跳过 → 屏幕全黑”的假象。

## 刷机（拿到产物之后，安全边界）

```bash
fastboot flash cust cust-payload.img   # 唯一写操作：cust 分区（格式化不影响安卓系统）
# 另外需要一个含 UEFI/DarwinBoot 的 boot 镜像（uefi-cepheus，仍在搭建）：
fastboot boot <uefi-darwinboot>.img    # 临时引导，不写盘，不碰 abl/xbl/bootloader
```

`cust-payload.img`（64 MiB FAT16）里已包含 `Payloads/kernel.macho`、
`Payloads/kernel.macho.adt`、空 ramdisk 占位和 `EFI/UniXNU/unixnu.toml`；
DarwinBoot 只挂 FAT 卷，所以内核和 ADT 必须放在这个镜像里。

卡死长按电源 10 秒强制重启回安卓。劣质 USB 线会导致 96MB 镜像传输报 `Load Error`。

## 已知坑（SM8150 通用，来自 nabu/raphael 实测）

- ramdisk 可用区间 32–64MB；boot 头 `header_version=1`、`page_size=2048`
- FVMAIN 上限 8–10MB → 内核走 cust 分区存储，不进固件卷
- DarwinBoot 必须在 `APRIORI.inc` 第一个 DXE 块
- ADT 不带 RAMDisk 占位符，除非真的提供 initrd
- `build-libpthread-kernel.py` 必须在 archives 里，否则 pthread panic
- "日志停止"≠"内核停止"：用 `boot-progress=2` 看检查点

## 历史文档

nabu 的原始工作笔记（FLOW/HANDOVER/PLAN 等）保存在 `docs/nabu-reference/`，是理解 SM8150 移植全貌的第一手资料。
