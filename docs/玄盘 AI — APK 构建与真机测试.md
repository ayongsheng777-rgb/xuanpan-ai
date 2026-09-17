# 玄盘 AI — APK 构建与真机测试

> 版本：2026-09-17
> 对应脚本：`apps/mobile/scripts/build-apk.sh`
> 对应产物：`apps/mobile/android/app/build/outputs/apk/release/app-release.apk`

---

## 一、这次要解决什么

移动端此前只验证到 `expo export`（Metro 打出 3.24MB 的 `.hbc` 包），**从未产出过可安装的 APK**。
本轮目标：打通本机（Windows + 中文路径）从源码到**真机可安装 APK** 的完整链路。

卡点不在业务代码，而在**本机 C++ 工具链环境**——`clang` 与 `ld.lld` 在这台机器上
**100% 无法写出任何目标文件**。定位这个根因花了十几轮实验，过程记录在本文件第三节。

---

## 二、安装与真机测试

### 2.0 本次构建产物（已实测）

```
BUILD SUCCESSFUL in 49m 5s
661 actionable tasks: 328 executed, 333 up-to-date
```

| 项 | 值 |
|---|---|
| 文件 | `dist/玄盘AI-v0.1.0-release.apk` |
| 大小 | 94.0 MB（98,517,157 字节） |
| SHA-256 | `41a3a29404836b746d0c053a49453cb5fadb5e3e78c03a271c6463071b7075a9` |
| 包名 / 版本 | `com.xuanpan.ai` / versionName `0.1.0` (versionCode 1) |
| 应用名 | 玄盘 AI |
| minSdk / targetSdk | 24 (Android 7.0) / 34 |
| 含 ABI | arm64-v8a(17)、armeabi-v7a(15)、x86(15)、x86_64(15)，共 62 个 `.so` |
| JS 引擎 | Hermes 字节码（`assets/index.android.bundle`，1.95 MB，magic `c61fbc03`） |
| 内嵌后端 | `http://192.168.57.10:8360`（bundle 内可 grep 到） |
| 明文 HTTP | `usesCleartextTraffic=true` ✅ |
| 签名 | APK Signature Scheme **v2**，证书 `CN=Android Debug`（debug keystore） |
| 权限 | CAMERA、INTERNET、ACCESS_NETWORK_STATE、READ_MEDIA_IMAGES、VIBRATE 等 |

安装前自检（可选，确认传输未损坏）：

```bash
# [Windows / Git Bash]
sha256sum "D:/WorkBuddy/玄盘AI/dist/玄盘AI-v0.1.0-release.apk"
# 应输出 41a3a29404836b746d0c053a49453cb5fadb5e3e78c03a271c6463071b7075a9
```

### 2.1 安装

把 `app-release.apk` 传到手机安装即可（Expo 模板的 release 默认用 debug 签名，可直接装）。

```bash
# [Windows / Git Bash] 用 ADB 安装
adb install -r "D:/WorkBuddy/玄盘AI/dist/玄盘AI-v0.1.0-release.apk"
```

或直接把 APK 拷进手机，用文件管理器点开安装（需允许「安装未知来源应用」）。

> 若手机已装过同包名旧版且签名不同，先卸载：`adb uninstall com.xuanpan.ai`。

### 2.2 测试前必须确认的三件事

APK 里的**后端地址是编译期内联的字面量**，不是运行时读取的——所以下面三条任何一条不满足，
APP 打开后会直接报网络失败：

| # | 条件 | 怎么确认 |
|---|------|----------|
| 1 | **手机与后端在同一局域网** | 手机连的 Wi-Fi 要能访问 `192.168.57.10` |
| 2 | **后端容器在 8360 监听** | 手机浏览器打开 `http://192.168.57.10:8360/healthz`，应返回 200 |
| 3 | **Windows 防火墙放行 8360 入站** | 本轮已配置（规则名 `Xuanpan API 8360`，入站/TCP 8360/域+专用+公用/仅本地子网）；若换网络配置文件需重新放行 |

> 想换后端地址，不要改源码，用构建参数覆盖：
> ```bash
> API_BASE_URL=http://192.168.1.20:8360 bash apps/mobile/scripts/build-apk.sh
> ```

### 2.2.1 ⚠️ 多网段陷阱：本机有三个局域网 IP

构建机有三块**真实物理网卡**，分属三个不同网段，**全部**都能访问后端：

