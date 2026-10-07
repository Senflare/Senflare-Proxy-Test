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
import ssl
import sys
import time
import http.client
import urllib.request
import urllib.error
from collections import OrderedDict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, quote

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

P1_ENABLED = True  # P1 真 CF 验证开关（关闭时漏斗组不设门槛，直接进主产物）
P1_METHOD = 'HEAD' # HEAD 或 GET
P1_TIMEOUT = 3     # 单次 HTTP 响应超时（秒）
P1_SAMPLES = 3   # HTTP 延迟采样次数
P1_WORKERS = 100   # HTTP 并发线程数

# —— P2 入口探测 + P3 反代检测（主:OTC 引擎 API / 备:Cmliu 检测接口）——
P2_TIMEOUT = 4         # P2 单次探测超时（秒）
P2_SNI = 'www.cloudflare.com'   # 入口探测的 SNI/Host 域名
P3_API = 'https://api.ytb1.dns-dynamic.net/check'  # P3 主检测接口（引擎直连 公共 API 逐个调用保持克制）
P3_FALLBACK_API = 'https://api.090227.xyz/check'  # P3 备用检测接口（Cmliu,主接口未判有效时回落）
P3_TIMEOUT = 120          # P3 主接口单次请求超时（秒）
P3_FALLBACK_TIMEOUT = 30  # P3 备用接口单次请求超时（秒）
P3_DELAY = 3              # 相邻两次请求间隔（秒）
P3_RETRIES = 2            # 单节点重试次数
TLS_CTX = ssl.create_default_context()
TLS_CTX.check_hostname = False
TLS_CTX.verify_mode = ssl.CERT_NONE

# —— 地区补全：ipinfo lite ——
REGION_API = 'https://api.ipinfo.io/lite/{ip}?token=2cb674df499388'
REGION_CACHE_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Country.json')  # 本地缓存：ip → 国家代码
REGION_CACHE_MAX = 10000   # 缓存条数上限
REGION_WORKERS = 32        # 地区查询并发线程数
REGION_TIMEOUT = 5         # 单次查询超时（秒）

OUTPUT_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy.txt')
ALL_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy-All.txt')  # 历史采集总库：所有从源采集过的节点,累积去重
INVALID_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy-Invalid.txt')  # 无效死单（累积）：记忆双探针全挂的节点,下轮跳过探测
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


def node_addr(line):
    """任意节点行(可带地区与标签)→ ip:port"""
    return line.split(' [')[0].strip().rpartition('#')[0].strip()

def fetch_text(url, timeout=FETCH_TIMEOUT):
    """拉取数据源文本"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', 'ignore')


def load_nodes():
    """拉取两组源 → 归一化 → 按 ip:port 去重（待测组跳过免测组已有 IP） 返回 (direct_nodes, test_nodes)"""
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
# 三、三分类探测(P1 真 CF 验证 + P2 入口透传)
# ============================================================================

def recv_all(sock):
    """读到对端关闭或超时,返回完整响应"""
    sock.settimeout(P2_TIMEOUT)
    data = b''
    try:
        while len(data) < 8192:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    return data


def probe_forward(ip, port):
    """P2 入口探测:TLS+SNI 透传,响应带 cf-ray 即达 CF 边缘(不看状态码)"""
    try:
        with socket.create_connection((ip, int(port)), timeout=P2_TIMEOUT) as s:
            with TLS_CTX.wrap_socket(s, server_hostname=P2_SNI) as t:
                t.sendall(f'HEAD /cdn-cgi/trace HTTP/1.1\r\nHost: {P2_SNI}\r\nConnection: close\r\n\r\n'.encode())
                return b'cf-ray' in recv_all(t).lower()
    except Exception:
        return False


UA_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}


def check_http(node):
    """P1 出口探测：http://ip:port/cdn-cgi/trace 返回 400 且 server 以 cloudflare 开头才算真 CF 返回 (node, 通过, 平均延迟ms, 抖动ms)"""
    host, _, port = node_addr(node).rpartition(':')
    rounds = max(3, P1_SAMPLES)
    latencies = []
    for _ in range(rounds):
        conn = http.client.HTTPConnection(host.strip('[]'), int(port), timeout=P1_TIMEOUT)
        try:
            start = time.time()
            conn.request(P1_METHOD, '/cdn-cgi/trace', headers=UA_HEADERS)
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


