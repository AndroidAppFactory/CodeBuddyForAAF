# CodeBuddyForAAF

AAF（AndroidAppFactory）开发辅助工具集，由 [ZixieKit](https://github.com/bihe0832/ZixieKit) 自动同步。

---

## 目录结构

```
CodeBuddyForAAF/
├── skills/          # 14 个 Skill
│   ├── aaf-demo/                # AAF Demo 开发助手
│   ├── aaf-doc-generator/       # AAF 文档生成
│   ├── aaf-doc-management/      # AAF 文档管理
│   ├── aaf-project-finder/      # AAF 项目定位
│   ├── aaf-release-check/       # AAF 发布前检查
│   ├── aaf-sample-apply/        # AAF Sample 升级
│   ├── aaf-sample-upgrade/      # AAF Sample 项目升级
│   ├── aaf-version-reader/      # AAF 版本信息读取
│   ├── aaf-version-upgrade/     # AAF 依赖版本升级
│   ├── adb-port-killer/         # ADB 端口释放
│   ├── android-debug/           # Android 调试
│   ├── android-log/             # Android 日志分析
│   ├── apk-16kb-check/          # APK 16KB 对齐检查
│   └── apk-size-analyzer/       # APK 包大小分析
├── commands/        # 11 个 CLI 命令
│   ├── aaf.release.md           # AAF 发布检查
│   ├── aaf.update.md            # AAF 版本升级
│   ├── aaf.version.reader.md    # 读取 AAF 版本信息
│   ├── aaf.version.update.md    # 更新 AAF 版本
│   ├── adb.replay.edit.md       # ADB 回放编辑器
│   ├── adb.replay.play.md       # ADB 回放执行
│   ├── adb.replay.record.md     # ADB 录制
│   ├── android.16kb.md          # 16KB 对齐检查
│   ├── android.apksize.md       # APK 包大小分析
│   ├── android.debug.md         # Android 调试
│   └── android.log.md           # Android 日志
├── rules/           # AAF 通用规则
│   └── aaf_common.mdc
├── tools/           # 可执行工具
│   └── aafkit/                  # AAF CLI 工具包
└── scripts/         # 共享脚本（依赖注入）
```

---

## 使用方式

### 作为 CodeBuddy Skill 使用

将本仓库作为 CodeBuddy 项目打开，对话中直接提及对应 Skill 的触发关键词即可唤起。

### 直接运行工具

```bash
# APK 16KB 对齐检查
python3 skills/apk-16kb-check/scripts/check_alignment.py <APK/AAB/AAR 路径>

# APK 包大小分析
python3 skills/apk-size-analyzer/scripts/analyze_apk.py <APK 路径>

# AAF CLI 工具
python3 -m tools.aafkit
```

---

## License

MIT