| 适配器 | IP | 网关 | 默认路由 metric |
|---|---|---|---|
| 以太网 3（Realtek GbE） | `192.168.57.10` | 192.168.57.1 | 10（主出口） |
| 以太网（Realtek 2.5GbE） | `192.168.59.56` | 192.168.59.1 | 15 |
| 以太网 2（Realtek 2.5GbE #2） | `192.168.68.80` | 192.168.68.1 | 20 |

实测三个地址的 `/healthz` **均返回 200**：

```json
{"status":"ok","db":"/app/data/xuanpan.db","ai_mode":"auto","keep_photos":false}
```

而 APK 里**只内联了一个** `192.168.57.10`。所以：**如果你的手机不在 `192.168.57.x` 网段，打开 APP 会直接连不上。**
这不是 Bug，是编译期内联的固有代价。有两条逃生路径，**无需重新构建**：

**路径 A（推荐，10 秒）：APP 内切换线路**

```
我的 → 网络线路 → 输入 http://192.168.59.56:8360（或 .68.80）
      → 「测试并应用」
```

该卡片会**先探活再切换**（`app/(tabs)/mine.tsx` 的 `NetworkCard`），
地址不对时不会把界面切成"全部请求失败"，改回来的入口始终在。
首页连不上时也会把当前地址显示出来（`app/(tabs)/index.tsx`），便于对照。

> 已知限制：切换结果**不持久化**（未装 AsyncStorage），重启 APP 会退回内联地址。

**路径 B：用正确的 IP 重新构建**

```bash
# [Windows / Git Bash]
API_BASE_URL=http://192.168.68.80:8360 bash apps/mobile/scripts/build-apk.sh
```

增量构建（原生缓存已在）会明显快于首次的 49 分钟。

### 2.3 地址是怎么进 APK 的

`EXPO_PUBLIC_API_BASE_URL` 由 `babel-preset-expo` 在打包时**静态替换成字面量**
（Expo 官方文档化机制），因此不需要修改任何受版本控制的文件：

```
app.config.js  ──(XUANPAN_API_BASE_URL)──▶  app.json extra.apiBaseUrl
                                              │
src/api/client.ts resolveBaseUrl() 三级优先： │
  1. process.env.EXPO_PUBLIC_API_BASE_URL  ◀──┘ 构建期内联（生效的那一级）
  2. Constants.expoConfig.extra.apiBaseUrl       回落
  3. DEFAULT_BASE_URL                            兜底
```

构建后可用 `grep -c "192.168.57.10" index.android.bundle` 在产物里直接验证。

---

## 三、环境根因：clang / ld.lld 写不出目标文件

### 3.1 现象

构建停在**第一个** CMake 任务：

```
> Task :react-native-screens:configureCMakeRelWithDebInfo[arm64-v8a] FAILED
  The C compiler ".../ndk/26.1.10909125/.../clang.exe" is not able to compile a simple test program.
  error: unable to rename temporary 'CMakeFiles\cmTC_93d66.dir\testCCompiler.c-cec58174.o.tmp'
         to output file 'CMakeFiles\cmTC_93d66.dir\testCCompiler.c.o': 'Permission denied'
```

单独链接时：

```
ld.lld: error: failed to write output 'libt.so': Permission denied
```

### 3.2 逐一排除的错误方向

| 假设 | 实验 | 结论 |
|------|------|------|
| 中文路径（`D:\WorkBuddy\玄盘AI`）导致 | 换到纯 ASCII 的 `C:\tmp` 编译 | ❌ 同样失败，与路径无关 |
| NDK / Android target / sysroot | 换成 host target、去掉 `--target` | ❌ 同样失败 |
| 目标文件格式问题 | `clang -E` **只预处理成文本** | ❌ 同样失败 → 与格式无关 |
| 沙箱 / WorkBuddy 进程链 | 由 Python `subprocess` 派生 clang | ❌ 同样失败 |
| Bash 通道特有 | 换 PowerShell 通道派生 | ❌ 同样失败 |
| 文件权限 | 同目录 Python 写文件 + 改名 | ✅ 成功 → 权限没问题 |
| 操作系统 rename API | Python `ctypes` 直调 `MoveFileExW`，**5 种 flag 组合** | ✅ 全部成功 |
| 杀软信任区 | 火绒信任区已含 `D:\WorkBuddy`、`D:\Android Studio` | ❌ 仍 100% 复现 → 加白无用 |
| 编译器本身坏了 | 同目录 MinGW `gcc` 编译 | ✅ **5/5 成功** |

### 3.3 根因

**只有「内存映射 + 临时文件重命名」这条写出路径中招。**

