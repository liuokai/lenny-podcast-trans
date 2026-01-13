# Lenny's Podcast 转译与浏览（重构版）

本项目用于**抓取播客文字稿**并**调用 DeepSeek 进行中文翻译**，同时提供**前端页面**进行双语对照浏览与交互“重新翻译”。遵循项目规则：可维护、可理解、可扩展、可验证。

## 项目结构

```
src/
  api/                # 对外 HTTP 服务（Flask）
    server.py
    templates/
      index.html
  service/            # 业务逻辑（抓取、翻译）
    scrape_service.py
    translate_service.py
  infra/              # 第三方服务封装
    deepseek_client.py
  config/             # 配置入口
    settings.py
episodes/             # 每个节目独立目录（输出）
episodes.json         # 节目列表配置
episode_manager.py    # 监控 episodes.json 并处理（抓取+翻译）
start_server.sh       # 一键启动 Web 服务脚本
```

## 功能概览
- 抓取 Substack 页面中的 transcript 并生成英文稿 `transcript.txt`
- 调用 DeepSeek 严格“只翻译不答题”生成 `transcript_bilingual.txt`
- 前端页面双栏展示：左侧英文、右侧中文；悬浮中文显示“重新翻译”并可实时覆盖对应段落
- 多节目管理：`episodes.json` 可新增节目链接，`episode_manager.py` 监控并自动处理

## 运行方式

### 依赖准备
请确保已安装 Python3，并在终端设置 DeepSeek API Key：
```bash
export DEEPSEEK_API_KEY="你的Key"
```
说明：
- 为避免泄露敏感信息，本项目**不修改 .env 文件**。环境变量由你在终端自行导出。

### 启动 Web 服务（浏览页面）
```bash
./start_server.sh
```
或：
```bash
python3 src/api/server.py
```
打开浏览器访问：
```
http://127.0.0.1:5001
```
- 页面顶部显示节目标题（中英），支持下拉选择不同节目
- 双栏展示双语内容；中文栏支持“重新翻译”并持久化到对应节目目录

### 添加新节目链接（自动处理）
1. 编辑 `episodes.json`，新增一条记录（状态为 pending）：
```json
{
  "episodes": [
    {
      "url": "https://www.lennysnewsletter.com/p/...你的链接...",
      "status": "pending"
    }
  ]
}
```
2. 在终端启动配置监控处理器：
```bash
python3 episode_manager.py
```
3. 当 `episodes.json` 被修改后，程序会自动：
   - 抓取 transcript 保存到 `episodes/<slug>/transcript.txt`
   - 调用 DeepSeek 翻译生成 `episodes/<slug>/transcript_bilingual.txt`
   - 更新该节目 `status` 为 `completed`

### 手动处理单节目（可选）
若你更偏好单次执行：
```bash
python3 scrape_transcript.py --url "<节目链接>" --out-dir "episodes/<slug>"
python3 translate_transcript.py --input "episodes/<slug>/transcript.txt" --output "episodes/<slug>/transcript_bilingual.txt"
```

## 配置说明
- 所有可变配置在 `src/config/settings.py` 中集中管理：
  - `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 等非敏感项
  - `DEEPSEEK_API_KEY` 从环境变量读取（不写入 .env）
  - `EPISODES_DIR`、`EPISODES_CONFIG_PATH` 文件布局
- 业务代码不硬编码敏感信息，遵循“显式优于隐式”

## 错误处理与日志
- DeepSeek API Key 未设置时会抛出异常提示
- 抓取与解析失败会抛出可读错误，便于定位问题
- 关键流程（抓取、翻译、保存）均有明确输入输出点

## 说明
- 本 README 仅记录已实现的功能与使用方式（不包含计划中内容）
- 如需扩展为多页面或更丰富的节目元数据管理，可在 `src/domain/` 中引入更清晰的数据模型与校验流程
