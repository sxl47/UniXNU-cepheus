# TODO-MEASURE：小米 9 真机实测清单

> 以下每一项都有对应的 board.toml / 脚本落点。实测工具：TWRP（或任意可进系统的恢复环境）+ fastboot + 小米 9 解锁 BL。
> 平台级参考值（可直接沿用 raphael/nabu 的）与必须实测的值已区分。

## 1. DRAM（→ board.toml `[payload.adt]` dram_size）

```bash
# TWRP shell:
cat /proc/meminfo | head -3        # 记 MemTotal
```
- 6GB 版：MemTotal ≈ 5.6–5.8×10^6 kB → 起步 `dram_size = 0x180000000`
- 8GB 版：MemTotal ≈ 7.6–7.8×10^6 kB → 起步 `dram_size = 0x200000000`
- 校准方法见 nabu STATUS.md：MemTotal + 预留（modem/hyp/rmtfs 约 816MB）≈ 物理容量
- base 固定 `0x80000000`（SM8150 通用）

## 2. userdata 分区（→ board.toml `[userdata]` first_lba/last_lba）

```bash
# TWRP shell（先确认 userdata 是 sda 几号分区）:
ls -l /dev/block/by-name/userdata
cat /sys/block/sda/sdaXX/start     # 512B 扇区
cat /sys/block/sda/sdaXX/size
```
换算：`first_lba = start / 8`，`last_lba = first_lba + size/8 - 1`（UFS LBA=4096B）
交叉验证：`fastboot partition-size:userdata`（字节数应 = (last-first+1)*4096）

## 3. 面板 framebuffer 地址（→ make-cepheus-adt.py 的 fbcon 节点 reg）

```bash
# TWRP shell:
cat /proc/device-tree/soc/qcom,mdss-sspp@0/... # 或直接
dmesg | grep -i "mdss\|framebuffer\|s6e3fc"
```
小米 9 面板：Samsung s6e3fc2x01，1080×2340。需要从cepheus 设备树找 MDSS/framebuffer 的物理地址和长度（nabu 是 `reg=<0x9C000000 0xC00000>`，cephues 不同）。
设备树提取方法照抄 nabu `docs/nabu-dts-extract.md`（针对 boot.img 里的 dtb）。

## 4. OS 卷 UUID（→ board.toml root_match_volume_uuid）

```bash
# 电脑上，对 IPSW 解出的 OS dmg:
7z l -slt 044-76040-038.dmg | grep vol_uuid
```
沿用 nabu 同款 IPSW 的话，可以直接先用 nabu 的值 `04769d26-2ca0-4825-b443-e2e5f88300f2`。

## 5. ADT 生成器（✅ 已完成：scripts/make-cepheus-adt.py）

- 已基于 Lux12138/UniXNU fork 的 make-nabu-adt.py 改造完成，并新增 `/cepheus-fbcon` 节点（补丁 0003 消费：reg=<物理地址 大小> + width/height/stride）
- **仍需实测**：fbcon 的 reg/size（§3 实测后用 `--fbcon-reg/--fbcon-size` 传入或改脚本默认值，当前是 nabu 占位值 0x9C000000/0xC00000）

## 6. CI 里的 fork 地址

`.github/workflows/build-kernel.yml` 目前 clone 的是 `Lux12138/UniXNU`。起步阶段可以直接用（SM8150 内核工作都在里面）；长期建议 fork 一份 `UniXNU` 改为自己的远端，并在里面加 `make-cepheus-adt.py`。

## 7. 内核补丁中的设备级内容（后期任务，不阻塞构建）

`xnu-8796/patches/` 里 83 个补丁是 nabu 的 SM8150 内核工作积累，文件名保持原样。cephues 需要动的内容（实测后再改）：
- `0004-nabu-machine-config.patch`：平台地址/DRAM 相关
- `0010-nabu-early-framebuffer-debug.patch`：fbcon 地址
- `0060~0063`（触摸驱动）：小米 9 触控 IC 与 nabu（NT36672?）不同，需要按 cepheus 设备树改
- `0061-nabu-iphone-x-display-size.patch`：分辨率适配
- UFS/USB/PMIC 大概率通用，先不动

## 6. 来自 nabu fork 最新实战的结论（2026-10-24）

- nabu 当前的卡点是 execve 后 panic，已定位：ADT 缺 maxmem（owned memory 上限）导致
  vm 页计数虚大 116 倍（freepg=91,199,444 页 ≈ 373GB），页分配必炸。
  修复 = ADT 注入 maxmem=4864（等于 owned_memory_size）。
  → **对 cepheus 的含义：实测出 dram_size / owned_memory_size 后，
  maxmem 必须等于 owned_memory_size（6GB 机约 6144 减保留区，以实测为准）。**
  CI 克隆的是 fork 最新代码，该修复已包含；本地 repos/UniXNU-nabu-fork 落后了，
  需要时 `git -C repos/UniXNU-nabu-fork pull` 同步。
- fork 全靠本地 WSL 构建，其 CI workflow 在新 runner 镜像上没有维护——
  我们踩的 hostcompat 坑是首发，修法见 build-kernel.yml 的 HOST_COMPAT_CFLAGS 注释。