- `clang` 走 `FileOutputBuffer`：创建 `.tmp` → `MapViewOfFile` → 写入 → 解映射 → `rename`
- `ld.lld` 默认 `--mmap-output-file`：直接 mmap 输出文件写入

这两者在**解映射到 rename 的毫秒级窗口**内，被本机的文件过滤驱动
（火绒 `sysdiag.sys` / `HipsDaemon.exe`，v6.0.12.1）打开并持有了句柄，
`rename` 因缺少 `FILE_SHARE_DELETE` 返回 `ACCESS_DENIED`，
而 LLVM 把该错误**统一归类为 `Permission denied`**——这就是报错信息的来源。

而 `gcc`、Python 的普通写+改名都不走 mmap，所以毫发无损。这解释了全部观测结果。

> **注意**：既然是驱动层拦截，**加杀软信任区是无效的**（已实测）。
> 正确的做法是让编译器绕开 mmap 写出路径。

### 3.4 解法

往 NDK 的工具链文件注入两个开关：

| 工具 | 开关 | 作用 |
|------|------|------|
| `clang` | `-fno-temp-file` | 直接写目标文件，不用临时文件重命名 |
| `ld.lld` | `-Wl,--no-mmap-output-file` | 不用内存映射写输出 |

**注入点是唯一的**：`<NDK>/build/cmake/android-legacy.toolchain.cmake`

```cmake
list(APPEND ANDROID_COMPILER_FLAGS -fno-temp-file)              # xuanpan
list(APPEND ANDROID_LINKER_FLAGS   -Wl,--no-mmap-output-file)   # xuanpan
```

为什么不能靠环境变量（**均已实测证伪**）：

- AGP **不向库模块**（`react-native-screens` / `expo-modules-core` 等）传 `-DCMAKE_C_FLAGS`
- `android-legacy.toolchain.cmake` 第 577–600 行会把 `CMAKE_C_FLAGS` **清空后重建**
  （`set(CMAKE_C_FLAGS "" CACHE STRING ...)`），所以 `CFLAGS` / `CXXFLAGS` / `LDFLAGS` 环境变量被吃掉
- `CCC_OVERRIDE_OPTIONS` 环境变量在 clang 17 上无效
- `ANDROID_USE_LEGACY_TOOLCHAIN_FILE` 默认就是 legacy，不能绕

**该补丁由 `build-apk.sh` 自动施加**（幂等：已打过就跳过），并自动备份为
`android-legacy.toolchain.cmake.xuanpan-orig`。

### 3.5 回滚

```bash
# 恢复原版工具链文件
cd "D:/Android Studio/Sdk/ndk/26.1.10909125/build/cmake"
cp android-legacy.toolchain.cmake.xuanpan-orig android-legacy.toolchain.cmake
```

回滚后本机的 C++ 构建会重新失败——**恢复的是「原状」，不是「可用态」**。
`samples/`、`data/`、`.env` 等业务数据均未被本补丁触及。

---

## 四、构建脚本用法

```bash
# 默认：arm64-v8a，后端 192.168.57.10:8360
bash apps/mobile/scripts/build-apk.sh

# 指定后端地址
API_BASE_URL=http://192.168.1.20:8360 bash apps/mobile/scripts/build-apk.sh

# 双架构
ARCH=arm64-v8a,armeabi-v7a bash apps/mobile/scripts/build-apk.sh

# 重建原生工程（会丢失 C++/Kotlin 编译缓存，全量约 20 分钟+）
CLEAN=1 bash apps/mobile/scripts/build-apk.sh

# 临时跳过 NDK 补丁（仅用于对比验证）
NO_NDK_PATCH=1 bash apps/mobile/scripts/build-apk.sh
```

脚本固化了 6 项本机必需处理（漏一项就是一次失败构建）：

1. `expo prebuild` 会重置 `gradle.properties` → 脚本每次重新写入必需项
2. Gradle wrapper 缺 `.ok` 标记时会用 Java 单线程重解压 286MB（约 10 分钟）→ 用 bsdtar 补（18 秒）
3. JVM 默认 `file.encoding=GBK`，而 `settings.gradle` 用 `node` 取路径（UTF-8 输出）→ 加 `-Dfile.encoding=UTF-8`
4. AGP 拒绝非 ASCII 项目路径 → `android.overridePathCheck=true`
5. Kotlin 版本必须等于 `react-native/libs.versions.toml` → `android.kotlinVersion=1.9.24`
6. **NDK 工具链 mmap 补丁**（见第三节）

