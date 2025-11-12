# CodeBuddyForAAF

一个在CodeBuddy中嵌入AAF（AndroidAPPFactory）的完整工作区

## 项目结构

```
CodeBuddyForAAF/
├── .codebuddy/rules                  # codebuddy 规则
├── init.sh                          # 项目初始化脚本
├── README.md                        # 项目说明和开发指南（本文件）
├── .gitignore                       # Git忽略文件配置
├── AndroidAppFactory/               # AAF核心框架（自动克隆，已忽略）
├── AndroidAppFactory-Doc/          # AAF文档（自动克隆，已忽略）
└── Template-Empty/                  # 空模板项目（主要开发目录，自动克隆，已忽略）
```

## 快速开始

### 1. 环境准备
- 确保已安装JDK 8+
- 配置Android SDK
- 设置ANDROID_HOME环境变量
- 确保网络连接正常（用于自动克隆项目）

### 2. 项目初始化
```bash
./init.sh
```

**init.sh脚本功能：**
- 自动检查并克隆缺失的AAF项目到当前目录
- 移除克隆项目的git支持（避免意外提交）
- 配置开发环境和依赖
- 验证项目配置

### 3. 开始开发

**直接在CodeBuddy开发，或者进入Template-Empty开始开发**

```bash
# 或者直接进入Template-Empty开始开发
cd Template-Empty
```

**默认事例**

目前AAF 本身已经提供了一系列接口的调用展示及测试用例，可以参考 ./AndroidAppFactory/BaseDebug 和 ./AndroidAppFactory/BaseDebugCompose 中的事例

**功能查询**

完成导入以后，你可以直接通过文字交互来查询是否具有对应的能力和功能

## 常见问题

### Q: 初始化脚本会自动做什么？
A: init.sh脚本会：
1. 检查必要的AAF项目是否存在
2. 自动从GitHub克隆缺失的项目到当前目录
3. 移除克隆项目的.git目录（避免意外提交到原项目）
4. 配置开发环境和依赖

### Q: 为什么要移除git支持？
A: 
1. 避免意外提交代码到原始AAF项目
2. 让你可以自由修改代码而不受git历史约束
3. 可以根据需要重新初始化自己的git仓库

### Q: 为什么三个AAF项目目录在.gitignore中？
A: 
1. 这些是自动克隆的第三方项目，不应该提交到你的仓库
2. 保持你的仓库干净，只包含配置和脚本文件
3. 其他人克隆你的项目后，运行init.sh会自动获取这些依赖项目

### Q: 如果网络不好，克隆失败怎么办？
A: 
1. 检查网络连接
2. 可以手动克隆项目到当前目录
3. 重新运行init.sh脚本



## 相关链接

- **AAF框架文档**: https://android.bihe0832.com/doc/
- **技术方案介绍**: https://blog.bihe0832.com/android-dev-summary.html
- **框架代码统计**: https://android.bihe0832.com/source/lib/index.html
