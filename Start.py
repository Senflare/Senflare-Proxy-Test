#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Senflare Proxy Test —— Cloudflare 优选 IP 测试脚本（TCP + HTTP 检测 + 免测汇聚）

流程：拉取多源（纯 IP 也收）→ 组内去重 → 免测源直入 + 其余源走 ① TCP 存活测试 → ② HTTP 真CF验证
     → ③ 地区补全（缓存优先，纯 IP 节点统一格式）→ 合并去重输出 Senflare-Proxy.txt

数据源按「只拉取 / 需测试」分成两组配置。
仅用 Python 标准库，无需安装任何依赖。Python 3.8+。
"""

import re
import io
import json
import os
import socket
import sys
import time
import http.client
import urllib.request
import urllib.error
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

# Windows 控制台默认 GBK 编码，emoji 会直接报 UnicodeEncodeError；
# 统一切到 UTF-8，切不动或写不了时降级为替换字符
for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        _stream.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# 一、配置
# ============================================================================

# —— 只拉取：上游已验证的聚合数据，免测直接汇入结果 ——
DIRECT_SOURCES = {
    # 聚合接口：Xiaobei09 项目把下列上游作者的验证结果汇聚成一个 all.txt
    # 项目地址：https://github.com/Xiaobei09/proxyip ，上游来源：
    #   - Cmliu：https://zip.cm.edu.kg/all.txt
    #   - Wentao883：https://github.com/wentao883/TG-wxgqlfx_ZBDW （fdip.txt / vlid.txt / yxip.txt）
    #   - ChatBotPlus：https://github.com/ChatBotPlus/cf-proxyips （list.txt）
    #   - Ymyuuu：https://github.com/ymyuuu/IPDB （BestProxy 的 proxy.txt 与 bestproxy&country.txt）
    #   - Mountain787：https://github.com/mountain787/Lunch-Bag-ip （proxyip.csv）
    # 拉取走 jsDelivr CDN 加速；原始地址：https://raw.githubusercontent.com/Xiaobei09/proxyip/refs/heads/main/data/valid/all.txt
    'Xiaobei': {
        'url': 'https://cdn.jsdelivr.net/gh/Xiaobei09/proxyip@main/data/valid/all.txt',
    },
    # 作者：Fangsia Karlina —— https://github.com/papapapapdelesia/Emilia （Mayumiwandi/Emilia fork）
    # 格式：CSV 列位 IP,端口,地区码，无表头（与主项目 parseColumns(text, 0, 1, 2, false) 一致）
    'Fangsia Karlina': {
        'url': 'https://cdn.jsdelivr.net/gh/Mayumiwandi/Emilia@main/Data/alive.txt',
        'columns': (0, 1, 2, False),
    },
    # 作者：Xgonce —— https://github.com/xgonce/Cloudflare_IP
    # 格式：CSV 列位 IP,,端口,,,地区码，带表头（与主项目 parseColumns(text, 0, 2, 4, true) 一致）
    'Xgonce': {
        'url': 'https://cdn.jsdelivr.net/gh/xgonce/Cloudflare_IP@main/result.csv',
        'columns': (0, 2, 4, True),
    },
}

# —— 需要测试：拉取后走 ① TCP 存活 → ② HTTP 真CF验证，通过的才汇入结果 ——
TEST_SOURCES = {
    'Xinyitang3': {
        'url': 'https://countrymerge.pages.dev/all.txt',
    },
}

# 输出/缓存统一锚定到脚本所在目录：无论从哪个工作目录启动，文件都落在脚本旁
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PORT = 443        # 不带端口的节点默认使用该端口
FETCH_RETRIES = 2         # 数据源拉取尝试次数
FETCH_TIMEOUT = 10        # 数据源拉取超时（秒）
TIMEOUT = 2.0             # 单次 TCP 连接超时（秒）
TCP_PROBES = 2            # 每个节点 TCP 连接测试次数
MIN_SUCCESS_RATE = 1.0    # TCP 最低成功率阈值（低于此值直接淘汰）
MAX_WORKERS = 300         # TCP 并发线程数

HTTP_TEST_ENABLED = True  # HTTP 二次验证开关
HTTP_TEST_METHOD = 'HEAD' # HEAD 或 GET
HTTP_TEST_TIMEOUT = 3     # 单次 HTTP 响应超时（秒）
HTTP_JITTER_SAMPLES = 3   # HTTP 延迟采样次数（≥3，用于算平均延迟与抖动）
HTTP_TEST_WORKERS = 128   # HTTP 并发线程数（纯 I/O 等待型，可开高；慢死节点 9s/个 是主要拖累）

# —— ③ 地区补全：无地区码的节点在测试后查接口补齐 ——
# 主查询：ipinfo.io lite 免费接口（返回 country_code 字段）
REGION_API = 'https://api.ipinfo.io/lite/{ip}?token=2cb674df499388'
# 兜底：主查询查不到时才启用，注意：该接口是代理可用性检测器，尽量不使用
FALLBACK_CHECK_API = 'https://api.090227.xyz/check'
REGION_CACHE_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Country.json')  # 本地缓存：ip → 国家代码
REGION_CACHE_MAX = 10000   # 缓存最多保留条数（超出淘汰最久未用）
REGION_WORKERS = 32        # 地区查询并发线程数
REGION_TIMEOUT = 5         # 单次查询超时（秒）

OUTPUT_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy.txt')
PROGRESS_INTERVAL = 1     # 进度打印刷新间隔（秒）
TEST_LIMIT = 0            # 🧪 试跑模式：每组只取前 N 个节点走完整流程（0 = 全量）


# ============================================================================
# 二、拉取与解析
# ============================================================================

REGION_RE = re.compile(r'[A-Z]{2,3}')
IPV4_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')


def valid_host(host):
    """主机合法性：IPv4 或含冒号的 IPv6 形态（排除把任意文本当主机）"""
    return bool(IPV4_RE.match(host) or ':' in host)


def fmt(n):
    """数字千分位格式化，日志更易读"""
    return f'{n:,}'


def fetch_text(url, timeout=FETCH_TIMEOUT):
    """拉取数据源文本"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', 'ignore')


