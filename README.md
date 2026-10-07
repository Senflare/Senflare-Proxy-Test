# Senflare Proxy Test

Senflare Proxy Test —— Cloudflare ProxyIP 聚合 / 测试脚本 —— 多源汇聚, GitHub Actions 每 6 小时自动更新结果


🌐 **主站**：<https://proxy.seeck.cn/> ｜ **备用**：<https://proxy-vercel.seeck.cn/>


## ✨ 工作流程

```
拉取多源 → 组内去重 → 剔除 Cloudflare 官方网段
  └─ 全量节点 → 读死单记忆（连续 3 轮双挂才跳过探测）→ P1×P2 探测（单遍完成）
        ├─ 免测数据：直接汇入主产物（上游有实测流水线，探测结果仅作分类标记）
        ├─ 漏斗组 P1 或 P2 通过：汇入主产物（按 P1 延迟排序）
        └─ 按 P2 主判据分类 → Senflare-Proxy-Bidirectional / Plaintext / Invalid.txt
主产物 → 地区补全 → 合并去重 → Senflare-Proxy.txt
```

| 层 | 说明 |
|---|---|
| P1 明文探测 | `HEAD /cdn-cgi/trace` 必须返回 400 且 `server: cloudflare*`（CF 的 1003 响应），证明节点真转发到 Cloudflare 三采样计算延迟/抖动（100 并发）附属标记，不参与正反向判定 |
| P2 TLS 探测（分类主判据） | TLS 握手 SNI=www.cloudflare.com，响应带 `cf-ray` 即透传成功。入口与 Worker 出口是同一条透传链路，**P2 通过即双向**；失败再看 P1 分「仅明文」与「探测点不可达」 |
| 地区补全 | 无地区码的节点调 [ipinfo.io lite](https://ipinfo.io) 补齐 本地 LRU 缓存 1 万条，重复 IP 不重复查询 |

拉取主走 raw 直链（推送即生效），jsDelivr 仅作备用 源配置、格式解析（`SourceParse.py`）、探测与终审全部在 `Start.py`。

## 📡 数据来源

[Xiaobei09](https://github.com/Xiaobei09) · [Cmliu](https://github.com/cmliu) · [Wentao883](https://github.com/wentao883) · [ChatBotPlus](https://github.com/ChatBotPlus) · [Ymyuuu](https://github.com/ymyuuu) · [Mountain787](https://github.com/mountain787) · [Fangsia Karlina](https://github.com/papapapapdelesia) · [Xgonce](https://github.com/xgonce) · [Lzj](https://github.com/wanwushequ/cfyxip) · [wan828963-code](https://github.com/wan828963-code/best-cf-ips) · [alphaxzj](https://github.com/alphaxzj/bestcf) · [rxsweet](https://github.com/rxsweet/cfip) · [liyan1972](https://github.com/liyan1972/proxyip-fetcher) · [NiREvil/vless](https://github.com/NiREvil/vless) · [avotcorg](https://github.com/avotcorg/proxy)

## 📤 输出格式

`Senflare-Proxy.txt`，每行一个节点，统一 `IP:端口#地区码`：

```
132.226.157.11:443#US
193.108.112.65:443#AL
157.22.240.45:8443#AR
```

合并去重（同组内按 P1 延迟升序）后按地区码升序输出，跨组按 `ip:port` 去重
兼容解析：干净标签、emoji 国旗富标签、竖线分段、空格分隔、纯 IP（默认 443 端口）、CSV 列位、分组 JSON

分类产物（探测方案详见 [代理分类与测试.md](代理分类与测试.md)）：

- `Senflare-Proxy-Bidirectional.txt`（双向可用）/ `Senflare-Proxy-Plaintext.txt`（仅明文可用）：**P2 通过即双向**——TLS 入口与 Worker 出口是同一条透传链路；P2 失败但 P1 通过的只收明文 HTTP，现代 HTTPS 站点与 Worker 都用不上
- `Senflare-Proxy-Invalid.txt`（探测点不可达）：双探针全挂的节点每轮记一行，行数即连续双挂轮数；连续 3 轮才拉黑跳过探测，节点复活后计数自然清零（删行也可人工降轮数）。**注意这是「从探测点不可达」不是「已死」**——机房 IP 常被反代节点限流，同一节点在住宅网络往往完全正常，详见 `代理分类与测试.md`
- `Senflare-Proxy-All.txt`：历史采集总库——从各源采集过的节点全部累积（含测试未通过的），按 `ip:port` 去重、只增不减

## 💻 本地运行

零第三方依赖，Python 3.8+ 直接跑（`Start.py` 与解析模块 `SourceParse.py` 需在同一目录）：

```bash
python Start.py
```

常用参数在脚本头部常量区，自己看代码，不多做介绍。

## 🤖 GitHub Actions

仓库自带 [`.github/workflows/run.yml`](.github/workflows/run.yml)：

- ⏰ 每 6 小时自动运行一次（UTC 00/06/12/18:23 = 北京 08/14/20/次日 02:23），支持手动触发
- 💾 运行结束自动提交 `Senflare-Proxy.txt`、地区缓存与五个分类文件回仓库
- 🔁 带 concurrency 防重入，无变化跳过提交

## 🙏 致谢

数据均来自各位作者的持续验证与分享，感谢。
