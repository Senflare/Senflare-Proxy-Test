# Senflare Proxy Test

Senflare Proxy Test —— Cloudflare ProxyIP 聚合 / 测试脚本 —— 多源汇聚, GitHub Actions 每小时自动更新结果


🌐 **主站**：<https://proxy.seeck.cn/> ｜ **备用**：<https://proxy-vercel.seeck.cn/>


## ✨ 工作流程

```
拉取多源 → 组内去重 → 剔除 Cloudflare 官方网段
  ├─ 免测数据 ─ 直接汇入（上游有实测流水线）
  └─ 待测数据 → TCP 存活测试 → HTTP 验证 → 通过者写入
                    ↓
        地区补全（缓存优先，纯 IP 统一格式）→ 合并去重 → Senflare-Proxy.txt
```

| 层 | 说明 |
|---|---|
| TCP 存活 | socket 直连测延迟，成功率不达标直接淘汰（200 并发） |
| HTTP 验证 | `HEAD /cdn-cgi/trace` 必须返回 400 且 `server: cloudflare*`，过滤假节点，采样计算延迟/抖动（100 并发） |
| 地区补全 | 无地区码的节点调 [ipinfo.io lite](https://ipinfo.io) 补齐；本地 LRU 缓存 1 万条，重复 IP 不重复查询 |

拉取主走 raw 直链（推送即生效），jsDelivr 仅作备用；源配置在 `Start.py`，格式解析在 `SourceParse.py`。

## 📡 数据来源

[Xiaobei09](https://github.com/Xiaobei09) · [Cmliu](https://github.com/cmliu) · [Wentao883](https://github.com/wentao883) · [ChatBotPlus](https://github.com/ChatBotPlus) · [Ymyuuu](https://github.com/ymyuuu) · [Mountain787](https://github.com/mountain787) · [Fangsia Karlina](https://github.com/papapapapdelesia) · [Xgonce](https://github.com/xgonce) · [Lzj](https://github.com/wanwushequ/cfyxip) · [wan828963-code](https://github.com/wan828963-code/best-cf-ips) · [alphaxzj](https://github.com/alphaxzj/bestcf) · [rxsweet](https://github.com/rxsweet/cfip) · [liyan1972](https://github.com/liyan1972/proxyip-fetcher) · [NiREvil/vless](https://github.com/NiREvil/vless) · [avotcorg](https://github.com/avotcorg/proxy)

## 📤 输出格式

`Senflare-Proxy.txt`，每行一个节点，统一 `IP:端口#地区码`：

```
132.226.157.11:443#US
193.108.112.65:443#AL
157.22.240.45:8443#AR
```

合并去重（同组内按 HTTP 延迟，HTTP 关闭回退 TCP）后按地区码升序输出，跨组按 `ip:port` 去重
兼容解析：干净标签、emoji 国旗富标签、竖线分段、空格分隔、纯 IP（默认 443 端口）、CSV 列位、分组 JSON

## 💻 本地运行

零第三方依赖，Python 3.8+ 直接跑（`Start.py` 与解析模块 `SourceParse.py` 需在同一目录）：

```bash
python Start.py
```

常用参数在脚本头部常量区，自己看代码，不多做介绍。

## 🤖 GitHub Actions

仓库自带 [`.github/workflows/run.yml`](.github/workflows/run.yml)：

- ⏰ 每小时自动运行一次（UTC 错峰），支持手动触发
- 💾 运行结束自动提交 `Senflare-Proxy.txt` 与地区缓存回仓库
- 🔁 带 concurrency 防重入，无变化跳过提交

## 🙏 致谢

数据均来自各位作者的持续验证与分享，感谢。