def normalize_line(line):
    """
    归一化为 ip:port#Region，主机非法返回 None。
    兼容格式：
      干净标签：1.2.3.4:443#US
      富标签（Xiaobei09 实测格式）：1.2.3.4:443#🇺🇸US-10ms-CF-84-DC-RES-CN-CF-82
      纯 IP 无端口：1.2.3.4#US → 端口默认 DEFAULT_PORT(443)
      纯 IP / 纯 IP:端口（无地区码）→ 保留为 ip:port#，由 ③ 地区补全填充
    有标签时取第一个大写字母段作地区码（国旗后紧跟的 ISO 码）。
    """
    line = line.strip().lstrip(chr(65279))  # 65279 = U+FEFF（BOM）
    if not line:
        return None
    if '#' in line:
        idx = line.find('#')
        ip_port, tag = line[:idx].strip(), line[idx + 1:]
        m = REGION_RE.search(tag.upper())
        region = m.group(0) if m else ''
    else:
        ip_port, region = line, ''
    # 兼容三种形态：ip:port、[IPv6]:port、纯 IP（端口取 DEFAULT_PORT）
    if ':' in ip_port:
        host, _, port = ip_port.rpartition(':')
        if not host or not port.isdigit():
            return None
    else:
        host, port = ip_port, str(DEFAULT_PORT)
    if not valid_host(host.strip('[]')):
        return None
    return f'{host}:{port}#{region}'


