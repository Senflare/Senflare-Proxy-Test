# Senflare Proxy Test

Senflare Proxy Test —— Cloudflare ProxyIP 聚合 / 测试脚本 —— 多源汇聚, GitHub Actions 每 6 小时自动更新结果


🌐 **主站**：<https://proxy.seeck.cn/> ｜ **备用**：<https://proxy-vercel.seeck.cn/>


## ✨ 工作流程

```
拉取多源（10 源） → 全局去重 → 剔除 Cloudflare 官方网段
  └─ 全量节点 → 读失败总表（全部跳过，每轮随机抽 500 个复测）→ A×B 四格判定
        ├─ 判定通过（A∨B）：汇入主产物
        └─ 判定不通过：记 Invalid 总表（只增；通过复测即移除）
主产物 → 地区补全 → Senflare-Proxy.txt
```

| 层 | 说明 |
|---|---|
| CF 内统一判定 | OTC 引擎 Worker 在 Cloudflare 内真实 `connect()` 节点并完成 TLS 握手，拿到 CF 边缘响应才算通过（批量接口，curl，8 并发 × 25/次）。**探测点固定在 CF，结论对所有用户一致可复现** —— 外部探针做不到，它的结论只对探测者那个网络成立 |
| 地区补全 | 无地区码的节点调 [ipinfo.io lite](https://ipinfo.io) 补齐 本地 LRU 缓存 1 万条，重复 IP 不重复查询 |

判定依据与正反向的定义见 [`代理分类与测试.md`](代理分类与测试.md)。拉取主走 raw 直链（推送即生效），jsDelivr 仅作备用；源配置与格式解析（`SourceParse.py`）、判定与终审全部在 `Start.py`。

## 📡 数据来源

[Xiaobei09](https://github.com/Xiaobei09) · [Cmliu](https://github.com/cmliu) · [Wentao883](https://github.com/wentao883) · [ChatBotPlus](https://github.com/ChatBotPlus) · [Ymyuuu](https://github.com/ymyuuu) · [Mountain787](https://github.com/mountain787) · [Fangsia Karlina](https://github.com/papapapapdelesia) · [Xgonce](https://github.com/xgonce) · [Lzj](https://github.com/wanwushequ/cfyxip) · [wan828963-code](https://github.com/wan828963-code/best-cf-ips) · [alphaxzj](https://github.com/alphaxzj/bestcf) · [rxsweet](https://github.com/rxsweet/cfip) · [liyan1972](https://github.com/liyan1972/proxyip-fetcher) · [NiREvil/vless](https://github.com/NiREvil/vless) · [avotcorg](https://github.com/avotcorg/proxy)

## 📤 输出格式

`Senflare-Proxy.txt`，每行一个节点，统一 `IP:端口#地区码`：

```
132.226.157.11:443#US
193.108.112.65:443#AL
157.22.240.45:8443#AR
```

判定通过后按 CF 内响应时间升序，再按地区码升序输出
兼容解析：干净标签、emoji 国旗富标签、竖线分段、空格分隔、纯 IP（默认 443 端口）、CSV 列位、分组 JSON

分类产物（判定方案详见 [代理分类与测试.md](代理分类与测试.md)）：

- `Senflare-Proxy-Bidirectional.txt`（判定通过）：OTC 引擎在 Cloudflare 内真实 connect 该节点并拿到 CF 边缘响应。探测点固定在 CF，所以结论对所有用户一致可复现 —— 入口与 Worker 出口是同一条透传链路，双向都能站
- `Senflare-Proxy-Invalid.txt`（失败总表）：所有判定无效的节点累积于此；每轮随机抽 500 个复测，通过的移除并救回分类/主产物（删行也可人工移除）
- `Senflare-Proxy-All.txt`：历史采集总库——从各源采集过的节点全部累积（含判定未通过的），按 `ip:port` 去重、只增不减

## 💻 本地运行

零第三方依赖，Python 3.8+ 直接跑（`Start.py` 与解析模块 `SourceParse.py` 需在同一目录）。判定走 OTC 批量接口，脚本内部调 `curl` 子进程（该接口挂在 CF 机器人防护后，`urllib` 会被 403），所以系统需有 curl：

```bash
python Start.py
```

常用参数在脚本头部常量区，自己看代码，不多做介绍。

## 🤖 GitHub Actions

仓库自带 [`.github/workflows/run.yml`](.github/workflows/run.yml)：

- ⏰ 每 6 小时自动运行一次（UTC 00/06/12/18:23 = 北京 08/14/20/次日 02:23），支持手动触发
- ⏱️ 单轮约 70 分钟（3.2 万节点 × 8 并发批量判定），workflow 超时设 90 分钟。GitHub 的 schedule 是尽力而为队列，实际启动时刻可能延后
- 💾 运行结束自动提交 `Senflare-Proxy.txt`、地区缓存与分类文件回仓库
- 🔁 带 concurrency 防重入，无变化跳过提交；运行期间有人推代码则 rebase 后再推

## 🙏 致谢

数据均来自各位作者的持续验证与分享，感谢。
