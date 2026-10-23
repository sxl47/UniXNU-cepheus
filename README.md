# UniXNU on Xiaomi Mi 9 (cepheus / SM8150)

在 **小米 9（cepheus，骁龙 855）** 上通过 UEFI 启动 **苹果 XNU 内核** 的设备仓库。

> **状态：骨架阶段。** 本仓库从 [Lux12138/unixnu-nabu](https://github.com/Lux12138/unixnu-nabu)（小米平板 5，同 SM8150，内核已走到 `execve("/sbin/launchd")`）改造而来，所有需真机实测的值均以 `TODO_MEASURE` 标注。开始实测前请读 `TODO-MEASURE.md`。

## 启动链

```
Android boot image → BootShim → Mu-Silicium UEFI → DarwinBoot → XNU
```

## 仓库关系

| 仓库 | 作用 |
|---|---|
| 本仓库 `UniXNU-cepheus` | 设备描述：board.toml / defconfig / kit / payload 脚本 / CI |
| `Lux12138/UniXNU`（fork） | UniXNU 构建+驱动 fork，**内含 `scripts/make-nabu-adt.py`（ADT 生成器底本）**，CI 里 clone |
| `penYo22` 已消失的 raphael 仓库 | SM8150 实测情报已存档于工作区 `notes/raphael-intel.md` |

## 需要实测的值（全部标 TODO_MEASURE）

1. DRAM 容量与 base（`/proc/meminfo`，6GB/8GB 版本不同）
2. userdata 分区 first_lba / last_lba（TWRP sysfs + fastboot 交叉验证）
3. 面板 framebuffer 地址（fbcon 节点 reg，从设备树读）
4. OS 卷 vol_uuid（换 IPSW 后从 dmg 读）
5. 面板/触摸驱动适配（小米 9：Samsung s6e3fc2x01 面板、触控 IC 待查）

## 刷机（拿到产物之后，安全边界）

```bash
fastboot flash cust cust-payload.img   # 唯一写操作：cust 分区（格式化不影响安卓系统）
fastboot boot cepheus-xnu.img          # 临时引导，不写盘，不碰 abl/xbl/bootloader
```

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