---

## 五、再次失败时的排查决策树

```
构建失败
├─ "unable to rename temporary ... : Permission denied"  或
│  "ld.lld: error: failed to write output ... Permission denied"
│     → NDK 补丁丢了。检查：
│       grep -c fno-temp-file "<NDK>/build/cmake/android-legacy.toolchain.cmake"
│       返回 0 就手工补上（第三节 3.4），或删掉 .xuanpan-orig 让脚本重打
│
├─ "Unable to strip the following libraries, packaging them as they are"
│     → 非致命降级，见第六节。构建会继续并成功
│
├─ "Included build ... does not exist" / 中文路径乱码
│     → gradle.properties 的 -Dfile.encoding=UTF-8 丢了（prebuild 重置过）
│
├─ "requires Kotlin 1.9.25 but using 1.9.24"
│     → android.kotlinVersion 与 libs.versions.toml 不一致
│
├─ 报错只有 "> 25.0.2" 一个版本号
│     → JAVA_HOME 指向了 JDK 25。Gradle 8.10.2 只支持 JDK 17
│
├─ "Daemon compilation failed: null"
│     → kotlin.compiler.execution.strategy=in-process 丢了
│
└─ SAFE_DELETE_BULK_CONFIRM_REQUIRED
      → 脚本在执行批量删除（.cxx 含上万文件），被安全策略拦下。
        脚本已移除该步骤；需人工清理时用资源管理器删：
        apps/mobile/node_modules/*/android/.cxx
```

---

## 六、已知限制

### 6.1 `llvm-strip` 失败导致 `.so` 未裁剪（非致命）

```
> Task :react-native-screens:stripReleaseDebugSymbols
llvm-strip.exe: error: Permission denied
Unable to strip the following libraries, packaging them as they are: librnscreens.so.
```

- **根因同上**：`llvm-strip`（`llvm-objcopy` 系）也走 mmap 写出，但它的命令行**没有**任何
  「禁用 mmap / 禁用临时文件」的开关，无法用 flag 修
- **影响**：native 库**带完整符号表**打包，APK 体积偏大；功能完全正常
- **对测试反而是好事**：保留符号便于后续 native 崩溃定位
- **后续优化方向**：构建后单独做一次符号裁剪（需要能正常写 ELF 的环境），
  或在 `app/build.gradle` 配 `packagingOptions { doNotStrip "**/*.so" }` 关掉告警噪音

### 6.2 APK 使用 debug 签名

Expo 模板的 release 默认复用 debug keystore。**仅供内部测试安装**，
上架或对外分发必须换成正式签名的 keystore。

### 6.3 NDK 补丁是机器级改动

补丁写在 `D:\Android Studio\Sdk\ndk\26.1.10909125\` 下，
**不在版本控制内**。换机器、重装 NDK、升级 Android Studio 后都会丢失，
需要重新跑一次 `build-apk.sh`（脚本会自动重打）。

---

## 七、下一步

### 7.1 待你真机实测（本轮交付给你的验证项）

完整链路：**拍摄罗盘 → 识别坐向 → 确认 → 生成报告**

重点观察：

1. **相机权限**：首次进入拍摄页是否正常弹窗授权（Android 13+ 用 `READ_MEDIA_IMAGES`，13 以下用 `READ_EXTERNAL_STORAGE`，两者都已声明）
2. **上传耗时**：`/api/v1/scan` 超时上限 90s；若真机 4G/Wi-Fi 较慢可能触顶
3. **线路选择**：先按 2.2.1 确认手机能访问 `192.168.57.10:8360`，否则切线路
4. **渲染差异**：Hermes 字节码下中文字体、罗盘 SVG 是否与开发期一致
5. **报告生成**：`/report` 与 `/ask` 都要跑模型，会**真实产生调用成本**，重试不会自动发生（客户端刻意不自动重试）

### 7.2 后续工程优化

1. **网络线路持久化**：装 `@react-native-async-storage/async-storage`，把 `setApiBaseUrl` 的结果存下来；
   进一步可把三个候选地址预置成可点选按钮，让 APP 自动探测可用线路
2. **正式签名 + `.so` 裁剪**：把 94 MB 压下来（见 6.1 / 6.2）
3. **Gate 1 真实罗盘数据集评测**（与本文件无关，见 `玄盘 AI — Gate1 合成退化扫描.md`）
4. **`.cxx` 清理走人工**：脚本已移除自动删除（会触发批量删除守卫），需要时用资源管理器手动删