def run_probe_tests(nodes):
    """单遍 P1×P2 探测：P1 真 CF 验证（三采样）+ P2 入口透传 返回 [(node, p1_ok, avg, jitter, p2_ok)]"""
    total = len(nodes)
    done, last_print = 0, time.time()
    results, p1_ok_n = [], 0
    print(f'\n🧭 ── 三分类探测 ── {fmt(total)} 个节点 · '
          f'P1 {P1_METHOD} /cdn-cgi/trace 采样 {max(3, P1_SAMPLES)} 次 · P2 TLS+SNI · 并发 {P1_WORKERS}')

    def work(node):
        if P1_ENABLED:
            _, p1, avg, jitter = check_http(node)
        else:
            p1, avg, jitter = True, 0.0, 0.0
        host, _, port = node_addr(node).rpartition(':')
        return node, p1, avg, jitter, probe_forward(host.strip('[]'), port)

    with ThreadPoolExecutor(max_workers=P1_WORKERS) as pool:
        futures = {pool.submit(work, n): n for n in nodes}
        for fut in as_completed(futures):
            node, p1, avg, jitter, p2 = fut.result()
            results.append((node, p1, avg, jitter, p2))
            p1_ok_n += p1
            done += 1
            now = time.time()
            if now - last_print >= PROGRESS_INTERVAL or done == total:
                print(f'\r⏳ 探测进度 {fmt(done)}/{fmt(total)} · P1 通过 {fmt(p1_ok_n)}   ',
                      end='', flush=True)
                last_print = now
    print(f'\n✅ 探测完成 · P1 通过 {fmt(p1_ok_n)} / {fmt(total)}')
    return results