def parse_columns(text, ip_idx, port_idx, country_idx, skip_header):
    """
    通用 CSV 列位解析 → ip:port#Region（与主项目 _worker.js 的 parseColumns 一致）。
    columns 元组：(IP列, 端口列, 地区码列, 是否跳表头)。
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip().lstrip(chr(65279))
        if not line:
            continue
        cols = line.split(',')
        if len(cols) <= max(ip_idx, port_idx, country_idx):
            continue
        if skip_header and cols[ip_idx].strip().upper() == 'IP':
            continue
        ip = cols[ip_idx].strip()
        port = cols[port_idx].strip()
        if not valid_host(ip) or not port.isdigit():
            continue
        country = cols[country_idx].strip().upper()
        if re.fullmatch(r'[A-Z]{2,3}', country):
            out.append(f'{ip}:{port}#{country}')
        else:
            out.append(f'{ip}:{port}#')  # 地区列非标准代码，留给 ③ 补全
    return out


def load_nodes():
    """
    拉取两组源 → 归一化 → 各组内按 ip:port 独立去重（保留先出现者）。
    两组数据来源不同、各自去重，跨组重复留给最终合并时统一清理。
    返回 (direct_nodes, test_nodes)
    """
    def fetch_group(sources):
        seen = set()
        nodes = []
        for name, source in sources.items():
            text = None
            for attempt in range(1, FETCH_RETRIES + 1):
                try:
                    text = fetch_text(source['url'])
                    break
                except Exception as e:
                    if attempt < FETCH_RETRIES:
                        print(f'⚠️  [{name}] 第 {attempt} 次拉取失败：{e}，重试中...')
            if text is None:
                print(f'❌ [{name}] 共 {FETCH_RETRIES} 次拉取均失败，跳过该源')
                continue

            count = 0
            # 带 'columns' 的源按 CSV 列位解析，其余按行格式归一化
            if 'columns' in source:
                parsed = parse_columns(text, *source['columns'])
            else:
                parsed = (n for n in map(normalize_line, text.splitlines()) if n)
            for node in parsed:
                key = node.rpartition('#')[0]
                if key not in seen:
                    seen.add(key)
                    nodes.append(node)
                    count += 1
            print(f'🌐 [{name}] 新增 {fmt(count)} 个节点')
        return nodes

    direct_nodes = fetch_group(DIRECT_SOURCES)
    test_nodes = fetch_group(TEST_SOURCES)
    print(f'\n📊 组内去重后共 {fmt(len(direct_nodes) + len(test_nodes))} 个节点'
          f'（只拉取 {fmt(len(direct_nodes))} · 需测试 {fmt(len(test_nodes))}）')
    return direct_nodes, test_nodes


# ============================================================================
# 三、① TCP 连接存活测试
# ============================================================================

def test_tcp(host, port):
    """socket 直连测活：返回 (是否通过, 最小延迟ms)，失败延迟为 inf"""
    min_lat = float('inf')
    success = 0
    for _ in range(TCP_PROBES):
        try:
            start = time.time()
            # create_connection 自动解析 IPv4/IPv6
            with socket.create_connection((host.strip('[]'), int(port)), timeout=TIMEOUT):
                pass
            min_lat = min(min_lat, (time.time() - start) * 1000)
            success += 1
        except Exception:
            continue
    ok = success > 0 and (success / TCP_PROBES) >= MIN_SUCCESS_RATE
    return ok, min_lat


def run_tcp_tests(nodes):
    """全量 TCP 测试，返回通过的 [(node, tcp_latency_ms)]"""
    results = []
    total = len(nodes)
    done, last_print = 0, time.time()

    def work(node):
        host, _, port = node.rpartition('#')[0].rpartition(':')
        ok, lat = test_tcp(host, port)
        return node, ok, lat

    print(f'\n🔌 ── ① TCP 存活测试 ── {fmt(total)} 个节点 · 超时 {TIMEOUT}s · 并发 {MAX_WORKERS}')
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(work, n): n for n in nodes}
        for fut in as_completed(futures):
            node, ok, lat = fut.result()
            done += 1
            if ok:
                results.append((node, lat))
            now = time.time()
            if now - last_print >= PROGRESS_INTERVAL or done == total:
                print(f'\r⏳ TCP 进度 {fmt(done)}/{fmt(total)} · 存活 {fmt(len(results))}   ',
                      end='', flush=True)
                last_print = now
    print(f'\n✅ TCP 完成 · 存活 {fmt(len(results))} / {fmt(total)}')
    return results


# ============================================================================
# 四、② HTTP 真 CF 验证（/cdn-cgi/trace）
# ============================================================================

UA_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}


def check_http(node):
    """
    向 http://ip:port/cdn-cgi/trace 发请求，判定是否真 Cloudflare 边缘：
      状态码必须为 400 且响应头 server 以 cloudflare 开头。
    返回 (node, 是否通过, 平均延迟ms, 抖动ms)
    """
    host, _, port = node.rpartition('#')[0].rpartition(':')
    rounds = max(3, HTTP_JITTER_SAMPLES)
    latencies = []
    for _ in range(rounds):
        # HTTPConnection 不支持 with 语法，用 try/finally 确保连接必关
        conn = http.client.HTTPConnection(host.strip('[]'), int(port), timeout=HTTP_TEST_TIMEOUT)
        try:
            start = time.time()
            conn.request(HTTP_TEST_METHOD, '/cdn-cgi/trace', headers=UA_HEADERS)
            resp = conn.getresponse()
            lat = (time.time() - start) * 1000
            resp.read()
        except Exception:
            return node, False, 0.0, 0.0
        finally:
            conn.close()
        if resp.status != 400:
            return node, False, 0.0, 0.0
        server = resp.getheader('server', '')
        if not server.lower().startswith('cloudflare'):
            return node, False, 0.0, 0.0
        latencies.append(lat)
    avg = sum(latencies) / len(latencies)
    jitter = (sum((x - avg) ** 2 for x in latencies) / len(latencies)) ** 0.5
    return node, True, avg, jitter


def run_http_tests(candidates):
    """对 TCP 存活节点做 HTTP 验证，返回 [(node, tcp_ms, http_ms, jitter_ms)]"""
    if not HTTP_TEST_ENABLED or not candidates:
        return [(n, l, 0.0, 0.0) for n, l in candidates]

    total = len(candidates)
    done, last_print = 0, time.time()
    passed = []
    samples = max(3, HTTP_JITTER_SAMPLES)
    print(f'\n🛰️  ── ② HTTP 真 CF 验证 ── {fmt(total)} 个候选 · '
          f'{HTTP_TEST_METHOD} /cdn-cgi/trace · 采样 {samples} 次 · 并发 {HTTP_TEST_WORKERS}')
    with ThreadPoolExecutor(max_workers=HTTP_TEST_WORKERS) as pool:
        futures = {pool.submit(check_http, n): n for n, _ in candidates}
        tcp_map = dict(candidates)
        for fut in as_completed(futures):
            node, ok, avg, jitter = fut.result()
            done += 1
            if ok:
                passed.append((node, tcp_map[node], avg, jitter))
            now = time.time()
            if now - last_print >= PROGRESS_INTERVAL or done == total:
                print(f'\r⏳ HTTP 进度 {fmt(done)}/{fmt(total)} · 通过 {fmt(len(passed))}   ',
                      end='', flush=True)
                last_print = now
    print(f'\n✅ HTTP 完成 · 通过 {fmt(len(passed))} / {fmt(total)}')
    return passed


# ============================================================================
# 五、③ 地区补全（缓存优先 → 接口查询，纯 IP 节点在这里统一格式）
# ============================================================================

def load_region_cache():
    """读取本地地区缓存（ip → 国家代码），文件缺失或损坏时返回空缓存"""
    try:
        with open(REGION_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return OrderedDict((str(k), str(v)) for k, v in data.items())
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f'⚠️  地区缓存读取失败，按空缓存处理：{e}')
    return OrderedDict()


def save_region_cache(cache):
    """写回地区缓存，超出上限时淘汰最久未用的条目"""
    while len(cache) > REGION_CACHE_MAX:
        cache.popitem(last=False)
    with open(REGION_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


def query_ipinfo(ip):
    """主查询：ipinfo.io lite 免费接口 → ISO 两位国家码"""
    url = REGION_API.format(ip=ip)
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=REGION_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8', 'ignore'))
            code = data.get('country_code') or data.get('country') or ''
            return code.upper() if isinstance(code, str) and len(code) == 2 else None
        except urllib.error.HTTPError:
            return None              # 状态码异常（限流/拒绝），重试无意义
        except Exception:
            continue                 # 网络抖动：再试一次
    return None


def query_fallback(host, port):
    """兜底：Cmliu 代理可用性检测接口 """
    try:
        qs = urlencode({'proxyip': f'{host}:{port}'})
        req = urllib.request.Request(f'{FALLBACK_CHECK_API}?{qs}',
                                     headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=REGION_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8', 'ignore'))
        probes = data.get('probe_results', {})
        probe = probes.get('ipv6') or probes.get('ipv4') or {}
        country = probe.get('exit', {}).get('country', '')
        if isinstance(country, str) and len(country) == 2:
            return country.upper()
    except Exception:
        pass
    return None


def query_region_api(host, port):
    """③ 查询入口"""
    code = query_ipinfo(host)
    if code:
        return code
    return query_fallback(host, port)


def ensure_regions(nodes):
    """
    ③ 地区补全：本身带地区码的节点直接跳过；缺地区的优先查缓存，
    未命中的并发调查询接口；最终拿不到地区的节点剔除（保证输出格式统一）。
    返回补全后的节点列表（保持原顺序）。
    """
    cache = load_region_cache()
    result = list(nodes)
    pending_idx = []
    hits = 0
    for i, node in enumerate(result):
        base, _, region = node.rpartition('#')
        if region:
            continue
        host = base.rpartition(':')[0]
        code = cache.get(host)
        if code:                       # 缓存命中：刷新 LRU 位置并直接填充
            cache.move_to_end(host)
            hits += 1
            result[i] = f'{base}#{code}'
        else:
            pending_idx.append(i)

    queried_ok = failed = 0
    if pending_idx:
        total = len(pending_idx)
        done, last_print = 0, time.time()
        print(f'\n🌍 ── ③ 地区补全 ── 待查 {fmt(total)} 个 · 缓存命中 {fmt(hits)} · '
              f'ipinfo lite · 并发 {REGION_WORKERS}')

        def work(i):
            base = result[i].rpartition('#')[0]
            host, _, port = base.rpartition(':')
            return i, query_region_api(host, port)

        with ThreadPoolExecutor(max_workers=REGION_WORKERS) as pool:
            futures = [pool.submit(work, i) for i in pending_idx]
            for fut in as_completed(futures):
                i, code = fut.result()
                done += 1
                if code:
                    queried_ok += 1
                    base = result[i].rpartition('#')[0]
                    host = base.rpartition(':')[0]
                    result[i] = f'{base}#{code}'
                    cache[host] = code  # 重新插入即刷新 LRU 位置
                else:
                    failed += 1
                    result[i] = None    # 补不到地区的剔除
                now = time.time()
                if now - last_print >= PROGRESS_INTERVAL or done == total:
                    print(f'\r⏳ 地区查询 进度 {fmt(done)}/{fmt(total)} · 成功 {fmt(queried_ok)}   ',
                          end='', flush=True)
                    last_print = now

    if hits or pending_idx:
        save_region_cache(cache)
    kept = [n for n in result if n]
    print(f'\n✅ 地区补全完成 · 缓存命中 {fmt(hits)} · 接口成功 {fmt(queried_ok)} · '
          f'失败剔除 {fmt(failed)} · 缓存存量 {fmt(len(cache))}')
    return kept


# ============================================================================
# 六、输出
# ============================================================================

def main():
    started = time.time()
    print('🚀 Senflare Proxy Test 启动')
    if TEST_LIMIT > 0:
        print(f'\n🧪 试跑模式：每组只取前 {fmt(TEST_LIMIT)} 个节点\n')

    direct_nodes, test_nodes = load_nodes()

    # 试跑模式：拉全量源后截断，只对前 N 个走 测试 → 补全 → 输出
    if TEST_LIMIT > 0:
        direct_nodes = direct_nodes[:TEST_LIMIT]
        test_nodes = test_nodes[:TEST_LIMIT]

    # 待测源走 ①TCP → ②HTTP 两层；只拉取组跳过
    passed = []
    if test_nodes:
        alive = run_tcp_tests(test_nodes)
        if not alive:
            print('❌ TCP 测试无存活节点')
        else:
            passed = run_http_tests(alive)

    # ③ 地区补全：无地区码（纯 IP）的节点查接口补齐，缓存优先，补不上的剔除
    direct_nodes = ensure_regions(direct_nodes)
    if passed:
        meta = {t[0]: t[1:] for t in passed}
        filled = ensure_regions([t[0] for t in passed])
        passed = [(n,) + meta[n] for n in filled]

    if not direct_nodes and not passed:
        print('❌ 没有任何有效节点，退出')
        sys.exit(1)

    # 结果合并：免测聚合数据在前，测试通过的按 HTTP 延迟升序在后；
    # 两组合流后再做一次去重兜底（按 ip:port，保留先出现者）
    passed.sort(key=lambda x: x[2] if x[2] > 0 else float('inf'))
    final_seen = set()
    final_nodes = []
    for node in direct_nodes:
        key = node.rpartition('#')[0]
        if key not in final_seen:
            final_seen.add(key)
            final_nodes.append(node)
    for node, _, _, _ in passed:
        key = node.rpartition('#')[0]
        if key not in final_seen:
            final_seen.add(key)
            final_nodes.append(node)
    dup = len(direct_nodes) + len(passed) - len(final_nodes)
    if dup:
        print(f'🧹 最终合并去重移除重复节点 {dup} 个')

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_nodes) + '\n')

    print(f'\n💾 已写入 {OUTPUT_FILE}：只拉取 {fmt(len(direct_nodes))} + '
          f'测试通过 {fmt(len(passed))} = 合并 {fmt(len(final_nodes))} 个')
    print(f'\n🎉 全部完成 · 耗时 {time.time() - started:.0f} 秒')


if __name__ == '__main__':
    main()
