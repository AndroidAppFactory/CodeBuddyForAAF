# APK体积分析Skill开发经验与踩坑记录

> 本文件记录APK体积分析Skill开发过程中的经验教训和踩坑复盘，供后续维护和优化参考。

## 开发经验记录

### 1. 灯箱图片尺寸收敛
**问题**：灯箱图片默认撑满整屏，信息面板空间不足
**解决**：横图模式限 `min(72vw, 880px)` × 68vh，竖图模式限 `min(42vw, 480px)` × 78vh

### 2. 目录按钮统一为"复制路径"而非file://链接
**问题**：浏览器对file://目录处理不一致，无法唤起文件管理器
**解决**：统一改为复制目录绝对路径到剪贴板，用户粘贴到Finder/Explorer地址栏

### 3. 未用资源多module聚合
**问题**：Lint默认只报告当前module，漏掉library未用资源
**解决**：扫描所有module的lint报告，按(type,name,defined_at,line)去重聚合

### 4. 脚本只读lint报告，不执行任何gradle命令
**原则**：脚本绝不自动执行gradle命令，只解析现有报告，用户手动执行lint

### 5. 未用资源覆盖面不足自动提示
**机制**：聚合≥3份报告但只命中≤1个module时，提示启用checkDependencies

### 6. 未用资源分类视图+图片预览
**优化**：按res_type分组折叠，drawable/mipmap用缩略图网格，非图片用紧凑表格

### 7. HTML顶部header紧凑化+分析耗时展示
**改进**：单行布局，文件名+四项指标+耗时，信息密度提升

### 8. Tab顶部摘要Pills→summary-line单行总结
**优化**：自然语言单句，只保留Top3类型，避免pill过多占用空间

### 9. 灯箱图片详情统一左图右文布局
**设计**：右列文字优先≥50vw，保证路径/引用列表/操作按钮展示空间

### 10. 修复图片资源目录缺失横幅关闭按钮失效
**问题**：CSS特异性冲突导致hidden属性失效
**解决**：添加[hidden] { display: none !important }

### 11. 未用资源卡片瘦身：定位信息移到灯箱
**优化**：卡片只保留资源名+体积，定位信息在灯箱展示

### 12. 修复未用资源module字段致命错位
**问题**：checkDependencies开启时，所有资源module都变成APPTest
**解决**：从defined_at路径推断真实module名

### 13. 统一「目录」按钮文案：📂打开目录→📋复制目录
**问题**：按钮文案与行为不符，实际是复制而非打开
**修复**：三处统一改为📋复制目录

### 14. 修复灯箱大横图挤爆右侧信息面板
**根因**：CSS规则顺序导致布局约束被覆盖
**解决**：调整规则顺序，添加min-width:0约束

### 15. Lint未用资源「按module筛选」chips改为可折叠面板
**优化**：默认折叠，summary显示当前选中状态，避免占用过多空间

### 16. 批量压缩脚本：通用shell + 临时清单（解耦逻辑与数据）
**问题**：给用户生成压缩产物时，"定制 shell"会把图片路径硬编码进脚本，逻辑与数据耦合，脚本本体不可复用、后续修复算法还得改所有旧报告
**方案**：固定内容的通用 `compress_images.sh`（作为 skill 资源模板）+ 每次生成的 `compress_images.list`（第 1 列为工程源文件真实路径）。Python 生成器只负责复制模板 + 反查源路径生成清单
**价值**：脚本本体可版本化；用户可手改清单剔除/追加图片；符合 Unix 哲学

### 17. 原地替换必须基于工程源文件而非 APK 解压副本
**踩坑**：最初想法是压缩 `{report}_assets/images/` 里的解压副本，但这些是只读副本——压缩它们对 APK 瘦身毫无意义
**根因**：真正会被打进 APK 的是工程里的源文件（如 `app/src/main/res/drawable-xxxhdpi/ic.png`），必须改这些才有效
**方案**：清单第 1 列 = 工程源文件真实绝对路径；反查策略：`basename` 建索引 → 按 APK 内路径尾部严格匹配 → 多 flavor 命中则全部写入 → 无匹配写 `# SKIPPED`

### 18. 压缩脚本三模式：dryrun / apply / restore
**设计**：默认 dry-run（不加参数只打印将要压缩的文件），`--apply` 才真执行（先 mkdir 镜像备份 → 调 TinyPNG → 校验 new_size < old_size 才覆盖），`--restore` 从 `.backup/` 一键恢复
**关键校验**：启动先调 TinyPNG `/shrink` 无 body 预检 Key 有效性（401/403 退出，400 视为 Key 有效）；压缩结果必须满足 `new_size > 0 && new_size < old_size` 才覆盖，否则保留原文件

### 19. 9-patch 双层兜底跳过
**必要性**：`*.9.png` 的 stretch/padding 区域在压缩后会被破坏，导致 UI 崩
**方案**：Python 生成器端过滤到注释区不写入主清单；shell 再判一次 `*.9.png|*.9.PNG` 兜底跳过，防止用户手改清单误加入

### 20. 批量压缩：shell 本体不进报告产物，只生成清单
**问题**：一开始把 `compress_images.sh` 复制进每次分析的 `{report}_assets/` 里，意味着脚本被复制 N 份——改算法时只能改 skill 源码，老报告里的脚本版本会过时；分享 zip 也臃肿
**解决**：shell 本体永远留在 skill 目录（`scripts/templates/compress_images.sh`），每次分析只在 `{report}_assets/` 下生成 `compress_images.list`。HTML「可优化图片」Tab 和终端同时给出 `bash <skill>/.../compress_images.sh --list <list>` 的完整命令，用户直接复制即可执行
**副产物落盘**：shell 把 `.backup/` 和 `compress_images.log` 派生自 `--list` 所在目录（即 `{report}_assets/`），这样"一次分析 = 一份清单 + 一份备份 + 一份日志"自成闭环；同时支持 `--backup-dir` / `--log` 显式覆盖

## 技术要点

### CSS规则管理
- 相同特异度下，规则顺序决定覆盖关系
- flex容器内图片必须设置min-width:0
- hidden属性需要配合display:none !important

### 路径处理
- 浏览器无法直接打开file://目录，只能复制路径
- 从资源路径推断module比从报告路径更准确

### 用户体验
- 默认折叠复杂内容，按需展开
- 按钮文案必须与行为一致
- 重要状态信息在折叠面板中保持可见

### 脚本安全设计
- 破坏性操作默认 dry-run，需 `--apply` 显式开启
- 任何原地替换都必须先备份到 `.backup/{相对根目录}/`（保留结构避免同名冲突）
- 外部 API 依赖必须预校验（如 TinyPNG Key 在启动时调一次无 body 预检）
- 压缩结果必须通过 `new_size > 0 && new_size < old_size` 双重门禁才覆盖原文件
- 提供配套的 `--restore` 一键回滚命令，让用户敢跑
