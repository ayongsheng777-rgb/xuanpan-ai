#!/usr/bin/env bash
#
# 构建可直接安装到真机的 release APK（默认仅 arm64-v8a）。
#
# ============================================================================
# 为什么必须用脚本，而不是直接敲 gradlew
# ============================================================================
# 本项目路径含中文（D:\WorkBuddy\玄盘AI），在 Windows 上触发了一串环境问题。
# 每一个都要手工处理，漏掉任何一步就是一次 30 分钟的失败构建：
#
#   1. `expo prebuild --clean` 会**重置 android/gradle.properties** ——
#      而几个必需开关恰恰都写在那个文件里（编码、Kotlin 版本、路径检查）。
#      手工流程里这一步最容易被忽略。
#   2. Gradle wrapper 缺少 .ok 完成标记时会重新解压 286MB 的发行版。
#      它用 Java 单线程解压，实测约 10 分钟；用 bsdtar 只要 18 秒。
#   3. JVM 默认 file.encoding=GBK，而 settings.gradle 通过
#      `node --print require.resolve(...)` 取路径 —— node 输出 UTF-8，
#      GBK 解码后中文路径变成乱码，报「Included build ... does not exist」。
#   4. AGP 默认拒绝非 ASCII 项目路径，需要显式开关绕过。
#   5. Compose Compiler 按 ext.kotlinVersion 查版本表，而真正的 Kotlin
#      编译器版本来自 react-native 的 libs.versions.toml —— 两者必须一致，
#      否则 expo-modules-core 编译报「requires Kotlin 1.9.25 but using 1.9.24」。
#   6. 【NDK 内存映射写出被安全驱动拦截】——最难的一个，见下节。
#
# ============================================================================
# 问题 6 详解：clang / ld.lld 在本机 100% 无法写出目标文件
# ============================================================================
# 现象（构建停在第一个 CMake 任务）：
#   :react-native-screens:configureCMakeRelWithDebInfo[arm64-v8a] FAILED
#     error: unable to rename temporary 'testCCompiler.c-xxxx.o.tmp'
#            to output file 'testCCompiler.c.o': 'Permission denied'
#   单独链接时：
#     ld.lld: error: failed to write output 'libx.so': Permission denied
#
# 排查结论（全部实测，非推测）：
#   · clang 连 `-E` 预处理成文本都失败 → 与目标文件格式/ABI/NDK sysroot 无关
#   · 把 clang.exe 复制到 C:\tmp 再跑，同样失败 → 与路径、中文目录无关
#   · 同一目录下 gcc 编译 5/5 成功、Python 写文件+改名成功、
#     MoveFileExW 五种 flag 组合全部成功 → 操作系统与 API 层完全健康
#   · 用线程毫秒级轮询抓取，clang 确实创建出了 .tmp 文件，失败发生在
#     「解映射 → 重命名」这一瞬间
#
# 根因：clang(FileOutputBuffer) 与 ld.lld 都默认用
#   「创建临时文件 → 内存映射写入 → 重命名」写出目标文件。
#   本机文件过滤驱动（火绒 sysdiag.sys / HipsDaemon）在这个毫秒级窗口内
#   打开了该文件，rename 因缺少 FILE_SHARE_DELETE 而返回 ACCESS_DENIED，
#   LLVM 把它统一归类成 "Permission denied"。
#   注意：火绒信任区里已配置 D:\WorkBuddy 与 D:\Android Studio，仍然复现 ——
#         所以不能指望「加信任区」解决，必须让编译器绕开 mmap 写出路径。
#
# 解法：往 NDK 的 android-legacy.toolchain.cmake 注入两行
#   ANDROID_COMPILER_FLAGS += -fno-temp-file            编译直接写目标文件
#   ANDROID_LINKER_FLAGS   += -Wl,--no-mmap-output-file 链接不用内存映射
#   为什么必须改 NDK 文件：AGP 不会向库模块的 CMake 传 -DCMAKE_C_FLAGS，
#   而 legacy toolchain 又会把 CMAKE_C_FLAGS 清空重建，
#   CFLAGS/CXXFLAGS/LDFLAGS 环境变量一律不生效 —— 工具链文件是唯一的注入点。
#
# 本脚本会自动打这个补丁（幂等、带 .xuanpan-orig 备份）。
# 回滚：恢复 android-legacy.toolchain.cmake.xuanpan-orig 即可。
#
# ============================================================================
# 用法
# ============================================================================
#   bash apps/mobile/scripts/build-apk.sh
#   API_BASE_URL=http://192.168.1.20:8360 bash apps/mobile/scripts/build-apk.sh
#   ARCH=arm64-v8a,armeabi-v7a bash apps/mobile/scripts/build-apk.sh
#   CLEAN=1 bash apps/mobile/scripts/build-apk.sh      # 重建原生工程
#   NO_NDK_PATCH=1 bash apps/mobile/scripts/build-apk.sh
#
# 产物：apps/mobile/android/app/build/outputs/apk/release/app-release.apk
#
# 注意：本脚本需要读写 Android SDK 与 ~/.gradle 缓存，
#       在受限沙箱中执行会被拒绝写入，需以正常权限运行。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ANDROID_DIR="$MOBILE_DIR/android"

