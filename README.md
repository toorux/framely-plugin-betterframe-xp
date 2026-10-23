# BetterFrame XP for Framely

将 [omuomu0909/betterframe-xp](https://github.com/omuomu0909/betterframe-xp)
移植为 Steam Frame 的 Framely 插件。插件 ID：`tooru.betterframe-xp`。
当前版本：`0.1.0-preview.3`。本移植由 AI 编写，头显上的最终画质和兼容性待验收。

原生渲染核心固定到上游 **0.1.2 / 1e5bab4afe07835b559431e6b57671b5e080807e**。
保留 CAS、中心权重、去色带、颗粒、纹理权重与串流检测；独立 OpenVR 面板改为
Framely 设置页。支持 **中文 / 日本語 / English**，默认跟随 Framely，可手动选择并保存。

## 安装与使用

需要 ARM64 Steam Frame、Python 3 和支持插件 API v1 的 Framely。本插件不声明额外宿主版本范围。
已在 Framely 0.8.3 上验证加载与实时控制；打包 CLI 固定版本与运行时最低版本分别管理。
旧版 `preview.2` 的 `>=0.8.3` 声明会按 SemVer 排除 `0.8.4-preview.1` 等预览版，
`preview.3` 已移除此不必要限制；商店刷新后选择新插件版本，无需降级 Framely。
后端使用 `steamos` 用户，无需 root。安装后默认关闭画面处理。

1. 将 `dist/tooru.betterframe-xp-0.1.0-preview.3.framely` 安装到 Framely。
2. 如果装过原版 BetterFrame XP，先用原版的 `betterframectl off` 和
   `betterframectl disable` 停用，再在方便时重启 SteamVR。本插件检测到原版仍加载或启用时拒绝叠加处理。
3. 打开插件，选择语言，启用“画面处理”。**首次启用需要下一次启动 SteamVR 才能加载渲染层**；插件不会自行重启 SteamVR。
4. 显示“渲染层已加载”后，使用锐化、预设或“处理前后对比”。参数约 250 ms 内反映，后续调节无需重启。
5. 建议关闭 PC 端 SteamVR 编码前的 `useSharpening`，避免重复锐化。

关闭设置页后处理继续运行。关闭页面与停用插件是不同操作。可以从快捷页面打开完整设置窗口。

## 保留与调整

| 项目 | Framely 版行为 |
| --- | --- |
| CAS / 中心权重 / 五点或九点采样 / 亮度或 RGB 锐化 | 保留上游算法与范围 |
| 左右对比、仅 PC 串流、并排双眼、跳过四角 | 保留，可实时调整 |
| 去色带、纹理增强权重、动态颗粒 | 保留并标为实验功能 |
| 预设 | 柔和、均衡、强烈；应用时关闭实验效果并恢复轻量 CAS |
| 原版配置 | 手动导入 `~/.config/betterframe-xp/params.conf` 的画质值，不导入启用状态和语言 |
| SteamVR 眼动相关补偿 | 按需读取；点击时才修改，修改前备份原值 |
| 性能 | 显示渲染层 GPU/CPU 耗时、合成器帧率与帧间隔 p99 |
| 更新 | 交给 Framely；不运行原版安装器、面板服务或 GitHub 自更新 |
| 崩溃保护 | 连续两次 10 秒内的 SteamVR 启动失败会移走插件自己的启用环境文件 |
| 日志 | 默认仅警告；逐帧 trace 默认关闭，保留每秒性能统计 |

“仅 PC 串流”按 YCbCr 视频纹理的绘制记录判定是否启用效果；处理对象仍是整张最终合成图像，
因此串流上方的 UI 也会受到处理。中心权重固定在每只眼图像中心，不跟随眼动。
本工具增强已有边缘对比度，不是超分辨率，也不能重建压缩丢失的细节。

## 停用、更新与卸载

- 关闭“启用画面处理”：立即将已加载的渲染层设为旁路，同时移除下次启动的插件配置。
  已映射的动态库要到 SteamVR 退出后才卸载；旁路仍存在一次图像复制的开销。
- 停用 Framely 插件、异常清理：将参数设为旁路，只移除本插件的 drop-in、环境文件与 Vulkan 清单。
  保留已保存的偏好，重新启用插件时恢复。OS 正在关机时保留下一次启动的配置。
- 关闭 Framely 页面不会停用处理；这与原版“关闭独立面板就停用效果”的行为不同。
- 更新采用原子替换。运行中的合成器继续映射旧库，界面通过 `/proc/<pid>/maps` 的 `(deleted)`
  提示重启。相同库不重复替换。更新后需下一次 SteamVR 启动加载新版本。
- 启动保护触发后不自动重试加载，需排除原因后手动重新启用。
- 如果修改过“SteamVR”页中的补偿开关，先点“恢复原始 SteamVR 设置”，或在 SteamVR 运行时卸载。
  卸载钩子会恢复原值；运行时不可用时钩子返回失败并保留备份，Framely 可在启动 SteamVR 后重试卸载。
  普通停用和崩溃清理不会改写这些独立、持久的 SteamVR 设置。

## 存储位置

| 位置 | 用途 |
| --- | --- |
| `$FRAMELY_DATA_DIR/settings.json` | 用户偏好，由 Framely 提供的用户数据目录保存 |
| `~/.local/share/framely/betterframe-xp/` | 稳定位置的动态库、实时参数、启动保护与补偿设置备份 |
| `~/.config/systemd/user/steamvr.service.d/92-framely-betterframe-xp.conf` | 插件自己的用户级 drop-in |
| `~/.local/share/vulkan/implicit_layer.d/framely-betterframe-xp.json` | 插件自己的 Vulkan implicit layer |
| `$XDG_RUNTIME_DIR/framely-betterframe-xp/` | 带合成器 PID 的性能数据、日志与启动计数 |

安装到 payload 的动态库先复制到稳定的用户目录，避免 Framely 升级或移除 payload 时使 Vulkan 清单失效。
卸载后保留一份中性 `params.conf`，供仍映射在合成器内的库读取；它没有启动配置，也不会自行运行。
本插件不修改 SteamVR 二进制、不使用 `LD_PRELOAD`，不启动或重启 SteamVR。

## 已知限制

- 原项目报告在 72/80 Hz 下启用锐化可能周期性卡顿，建议尝试 120/144 Hz 或锐化强度 0。
  原版效果验证限于作者的一台设备；本移植没有完成头显实机验收。
- 调整去色带可能导致画面异常，发生时设回 0。原算法及此已知问题均保留，不把它标为稳定功能。
- 额外的 GPU 处理和图像复制会增加耗电；关闭效果不等于卸载渲染层。
- `streamOnly` 继承上游的启发式检测，不覆盖 push descriptors、descriptor update templates 等未跟踪路径。
- 保留上游共享 coherent uniform buffer 更新方式；它没有为每个在途帧单独分配参数缓冲，
  同步和眼内视觉稳定性仍须在目标 Turnip/Adreno 驱动上验证。
- 当前构建产物为 Linux ARM64，动态链接 glibc / libstdc++。本机产物最低导入版本为
  `GLIBC_2.38`、`GLIBCXX_3.4.32`；目标 SteamOS 需提供对应符号，或在目标系统重编译。

## 构建与校验

Linux ARM64 构建依赖：C++20 编译器、Python 3、Node.js 22+、Vulkan 头文件、`glslangValidator`。
打包需要 Framely CLI。Debian/Ubuntu 可安装 `g++ libvulkan-dev glslang-tools`。

```sh
npm ci
npm run typecheck
npm test
npm run build
npm run test:ui       # 需要 google-chrome，可通过 CHROME 指定
npm run test:vulkan   # 需要 libvulkan 和支持 headless surface 的驱动；优先使用 lavapipe
FRAMELY_CLI=/path/to/framely npm run pack
```

可以通过 `CXX`、`VULKAN_HEADERS`（含 vulkan/ 的 include 目录）和 `GLSLANG_VALIDATOR` 指定本地工具。
`npm run build:ui` 只更新页面、后端、许可和源码归档，不重新编译已存在的原生库。
`npm run dev` 在本机打开模拟预览，不连接 SteamVR，也不修改系统配置。

`scripts/native.py` 在 `build/native` 生成隔离命名的构建副本；`vendor/upstream` 保持原始内容。
构建不会安装 Vulkan 清单。打包会校验 ARM64 ELF 和完整载荷集合，再调用 Framely 自身的 pack/verify。
输出包、`SHA256SUMS` 和校验结果放在 `dist/`；具体测试记录见 [VALIDATION.md](VALIDATION.md)。

## GitHub Actions 与 topic 自动发现

发布不依赖 database、submodule 登记或 `DATABASE_TOKEN`。遵循 Framely 最新的
[GitHub 插件发现规范](https://github.com/SteamFramelyHomebrew/framely/blob/main/docs/github-plugin-discovery.md)：

1. 仓库保持公开、非 fork、未归档，并在 GitHub 仓库 About → Topics 添加 **`framely-plugin`**。
2. `.github/workflows/release.yml` 仅在推送 `v*` 版本标签时构建 ARM64 插件，执行类型检查、后端和三语测试、
   实际 headless Vulkan 渲染测试，上传 Actions 构建产物并创建 Release。分支推送和 PR 不触发构建。
3. 发布时同步 `manifest.json`、`package.json` 和 `package-lock.json` 的版本，提交后推送同名 `v<version>` 标签：

   ```sh
   git push origin main
   git tag v0.1.0-preview.3
   git push origin v0.1.0-preview.3
   ```

4. tag 必须与清单版本完全一致。预览版本自动设置 GitHub prerelease；正式版本正常发布。
5. CI 从 `scripts/framely-toolchain.json` 固定的官方源码提交构建 CLI，生成包含固定版本 `downloadUrl` 的临时清单，
   打包并校验最终 `.framely`。源码清单不手写整包哈希或下载地址。
6. 使用官方 `framely release-json` 从最终包生成 `release.json`，导出包内图标，并检查 ID、版本、
   `runAs`、Framely 版本要求、整包字节数和 SHA256。之后不再修改安装包。
7. 发行目录 `dist/release/` 包含 `.framely`、`release.json`、导出图标和 `SHA256SUMS`，全部上传到同一个 Release。
   先建立带完整附件的草稿，再发布；同 tag 的现存 Release 不覆盖。失败的草稿也需人工检查，不自动删除。

仅使用仓库内置 `GITHUB_TOKEN`；build 任务只读，release 任务才授予 `contents: write`。
首次设置 topic 需要仓库维护权限，工作流不会申请管理员 token。更新 Framely 打包工具时，审查官方发现规范后
更新 `scripts/framely-toolchain.json` 的固定提交；无需下载完整 CEF 或在 CI 启动 SteamVR。

本地生成相同的发现附件：先运行构建和打包，再指定支持 `release-json` 的新版 CLI：

```sh
FRAMELY_CLI=/path/to/new/framely npm run release:assets
```

发行目录必须为空，每个 ID 只放一个最终包。Framely 自动发现读取的是 **Release 附件** `release.json`，
不是默认分支里的文件；只有推送源码、没有公开 Release 时，插件还不会出现在发现列表中。

## 许可与源码

包含 Framely SDK 的设置界面按 **AGPL-3.0-only** 分发。独立编写的集成源码另提供
`LICENSE.integration` 中的 MIT 条款；BetterFrame XP、vkBasalt、CAS、deband 和 React
保留各自许可。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
每个插件包包含对应的 `source.zip`，内含完整集成源码、固定版本的上游渲染核心、SDK、
依赖锁文件、构建脚本与测试；不包含 node_modules 或本机缓存。
