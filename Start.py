#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Senflare Proxy Test —— Cloudflare ProxyIP 聚合 / 测试脚本 —— 多源汇聚

标准库，Python 3.8+。
"""

import io
import ipaddress
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

from SourceParse import parse_source

# 控制台输出统一为 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        _stream.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# 一、配置列表
# ============================================================================

# —— 免测数据 ——
DIRECT_SOURCES = {
    # 项目作者：Xiaobei09
    # 项目地址：https://github.com/Xiaobei09/proxyip
    # 项目来源：Cmliu（zip.cm.edu.kg/all.txt）/ Wentao883（TG-wxgqlfx_ZBDW）/ ChatBotPlus（cf-proxyips）/ Ymyuuu（IPDB BestProxy）/ Mountain787（Lunch-Bag-ip）
    'Xiaobei': {
        'url': 'https://raw.githubusercontent.com/Xiaobei09/proxyip/refs/heads/main/data/valid/all.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/Xiaobei09/proxyip@main/data/valid/all.txt',
    },
    # 项目作者：Fangsia Karlina
    # 项目地址：https://github.com/papapapapdelesia/Emilia
    'Fangsia Karlina': {
        'url': 'https://raw.githubusercontent.com/papapapapdelesia/Emilia/refs/heads/main/Data/alive.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/papapapapdelesia/Emilia@main/Data/alive.txt',
        'columns': (0, 1, 2, False),
    },
}

# —— 待测数据 ——
TEST_SOURCES = {
    # 项目作者：Xgonce
    # 项目地址：https://github.com/xgonce/Cloudflare_IP
    'Xgonce': {
        'url': 'https://raw.githubusercontent.com/xgonce/Cloudflare_IP/refs/heads/main/result.csv',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/xgonce/Cloudflare_IP@main/result.csv',
        'columns': (0, 2, 4, True),
    },
    # 项目作者：Lzj（辣子鸡）
    # 项目地址：https://github.com/wanwushequ/cfyxip
    'Lzj': {
        'url': 'https://raw.githubusercontent.com/wanwushequ/cfyxip/refs/heads/main/lzj/all.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/wanwushequ/cfyxip@main/lzj/all.txt',
    },
    # 项目作者：Wan828963-code
    # 项目地址：https://github.com/wan828963-code/best-cf-ips
    'Wan828963-code': {
        'url': 'https://raw.githubusercontent.com/wan828963-code/best-cf-ips/refs/heads/main/best-cf-ipv4.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/wan828963-code/best-cf-ips@main/best-cf-ipv4.txt',
    },
    # 项目作者：Alphaxzj
    # 项目地址：https://github.com/alphaxzj/bestcf
    'Alphaxzj': {
        'url': 'https://raw.githubusercontent.com/alphaxzj/bestcf/refs/heads/main/ipv4.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/alphaxzj/bestcf@main/ipv4.txt',
    },
    # 项目作者：Rxsweet
    # 项目地址：https://github.com/rxsweet/cfip
    'Rxsweet': {
        'url': 'https://raw.githubusercontent.com/rxsweet/cfip/refs/heads/main/ip/allip.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/rxsweet/cfip@main/ip/allip.txt',
    },
    # 项目作者：Liyan1972
    # 项目地址：https://github.com/liyan1972/proxyip-fetcher
    'Liyan1972': {
        'url': 'https://raw.githubusercontent.com/liyan1972/proxyip-fetcher/refs/heads/main/ProxyIP-asn-ips.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/liyan1972/proxyip-fetcher@main/ProxyIP-asn-ips.txt',
    },
    # 项目作者：NiREvil
    # 项目地址：https://github.com/NiREvil/vless
    # 项目来源：社区扫描聚合快照（02_proxies.csv 全量包含于 03_proxies.txt）
    'NiREvil': {
        'url': 'https://raw.githubusercontent.com/NiREvil/vless/refs/heads/main/sub/country_proxies/03_proxies.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/NiREvil/vless@main/sub/country_proxies/03_proxies.txt',
    },
    # 项目作者：OTC
    # 项目地址：https://github.com/avotcorg/proxy
    'OTC': {
        'url': 'https://raw.githubusercontent.com/avotcorg/proxy/refs/heads/main/ProxyList1.txt',
        'fallbackUrl': 'https://cdn.jsdelivr.net/gh/avotcorg/proxy@main/ProxyList1.txt',
        'columns': (0, 1, 2, False),
    },
}
# 输出/缓存锚定到脚本所在目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FETCH_RETRIES = 5
FETCH_RETRY_DELAY = 2     # 相邻两次拉取之间的等待（秒）
FETCH_TIMEOUT = 10        # 数据源拉取超时（秒）
TIMEOUT = 2.0             # 单次 TCP 连接超时（秒）
TCP_PROBES = 2            # 每个节点 TCP 连接测试次数
MIN_SUCCESS_RATE = 1.0    # TCP 最低成功率阈值
MAX_WORKERS = 200         # TCP 并发线程数

HTTP_TEST_ENABLED = True  # HTTP 二次验证开关
HTTP_TEST_METHOD = 'HEAD' # HEAD 或 GET
HTTP_TEST_TIMEOUT = 3     # 单次 HTTP 响应超时（秒）
HTTP_JITTER_SAMPLES = 3   # HTTP 延迟采样次数
HTTP_TEST_WORKERS = 100   # HTTP 并发线程数

# —— 地区补全：主查询 ipinfo lite，兜底 Cmliu 接口 ——
REGION_API = 'https://api.ipinfo.io/lite/{ip}?token=2cb674df499388'
FALLBACK_CHECK_API = 'https://api.090227.xyz/check'
REGION_CACHE_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Country.json')  # 本地缓存：ip → 国家代码
REGION_CACHE_MAX = 10000   # 缓存条数上限
REGION_WORKERS = 32        # 地区查询并发线程数
REGION_TIMEOUT = 5         # 单次查询超时（秒）

OUTPUT_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy.txt')
PROGRESS_INTERVAL = 1     # 进度打印刷新间隔（秒）
TEST_LIMIT = 0            # 试跑：每组只取前 N 个（0 = 全量）


# ============================================================================
# 二、拉取与解析（格式解析函数在 SourceParse.py 模块）
# ============================================================================

# Cloudflare 官方网段
CF_NETWORKS = [ipaddress.ip_network(n) for n in (
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20', 
    '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13', '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32',
)]

def is_cf_ip(host):
    """主机是否在 Cloudflare 官方网段内"""
    try:
        addr = ipaddress.ip_address(host.strip('[]'))
    except ValueError:
        return False
    return any(addr in net for net in CF_NETWORKS)

def fmt(n):
    """数字千分位格式化，日志更易读"""
    return f'{n:,}'

def fetch_text(url, timeout=FETCH_TIMEOUT):
    """拉取数据源文本"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', 'ignore')