# ---- 可覆盖的构建参数 -------------------------------------------------------
# 默认用 ddns-go 维护的域名而非局域网 IP：
#   oc.ayong.qzz.io 由本机 ddns-go 每 300s 刷新（AAAA → 本机「以太网」IPv6），
#   手机连 Wi-Fi（同链路直连）与连移动数据（走公网 IPv6）两种场景都可用；
#   局域网 IP 只在同网段有效，且随 DHCP 租约/网卡变化。
#   需要临时指回局域网地址时用 API_BASE_URL=... 覆盖即可。
API_BASE_URL="${API_BASE_URL:-http://oc.ayong.qzz.io:8360}"
ARCH="${ARCH:-arm64-v8a}"
NO_NDK_PATCH="${NO_NDK_PATCH:-0}"

# Android SDK / JDK。
#
# JAVA_HOME 刻意**不**沿用同名环境变量：本机环境里的 JAVA_HOME 指向 Android Studio
# 自带的 jbr（JDK 25），而 Gradle 8.10.2 不支持 JDK 25 —— 报错只显示一个版本号
# 「> 25.0.2」，完全看不出是 JDK 版本问题，排查成本极高。
# RN 0.76 / AGP 8.6 要求的是 JDK 17，这里固定用它（需要换用 XUANPAN_JAVA_HOME）。
export JAVA_HOME="${XUANPAN_JAVA_HOME:-D:/Android Studio/jdk-17.0.20+8}"
export ANDROID_HOME="${ANDROID_HOME:-D:/Android Studio/Sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

# Kotlin 版本必须与 react-native 的 libs.versions.toml 保持一致。
KOTLIN_VERSION="${KOTLIN_VERSION:-1.9.24}"

log() { printf '\n=== %s ===\n' "$1"; }

# ---- 0. 前置检查 -------------------------------------------------------------
log "环境检查"
[ -x "$JAVA_HOME/bin/java.exe" ] || [ -x "$JAVA_HOME/bin/java" ] \
  || { echo "JDK 未找到: $JAVA_HOME（可用 JAVA_HOME 覆盖）" >&2; exit 1; }
[ -d "$ANDROID_HOME/platforms" ] \
  || { echo "Android SDK 未找到: $ANDROID_HOME（可用 ANDROID_HOME 覆盖）" >&2; exit 1; }
command -v node >/dev/null 2>&1 \
  || { echo "node 不在 PATH 中" >&2; exit 1; }
echo "  JDK        : $JAVA_HOME"
echo "  Android SDK: $ANDROID_HOME"
echo "  后端地址   : $API_BASE_URL"
echo "  目标架构   : $ARCH"

# ---- 1. 修复 Gradle 发行版（缺 .ok 标记时补解压）----------------------------
# Gradle wrapper 判定"解压完成"的依据是同目录下的 <zip>.ok 文件。
# 若上一次构建被中断，标记不会写入，wrapper 会重新解压 —— 用 Java 单线程，
# 286MB 实测约 10 分钟。这里提前用 bsdtar 补上，速度快百倍。
log "检查 Gradle 发行版"
DISTS="$HOME/.gradle/wrapper/dists"
if [ -d "$DISTS" ]; then
  shopt -s nullglob
  for zip in "$DISTS"/*/*/*.zip; do
    dist_dir="$(dirname "$zip")"
    [ -f "$zip.ok" ] && continue
    inner="$(basename "$zip" .zip)"
    echo "  → $(basename "$zip") 缺少完成标记，用 bsdtar 补解压"
    rm -rf "${dist_dir:?}/$inner"
    if [ -x /c/Windows/System32/tar.exe ]; then
      /c/Windows/System32/tar.exe -xf "$zip" -C "$dist_dir"
    else
      (cd "$dist_dir" && unzip -q "$zip")
    fi
    touch "$zip.ok"
    echo "  → 已补解压并写入完成标记"
  done
  shopt -u nullglob
