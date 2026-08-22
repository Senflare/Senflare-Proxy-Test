# Senflare Proxy Test

Cloudflare 优选 IP 聚合测试脚本 —— 多源汇聚、漏斗检测、自动补全地区，GitHub Actions 每 3 小时自动更新结果。

## ✨ 工作流程

```
拉取多源（纯 IP 也收）→ 组内去重
  ├─ 只拉取组 ──────────────────────────── 直接汇入（上游已验证）
  └─ 需测试组 → ① TCP 存活测试 → ② HTTP 真 CF 验证 → 通过者汇入
                    ↓
        ③ 地区补全（缓存优先，纯 IP 统一格式）→ 合并去重 → Senflare-Proxy.txt
```

| 层 | 说明 |
|---|---|
| ① TCP 存活 | socket 直连测延迟，成功率不达标直接淘汰（300 并发） |
| ② HTTP 真 CF | `HEAD /cdn-cgi/trace` 必须返回 400 且 `server: cloudflare*`，过滤假节点，采样计算延迟/抖动（128 并发） |
| ③ 地区补全 | 无地区码的节点调 [ipinfo.io lite](https://ipinfo.io) 补齐；本地 LRU 缓存 1 万条，重复 IP 不重复查询 |

## 📡 数据源

**只拉取**（上游已验证，免测直入）：

| 来源 | 说明 |
|---|---|
| [Xiaobei09/proxyip](https://github.com/Xiaobei09/proxyip) | 聚合接口，已汇聚 Cmliu / Wentao883 / ChatBotPlus / Ymyuuu / Mountain787 等上游 |
| [Fangsia Karlina](https://github.com/papapapapdelesia/Emilia) | Emilia 存活列表（CSV） |
| [Xgonce](https://github.com/xgonce/Cloudflare_IP) | Cloudflare_IP 测速结果（CSV） |

**需测试**（通过 ①② 两层才汇入）：

| 来源 | 说明 |
|---|---|
| [xinyitang3/countrymerge](https://github.com/xinyitang3/cfnb) | countrymerge 全量列表 |

## 📤 输出格式

`Senflare-Proxy.txt`，每行一个节点，统一 `IP:端口#地区码`：

```
132.226.157.11:443#US
193.108.112.65:443#AL
157.22.240.45:8443#AR
```

免测组在前，测试通过的按 HTTP 延迟升序在后；跨组按 `ip:port` 去重。兼容解析：干净标签、emoji 国旗富标签、纯 IP（默认 443 端口）。

## 💻 本地运行

零第三方依赖，Python 3.8+ 直接跑：

```bash
python Start.py
```

常用参数在脚本头部常量区：

| 参数 | 默认 | 说明 |
|---|---|---|
| `TIMEOUT` | 2.0s | TCP 连接超时 |
| `MAX_WORKERS` | 300 | TCP 并发线程数 |
| `HTTP_TEST_WORKERS` | 128 | HTTP 并发线程数 |
| `REGION_CACHE_MAX` | 10000 | 地区缓存条数上限 |
| `TEST_LIMIT` | 0 | 🧪 试跑模式：每组只取前 N 个（0 = 全量） |

## 🤖 GitHub Actions 自动化

仓库自带 [`.github/workflows/run.yml`](.github/workflows/run.yml)：

- ⏰ 每 3 小时自动运行一次（UTC 错峰），支持手动触发
- 💾 运行结束自动提交 `Senflare-Proxy.txt` 与地区缓存回仓库
- 🔁 带 concurrency 防重入，无变化跳过提交

结果文件随时获取：

```
https://raw.githubusercontent.com/Senflare/Senflare-Proxy-Test/main/Senflare-Proxy.txt
```

## 🙏 致谢

数据均来自上述公开项目作者的持续验证与分享。