def load_nodes():
    """拉取两组源 → 归一化 → 按 ip:port 去重（待测组跳过免测组已有 IP）；返回 (direct_nodes, test_nodes)"""
    def fetch_group(sources, seen=None):
        seen = seen if seen is not None else set()
        nodes = []
        for name, source in sources.items():
            text = None
            urls = [u for u in (source.get('url'), source.get('fallbackUrl')) if u]
            for url in urls:
                for attempt in range(1, FETCH_RETRIES + 1):
                    try:
                        text = fetch_text(url)
                        break
                    except Exception as e:
                        if attempt < FETCH_RETRIES:
                            print(f'⚠️  [{name}] 第 {attempt} 次拉取失败：{e}，{FETCH_RETRY_DELAY}s 后重试...')
                            time.sleep(FETCH_RETRY_DELAY)
                if text is not None:
                    break
            if text is None:
                print(f'❌ [{name}] 主源+备用共 {len(urls) * FETCH_RETRIES} 次拉取均失败，跳过该源')
                continue

            count = 0
            # 格式解析走 SourceParse 模块
            parsed = parse_source(text, source)
            for node in parsed:
                key = node.rpartition('#')[0]
                if key in seen:
                    continue
                seen.add(key)
                nodes.append(node)
                count += 1
            print(f'🌐 [{name}] 新增 {fmt(count)} 个节点')
        return nodes

    direct_nodes = fetch_group(DIRECT_SOURCES)
    test_nodes = fetch_group(TEST_SOURCES, seen={n.rpartition('#')[0] for n in direct_nodes})
    print(f'\n📊 组内去重后共 {fmt(len(direct_nodes) + len(test_nodes))} 个节点'
          f'（只拉取 {fmt(len(direct_nodes))} · 需测试 {fmt(len(test_nodes))}）')
    return direct_nodes, test_nodes


# ============================================================================
# 三、TCP 连接存活测试
# ============================================================================

def test_tcp(host, port):
    """socket 直连测活：返回 (是否通过, 最小延迟ms)，失败延迟为 inf"""
    min_lat = float('inf')
    success = 0
    for _ in range(TCP_PROBES):
        try:
            start = time.time()
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

    print(f'\n🔌 ── TCP 存活测试 ── {fmt(total)} 个节点 · 超时 {TIMEOUT}s · 并发 {MAX_WORKERS}')
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
# 四、HTTP 真 CF 验证（/cdn-cgi/trace）
# ============================================================================

UA_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}


def check_http(node):
    """http://ip:port/cdn-cgi/trace 返回 400 且 server 以 cloudflare 开头才算真 CF；返回 (node, 通过, 平均延迟ms, 抖动ms)"""
    host, _, port = node.rpartition('#')[0].rpartition(':')
    rounds = max(3, HTTP_JITTER_SAMPLES)
    latencies = []
    for _ in range(rounds):
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
    print(f'\n🛰️  ── HTTP 真 CF 验证 ── {fmt(total)} 个候选 · '
          f'{HTTP_TEST_METHOD} /cdn-cgi/trace · 采样 {max(3, HTTP_JITTER_SAMPLES)} 次 · 并发 {HTTP_TEST_WORKERS}')
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
# 五、地区补全（缓存优先 → 接口查询，纯 IP 节点在这里统一格式）
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