fi
echo "  OK"

# ---- 2. 给 NDK 工具链打 mmap 绕过补丁（问题 6 的解药）-----------------------
# 详细根因见文件头「问题 6 详解」。此处只做幂等落地：
#   已打过 → 跳过；未打过 → 备份 .xuanpan-orig 后注入两行。
log "检查 NDK 工具链补丁"

# 解析实际使用的 NDK 目录：优先 android/build.gradle 里的 ndkVersion，其次环境变量，最后取最新一个
resolve_ndk_dir() {
  local v="" d=""
  if [ -f "$ANDROID_DIR/build.gradle" ]; then
    v="$(grep -oE 'ndkVersion[[:space:]]*[=:][[:space:]]*"[^"]+"' "$ANDROID_DIR/build.gradle" 2>/dev/null \
         | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
  fi
  [ -z "$v" ] && v="${NDK_VERSION:-}"
  if [ -n "$v" ] && [ -d "$ANDROID_HOME/ndk/$v" ]; then printf '%s' "$ANDROID_HOME/ndk/$v"; return; fi
  ls -d "$ANDROID_HOME"/ndk/* 2>/dev/null | sort -V | tail -1
}

NDK_DIR="$(resolve_ndk_dir || true)"
if [ "$NO_NDK_PATCH" = "1" ]; then
  echo "  NO_NDK_PATCH=1，跳过（若构建报 Permission denied，就是这里被跳过的原因）"
elif [ -z "$NDK_DIR" ] || [ ! -d "$NDK_DIR" ]; then
  echo "  ! 未找到 NDK 目录，跳过补丁。已安装的 NDK:" >&2
  ls -d "$ANDROID_HOME"/ndk/* 2>/dev/null | sed 's/^/    /' >&2 || echo "    (无)" >&2
else
  TOOLCHAIN="$NDK_DIR/build/cmake/android-legacy.toolchain.cmake"
  TC_BAK="$TOOLCHAIN.xuanpan-orig"
  echo "  NDK: $(basename "$NDK_DIR")"
  if [ ! -f "$TOOLCHAIN" ]; then
    echo "  ! 未找到 $TOOLCHAIN，跳过补丁" >&2
  elif grep -q -- '-fno-temp-file' "$TOOLCHAIN"; then
    echo "  补丁已存在，跳过（备份: $(basename "$TC_BAK")）"
  else
    cp "$TOOLCHAIN" "$TC_BAK"
    echo "  → 已备份: $(basename "$TC_BAK")"
    # 在 "# Convert these lists into strings." 之前插入两行。
    # 纯 sed 实现，不依赖 python，插入点唯一且稳定。
    sed -i 's|^# Convert these lists into strings\.$|list(APPEND ANDROID_COMPILER_FLAGS -fno-temp-file)  # xuanpan: 见 scripts/build-apk.sh 问题 6\nlist(APPEND ANDROID_LINKER_FLAGS   -Wl,--no-mmap-output-file)  # xuanpan: 见 scripts/build-apk.sh 问题 6\n# Convert these lists into strings.|' "$TOOLCHAIN"
    if grep -q -- '-fno-temp-file' "$TOOLCHAIN"; then
      echo "  → 补丁已注入（-fno-temp-file + --no-mmap-output-file）"
    else
      echo "  ! 补丁注入失败，请检查 $TOOLCHAIN 的写入权限" >&2
      exit 1
    fi
  fi
fi

# ---- 3. 原生构建缓存（默认不动）---------------------------------------------
# 上一次失败/中断的 CMake configure 会在 .cxx 下留下半成品。实测不需要清理：
# 上次 configure 并未成功，CMake 下次会自行重跑整条 configure，届时会重新
# 执行工具链文件、拿到新参数。
#
# 千万不要在这里 rm -rf .cxx —— 单个 .cxx 就有上万个文件，会被安全策略的
# 批量删除守卫拦下（SAFE_DELETE_BULK_CONFIRM_REQUIRED），直接中断整个构建。
# 确实需要清空时请人工在资源管理器里删除下列目录：
#   apps/mobile/node_modules/*/android/.cxx
#   apps/mobile/android/.cxx 与 apps/mobile/android/app/.cxx
log "原生构建缓存"
if [ "${CLEAN_CXX:-0}" = "1" ]; then
  echo "  CLEAN_CXX=1 —— 需要人工删除，脚本不执行批量删除（原因见脚本说明）"
  find "$MOBILE_DIR/node_modules" -maxdepth 5 -type d -name .cxx -print 2>/dev/null | sed 's/^/    待删: /' || true
  for d in "$ANDROID_DIR/.cxx" "$ANDROID_DIR/app/.cxx"; do
    [ -d "$d" ] && echo "    待删: $d"
  done
  echo "  ^ 请在资源管理器中删除上述目录后重新运行本脚本"
  exit 0
else
  echo "  跳过（默认保留，CMake 会自行重跑 configure）"
fi

# ---- 4. 生成原生工程 ---------------------------------------------------------
# CLEAN=1 会先删掉整个 android/ 再重建 —— 更干净，但所有 C++/Kotlin/Java
# 编译产物随之丢失，下次是全量编译（实测 20 分钟以上）。
# 默认不清理：config plugin 每次都会重新同步图标、启动图与权限，
# 资源变更不需要靠 --clean 才能生效，而保留 build/ 能走增量编译。
log "生成原生工程（prebuild，CLEAN=${CLEAN:-0}）"
cd "$MOBILE_DIR"
PREBUILD_ARGS=(--platform android)
[ "${CLEAN:-0}" = "1" ] && PREBUILD_ARGS+=(--clean)
XUANPAN_API_BASE_URL="$API_BASE_URL" npx expo prebuild "${PREBUILD_ARGS[@]}"

# ---- 5. 重新应用 prebuild 会重置的配置 --------------------------------------
# 这几项是第 3、4、5 号问题的解药，必须写在 gradle.properties 里。
log "应用 gradle.properties 必需配置"
GP="$ANDROID_DIR/gradle.properties"
sed -i 's|^org\.gradle\.jvmargs=.*|org.gradle.jvmargs=-Xmx4096m -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8|' "$GP"

# 追加前必须确保文件以换行结尾：prebuild 生成的 gradle.properties 末行
# （android.extraMavenRepos=[]）没有换行符，直接 append 会拼成
# 「android.extraMavenRepos=[]android.kotlinVersion=1.9.24」这样一条无效配置 ——
# 不报错、不生效，只是默默用回错误的 Kotlin 版本。
[ -n "$(tail -c 1 "$GP" 2>/dev/null)" ] && printf '\n' >> "$GP"

grep -q '^android.kotlinVersion=' "$GP"     || echo "android.kotlinVersion=$KOTLIN_VERSION" >> "$GP"
grep -q '^android.overridePathCheck=' "$GP" || echo 'android.overridePathCheck=true' >> "$GP"
# Kotlin 编译改在 Gradle daemon 进程内执行。
# 默认策略会另起一个 Kotlin daemon，本机上它反复启动失败，报错只有一句
# 「Daemon compilation failed: null」加一段栈，不给任何根因线索。
# in-process 省掉这个额外 JVM（也省一份内存），代价是增量编译略慢。
grep -q '^kotlin\.compiler\.execution\.strategy=' "$GP" \
  || echo 'kotlin.compiler.execution.strategy=in-process' >> "$GP"

# 说明块：**幂等**。
# 之前这里是无条件 `cat >>`，每次构建都会再追加一遍，日志里能看到同一段
# 注释重复出现。现在先按起始标记整段删除到文件末尾，再重新追加。
sed -i '/^# >>> build-apk\.sh 追加区/,$d' "$GP"
cat >> "$GP" <<'EOF'
# >>> build-apk.sh 追加区（每次构建会整段重写，请勿在下方手工添加）
# `expo prebuild` 会重置本文件，所以这些配置放在脚本里而不是 app.json：
#   file.encoding=UTF-8 : settings.gradle 用 node 取路径，输出是 UTF-8，
#                        JVM 默认 GBK 会把中文路径解成乱码
#   kotlinVersion       : 必须等于 react-native libs.versions.toml 里的 kotlin，
#                        否则 expo-modules-core 的 Compose 插件判定不兼容
#   overridePathCheck   : AGP 默认拒绝非 ASCII 项目路径
#   kotlin.execution.strategy=in-process : 本机独立 Kotlin daemon 启动失败
EOF
grep -E "jvmargs|kotlinVersion|overridePathCheck|execution.strategy" "$GP" | sed 's/^/  /'

# SDK 路径写成文件，避免依赖环境变量传递（prebuild 也会重置它）
cat > "$ANDROID_DIR/local.properties" <<EOF
sdk.dir=$(echo "$ANDROID_HOME" | sed 's|\\|/|g')
EOF

# ---- 6. JS bundle 与后端地址的一致性 ----------------------------------------
# 坑：Gradle 的 createBundleReleaseJsAndAssets 任务**不把环境变量算作任务输入**。
# 只改 API_BASE_URL 重跑构建时，该任务被判 UP-TO-DATE 并复用上一次的 bundle，
# 于是 APK 里嵌的还是旧地址，而构建日志一路绿灯（实测 630 up-to-date / 1m25s 就
# 报 BUILD SUCCESSFUL）。若不校验 APK 内容，会直接把指向旧地址的包装出去。
# 解法：记录上次注入的地址，一旦变化就清掉 bundle 产物强制重打包。
# 需要无条件重打包时用 FORCE_BUNDLE=1。
BUNDLE_STAMP="$ANDROID_DIR/.xuanpan-api-base-url"
BUNDLE_TASK_DIR="$ANDROID_DIR/app/build/generated/assets/createBundleReleaseJsAndAssets"
BUNDLE_MERGED="$ANDROID_DIR/app/build/intermediates/assets/release/mergeReleaseAssets/index.android.bundle"
BUNDLE_SOURCEMAP="$ANDROID_DIR/app/build/generated/sourcemaps/react"

LAST_URL=""
[ -f "$BUNDLE_STAMP" ] && LAST_URL="$(cat "$BUNDLE_STAMP" 2>/dev/null || true)"

if [ "$LAST_URL" != "$API_BASE_URL" ] || [ "${FORCE_BUNDLE:-0}" = "1" ]; then
  log "后端地址变更，清理旧 JS bundle（强制重打包）"
  echo "  上次注入: ${LAST_URL:-（无记录，视为变更）}"
  echo "  本次注入: $API_BASE_URL"
  [ -d "$BUNDLE_TASK_DIR" ] && rm -rf "$BUNDLE_TASK_DIR"
  [ -f "$BUNDLE_MERGED" ] && rm -f "$BUNDLE_MERGED"
  [ -d "$BUNDLE_SOURCEMAP" ] && rm -rf "$BUNDLE_SOURCEMAP"
  echo "  已清理 bundle 产物"
else
  echo "  后端地址未变（$API_BASE_URL），复用已有 JS bundle"
fi
printf '%s' "$API_BASE_URL" > "$BUNDLE_STAMP"

# ---- 7. 构建 ----------------------------------------------------------------
log "开始构建（$(date '+%H:%M:%S')）"
cd "$ANDROID_DIR"
export EXPO_PUBLIC_API_BASE_URL="$API_BASE_URL"
export XUANPAN_API_BASE_URL="$API_BASE_URL"
bash ./gradlew assembleRelease -PreactNativeArchitectures="$ARCH" --console=plain

# ---- 8. 汇总与自检 ----------------------------------------------------------
log "构建完成（$(date '+%H:%M:%S')）"
APK="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
if [ -f "$APK" ]; then
  echo "  产物: $APK"
  echo "  大小: $(du -h "$APK" | cut -f1)"
  echo "  内嵌后端地址: $API_BASE_URL"

  # 自检：确认 bundle 里确实写着本次的地址。
  # 「BUILD SUCCESSFUL」不等于「地址正确」—— 第 6 步那个缓存坑产出的包同样报成功，
  # 里面却嵌着上一版的地址。这里直接读 bundle 内容做断言，失败就退出非零。
  BUNDLE_FILE="$BUNDLE_TASK_DIR/index.android.bundle"
  if [ -f "$BUNDLE_FILE" ]; then
    if grep -qF -- "$API_BASE_URL" "$BUNDLE_FILE"; then
      echo "  ✅ 自检通过：JS bundle 内含 $API_BASE_URL"
    else
      echo "  ❌ 自检失败：JS bundle 内未找到 $API_BASE_URL" >&2
      echo "     bundle 文件: $BUNDLE_FILE" >&2
      echo "     处理: FORCE_BUNDLE=1 重跑本脚本" >&2
      exit 1
    fi
  fi
else
  echo "  未找到产物，请检查上面的构建输出" >&2
  exit 1
fi