def p3_check(addrs):
    """P3 反代检测:逐个直连 OTC 引擎 API(Worker 内真连接验证) 返回 {addr: (是否有效, 失败原因)},流水线不自动调用,手动用"""
    out, headers = {}, {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    total = len(addrs)
    for i, addr in enumerate(addrs, 1):
        url = f'{P3_API}?proxyip={quote(addr, safe=":,.[]")}'
        data = None
        for attempt in range(1, P3_RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=P3_TIMEOUT) as r:
                    data = json.loads(r.read().decode('utf-8'))
                break
            except Exception as e:
                if attempt == P3_RETRIES:
                    print(f'\n⚠️ P3 检测失败({addr}):{e}')
                else:
                    time.sleep(P3_DELAY)
        if isinstance(data, dict):
            ok = data.get('有效ProxyIP', data.get('有效代理IP'))
            ok, reason = ok is True, str(data.get('失败原因', ''))
        else:
            ok, reason = False, '无返回结果'
        if not ok:                       # 主接口未判有效 → Cmliu 备用接口回落
            fb = p3_check_fallback(addr)
            if fb is not None:
                ok, reason = fb
        out[addr] = (ok, reason)
        print(f'\r⏳ P3 检测 {i}/{total} · 有效 {sum(1 for v in out.values() if v[0])}   ', end='', flush=True)
        time.sleep(P3_DELAY)
    print()
    return out


def p3_check_fallback(addr):
    """P3 备用检测:Cmliu 接口 success 字段判有效 返回 (有效, 原因),无法判定返回 None"""
    try:
        qs = urlencode({'proxyip': addr})
        req = urllib.request.Request(f'{P3_FALLBACK_API}?{qs}',
                                     headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=P3_FALLBACK_TIMEOUT) as r:
            data = json.loads(r.read().decode('utf-8', 'ignore'))
        if isinstance(data, dict) and isinstance(data.get('success'), bool):
            reason = ''
            if not data['success']:
                probes = data.get('probe_results') or {}
                probe = probes.get('ipv4') or probes.get('ipv6') or {}
                reason = str(probe.get('error', '') or '备用接口未通过')
            return data['success'], reason
    except Exception:
        pass
    return None


# ============================================================================
# 四、地区补全（缓存优先 → 接口查询，纯 IP 节点在这里统一格式）
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
    """查询 ipinfo → 国家码 限流（429）抛 RegionRateLimited"""
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


def ensure_regions(nodes):
    """地区补全：带地区码的跳过，缺的查缓存 → 接口 补不到的剔除，限流的保留待下轮"""
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
            host = result[i].rpartition('#')[0].rpartition(':')[0]
            try:
                return i, query_ipinfo(host)
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
# 五、输出
# ============================================================================

def load_dead_list():
    """读 Invalid 文件作为死单记忆:双探针全挂过的节点,下轮整批跳过探测"""
    dead = {}
    if os.path.exists(INVALID_FILE):
        for l in open(INVALID_FILE, encoding='utf-8'):
            l = l.strip()
            if l:
                dead.setdefault(node_addr(l), l)
    # ponytail: 死单永久拉黑不复测;网络抖动误杀需人工清理 Invalid 文件,要自动冷却再加
    return dead


def write_class_files(probed, dead):
    """P1×P2 矩阵落盘四个分类文件,Invalid 累积历史死单;返回 (本轮计数, 死单累计)"""
    # Senflare-Proxy-Bidirectional.txt 双向代理(入口出口都行) / Forward.txt 正向代理(仅入口)
    # Senflare-Proxy-Reverse.txt 反向代理(仅出口) / Invalid.txt 无效淘汰(累积死单,下轮跳过探测)
    files = {t: open(os.path.join(_SCRIPT_DIR, f'Senflare-Proxy-{t}.txt'), 'w', encoding='utf-8')
             for t in ('Forward', 'Reverse', 'Bidirectional', 'Invalid')}
    cnt = Counter()
    for node, p1, _, _, p2 in probed:
        tag = 'Bidirectional' if p1 and p2 else 'Reverse' if p1 else 'Forward' if p2 else 'Invalid'
        cnt[tag] += 1
        files[tag].write(f'{node}\n')
    for line in dead.values():               # 历史死单原样并入 Invalid
        files['Invalid'].write(f'{line}\n')
    for f in files.values():
        f.close()
    return cnt, len(dead) + sum(1 for r in probed if not r[1] and not r[4])


def update_all_file(nodes):
    """历史采集总库：本轮采集的全部节点累积进去,按 ip:port 去重、地区排序 返回 (本轮数, 累计数)"""
    merged = {}
    if os.path.exists(ALL_FILE):
        for l in open(ALL_FILE, encoding='utf-8'):
            l = l.strip()
            if l:
                merged.setdefault(node_addr(l), l)
    for n in nodes:
        merged.setdefault(node_addr(n), n)
    # ponytail: 只增不减,不清理长期失效节点 文件过大时再加老化策略
    with open(ALL_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(merged.values(), key=lambda l: (l.rpartition('#')[2], l))) + '\n')
    return len(nodes), len(merged)


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

    # 历史采集总库:采集过的节点(免测+待测)全部累积
    all_new, all_total = update_all_file(direct_nodes + test_nodes)

    # 单遍 P1×P2 探测:免测组同样参与分类,但其结果只作标记、不设主产物门槛
    dead = load_dead_list()                  # 死单记忆:双探针全挂过的节点本轮整批跳过
    skip = sum(1 for n in direct_nodes + test_nodes if node_addr(n) in dead)
    if skip:
        print(f'⏭️ 死单跳过 {fmt(skip)} 个(历史无效节点不再探测)')
    probed = run_probe_tests([n for n in direct_nodes + test_nodes if node_addr(n) not in dead])
    direct_keys = {node_addr(n) for n in direct_nodes}
    cnt, dead_total = write_class_files(probed, dead)

    # 主产物门槛:免测组全收,漏斗组须 P1 或 P2 通过(三种代理全收,仅剔除双探针全挂的)
    direct_nodes = ensure_regions(direct_nodes)
    test_passed = [r for r in probed if node_addr(r[0]) not in direct_keys and (r[1] or r[4])]
    meta = {node_addr(r[0]): (r[2], r[3]) for r in test_passed}
    filled = ensure_regions([r[0] for r in test_passed])
    test_final = [(n,) + meta[node_addr(n)] for n in filled]

    if not direct_nodes and not test_final:
        print('❌ 没有任何有效节点，退出')
        sys.exit(1)

    # 合并输出：免测组在前，测试组按延迟升序 去重兜底
    test_final.sort(key=lambda x: x[1] if x[1] > 0 else float('inf'))
    final_seen, final_nodes = set(), []
    dup = 0
    for node in direct_nodes + [p[0] for p in test_final]:
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
          f'测试通过 {fmt(len(test_final))} = 合并 {fmt(len(final_nodes))} 个')
    print(f'🧭 三分类:{dict(cnt)} · 死单累计 {fmt(dead_total)}')
    print(f'📚 采集总库:本轮 {fmt(all_new)} · 累计 {fmt(all_total)} → {ALL_FILE}')
    print(f'\n🎉 全部完成 · 耗时 {time.time() - started:.0f} 秒')


if __name__ == '__main__':
    main()