class RegionRateLimited(Exception):
    """ipinfo 限流标记：节点保留，待下轮重试"""

RATE_LIMITED = object()


def query_ipinfo(ip):
    """查询 ipinfo → 国家码；限流（429）抛 RegionRateLimited"""
    url = REGION_API.format(ip=ip)
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=REGION_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8', 'ignore'))
            code = data.get('country_code') or data.get('country') or ''
            return code.upper() if isinstance(code, str) and len(code) == 2 else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RegionRateLimited
            return None
        except Exception:
            continue
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
    """查询入口：ipinfo → 兜底；均失败且因限流则抛 RegionRateLimited"""
    limited = False
    try:
        code = query_ipinfo(host)
        if code:
            return code
    except RegionRateLimited:
        limited = True
    code = query_fallback(host, port)
    if code:
        return code
    if limited:
        raise RegionRateLimited
    return None


def ensure_regions(nodes):
    """地区补全：带地区码的跳过，缺的查缓存 → 接口；补不到的剔除，限流的保留待下轮"""
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
        if code:                       # 缓存命中
            cache.move_to_end(host)
            hits += 1
            result[i] = f'{base}#{code}'
        else:
            pending_idx.append(i)

    queried_ok = failed = limited = 0
    if pending_idx:
        total = len(pending_idx)
        done, last_print = 0, time.time()
        print(f'\n🌍 ── 地区补全 ── 待查 {fmt(total)} 个 · 缓存命中 {fmt(hits)} · '
              f'ipinfo lite · 并发 {REGION_WORKERS}')

        def work(i):
            base = result[i].rpartition('#')[0]
            host, _, port = base.rpartition(':')
            try:
                return i, query_region_api(host, port)
            except RegionRateLimited:
                return i, RATE_LIMITED

        with ThreadPoolExecutor(max_workers=REGION_WORKERS) as pool:
            futures = [pool.submit(work, i) for i in pending_idx]
            for fut in as_completed(futures):
                i, code = fut.result()
                done += 1
                if code is RATE_LIMITED:
                    limited += 1              # 限流：节点原样保留，下轮重试
                elif code:
                    queried_ok += 1
                    base = result[i].rpartition('#')[0]
                    host = base.rpartition(':')[0]
                    result[i] = f'{base}#{code}'
                    cache[host] = code
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
          f'失败剔除 {fmt(failed)} · 限流保留 {fmt(limited)} · 缓存存量 {fmt(len(cache))}')
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

    # 剔除 Cloudflare 官方网段（测试前清掉，省漏斗算力）
    before = len(direct_nodes) + len(test_nodes)
    direct_nodes = [n for n in direct_nodes if not is_cf_ip(n.rpartition('#')[0].rpartition(':')[0])]
    test_nodes = [n for n in test_nodes if not is_cf_ip(n.rpartition('#')[0].rpartition(':')[0])]
    cf_dropped = before - len(direct_nodes) - len(test_nodes)
    if cf_dropped:
        print(f'🧹 Cloudflare 官方网段剔除 {fmt(cf_dropped)} 个节点')

    if TEST_LIMIT > 0:
        direct_nodes = direct_nodes[:TEST_LIMIT]
        test_nodes = test_nodes[:TEST_LIMIT]

    # 待测源走 TCP → HTTP 两层；只拉取组跳过
    passed = []
    if test_nodes:
        alive = run_tcp_tests(test_nodes)
        if not alive:
            print('❌ TCP 测试无存活节点')
        else:
            passed = run_http_tests(alive)

    direct_nodes = ensure_regions(direct_nodes)
    if passed:
        meta = {t[0].rpartition('#')[0]: t[1:] for t in passed}
        filled = ensure_regions([t[0] for t in passed])
        passed = [(n,) + meta[n.rpartition('#')[0]] for n in filled]

    if not direct_nodes and not passed:
        print('❌ 没有任何有效节点，退出')
        sys.exit(1)

    # 合并输出：免测组在前，测试组按延迟升序；去重兜底
    passed.sort(key=lambda x: x[2] if x[2] > 0 else x[1] if x[1] > 0 else float('inf'))
    final_seen, final_nodes = set(), []
    dup = 0
    for node in direct_nodes + [p[0] for p in passed]:
        key = node.rpartition('#')[0]
        if key in final_seen:
            dup += 1
            continue
        final_seen.add(key)
        final_nodes.append(node)
    if dup:
        print(f'🧹 合并去重移除重复节点 {fmt(dup)} 个')

    # 按国家码升序分组，同国内保持原有（来源/延迟）顺序
    final_nodes.sort(key=lambda n: n.rpartition('#')[2])

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_nodes) + '\n')

    print(f'\n💾 已写入 {OUTPUT_FILE}：只拉取 {fmt(len(direct_nodes))} + '
          f'测试通过 {fmt(len(passed))} = 合并 {fmt(len(final_nodes))} 个')
    print(f'\n🎉 全部完成 · 耗时 {time.time() - started:.0f} 秒')


if __name__ == '__main__':
    main()
