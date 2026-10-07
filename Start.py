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
import subprocess
import sys
import time
import urllib.request
import urllib.error
from collections import OrderedDict, Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from SourceParse import parse_source

# 控制台输出统一为 UTF-8
for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        _stream.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# 一、配置列表
# ============================================================================

# —— 数据源 ——
SOURCES = {
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

# —— P3 CF 内判定（OTC 引擎 Worker 真实 connect，探测点固定在 Cloudflare）——
P3_BATCH_URL = 'https://check.proxyip.zzzzzz.hidns.vip/?ip={ips}'  # OTC 批量接口，逗号分隔；同一引擎也提供 /check?proxyip= 单节点版
P3_BATCH = 25         # 单次请求的 IP 数：源码无数量限制，但单请求有约 60s 墙钟，超预算的探测被静默标成无效（实测 n>=50 开始丢，n=100 丢 44/100），25 可复现不丢
P3_PARALLEL = 8       # 并发批量数（实测 8 已饱和：200 节点 26s，20 并发无增益）
P3_TIMEOUT = 90       # 单次批量请求超时（秒）
P3_FALLBACK_API = 'https://api.090227.xyz/check'  # 备用单节点接口（Cmliu），主接口整体不可用时逐个回落
P3_FALLBACK_TIMEOUT = 30

# —— 地区补全：ipinfo lite ——
REGION_API = 'https://api.ipinfo.io/lite/{ip}?token=2cb674df499388'
REGION_CACHE_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Country.json')  # 本地缓存：ip → 国家代码
REGION_CACHE_MAX = 10000   # 缓存条数上限
REGION_WORKERS = 32        # 地区查询并发线程数
REGION_TIMEOUT = 5         # 单次查询超时（秒）

OUTPUT_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy.txt')
ALL_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy-All.txt')  # 历史采集总库：所有从源采集过的节点,累积去重
INVALID_FILE = os.path.join(_SCRIPT_DIR, 'Senflare-Proxy-Invalid.txt')  # CF 内判定连续无效的节点：同一节点连续 DEAD_ROUNDS 轮无效才拉黑，未满轮数照常复测
DEAD_ROUNDS = 3        # 连续几轮判定无效才拉黑（1 = 旧行为，抖动一次就永久出局）
PROGRESS_INTERVAL = 1     # 进度打印刷新间隔（秒）
TEST_LIMIT = 0            # 试跑：每源只取前 N 个（0 = 全量）


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
    """拉取全部数据源 → 归一化 → 按 ip:port 去重 返回节点列表
    两组源已合并为 SOURCES：判定改为 CF 内统一判定后，"免测/待测"不再影响任何行为"""
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

    nodes = fetch_group(SOURCES)
    print(f'\n📊 去重后共 {fmt(len(nodes))} 个节点')
    return nodes


# ============================================================================
# 三、CF 内判定（OTC 引擎 Worker 真实 connect，探测点固定在 Cloudflare）
# ============================================================================

def parse_ms(text):
    """OTC 返回的响应时间（'5ms' / '1.2s'）→ 毫秒；解析不了返回 0"""
    try:
        v = str(text).strip()
        if v.endswith('ms'):
            return float(v[:-2])
        if v.endswith('s'):
            return float(v[:-1]) * 1000
    except (ValueError, TypeError):
        pass
    return 0.0


def p3_probe_batch(batch):
    """单次批量请求 → {addr: (有效, 延迟ms, 原因)}；返回条数可能少于请求数（墙钟截断），由调用方核对
    必须走 curl 子进程：该接口挂在 CF 机器人防护后，urllib 一律 403"""
    url = P3_BATCH_URL.format(ips=','.join(batch))
    raw = subprocess.run(['curl', '-s', '--max-time', str(P3_TIMEOUT), url],
                         capture_output=True).stdout
    try:
        data = json.loads(raw.decode('utf-8', 'ignore'))
    except Exception:
        return None
    if not isinstance(data, list):
        return None
    return {d['目标']: (d.get('有效ProxyIP') is True, parse_ms(d.get('响应时间')),
                        str(d.get('失败原因', '')))
            for d in data if isinstance(d, dict) and d.get('目标')}


def p3_check(addrs):
    """全量 CF 内判定：切 P3_BATCH 一批、并发 P3_PARALLEL 路；整批失败或被截断的逐个回落 Cmliu
    返回 {addr: (有效, 延迟ms, 原因)}"""
    batches = [addrs[i:i + P3_BATCH] for i in range(0, len(addrs), P3_BATCH)]
    print(f'\n🧭 ── CF 内判定 ── {fmt(len(addrs))} 个节点 · OTC 批量 {P3_BATCH}/次 · '
          f'并发 {P3_PARALLEL} · 共 {len(batches)} 批')
    out, done, last = {}, 0, time.time()

    def work(batch):
        got = p3_probe_batch(batch)
        if got is None or len(got) != len(batch):   # 整体失败或被约 60s 墙钟截断 → 不能信，逐个回落
            fb = {a: p3_check_fallback(a) for a in batch}
            return {a: (*(fb[a] or (False, '主接口与备用接口均无结果')), 0.0) for a in batch}
        return {a: got.get(a, (False, 0.0, '批量接口漏返')) for a in batch}

    with ThreadPoolExecutor(P3_PARALLEL) as pool:
        for batch, res in zip(batches, pool.map(work, batches)):
            out.update(res)
            done += len(batch)
            now = time.time()
            if now - last >= PROGRESS_INTERVAL:
                print(f'\r⏳ 判定进度 {fmt(done)}/{fmt(len(addrs))} · '
                      f'有效 {fmt(sum(1 for v in out.values() if v[0]))}   ', end='', flush=True)
                last = now
    print(f'\n✅ 判定完成 · 有效 {fmt(sum(1 for v in out.values() if v[0]))} / {fmt(len(addrs))}')
    return out


def p3_check_fallback(addr):
    """备用单节点检测：Cmliu 接口 success 字段判有效 返回 (有效, 原因)，无法判定返回 None"""
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

def load_dead_list(lines=None):
    """筛出已拉黑的死单:同一节点连续 DEAD_ROUNDS 轮双探针全挂才入选,未满轮数本轮照常复测
    lines 为 None 时读 Invalid 文件。write_class_files 每轮给每个死单只写一行,
    故行数即连续无效轮数;节点某轮判定通过后不再写入,计数自然清零
    """
    if lines is None:
        lines = [l.strip() for l in open(INVALID_FILE, encoding='utf-8')] if os.path.exists(INVALID_FILE) else []
    counter, latest = Counter(), {}
    for l in lines:
        if l:
            addr = node_addr(l)
            counter[addr] += 1
            latest.setdefault(addr, l)
    return {a: l for a, l in latest.items() if counter[a] >= DEAD_ROUNDS}


def write_class_files(probed, dead):
    """按 CF 内判定结果落盘分类文件；Invalid 每轮给已拉黑节点续写一行（维持连续无效轮数）
    Bidirectional = 判定通过 = 该节点确实在转发到 Cloudflare，对所有用户一致可用
    Invalid = 判定不通过 = CF 内连不通；连续 DEAD_ROUNDS 轮才拉黑，未满轮数下轮照常复测
    返回 (本轮计数, Invalid 总行数)"""
    groups = {t: [] for t in ('Bidirectional', 'Invalid')}
    cnt = Counter()
    for node, ok, _lat, _reason in probed:
        tag = 'Bidirectional' if ok else 'Invalid'
        cnt[tag] += 1
        groups[tag].append(node)
    groups['Invalid'] += list(dead.values())   # 已拉黑节点续写，保住轮数不被清零
    for t, nodes in groups.items():            # 与主产物一致，按地区码升序
        nodes.sort(key=lambda l: (l.rpartition('#')[2], l))
        with open(os.path.join(_SCRIPT_DIR, f'Senflare-Proxy-{t}.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(nodes) + '\n' if nodes else '')
    return cnt, len(groups['Invalid'])


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
        print(f'\n🧪 试跑模式：每个源只取前 {fmt(TEST_LIMIT)} 个节点\n')

    nodes = load_nodes()

    # 剔除 Cloudflare 官方网段（判定前清掉，省判定算力）
    before = len(nodes)
    nodes = [n for n in nodes if not is_cf_ip(n.rpartition('#')[0].rpartition(':')[0])]
    if before - len(nodes):
        print(f'🧹 Cloudflare 官方网段剔除 {fmt(before - len(nodes))} 个节点')

    if TEST_LIMIT > 0:
        nodes = nodes[:TEST_LIMIT * len(SOURCES)]

    # 历史采集总库:本轮采集到的节点全部累积
    all_new, all_total = update_all_file(nodes)

    # CF 内统一判定:探测点固定在 Cloudflare,结论对所有用户一致
    dead = load_dead_list()          # 连续 DEAD_ROUNDS 轮判定无效的节点本轮整批跳过
    todo = [n for n in nodes if node_addr(n) not in dead]
    if len(nodes) - len(todo):
        print(f'⏭️ 死单跳过 {fmt(len(nodes) - len(todo))} 个（连续 {DEAD_ROUNDS} 轮无效已拉黑）')
    verdict = p3_check([node_addr(n) for n in todo])
    probed = [(n, *verdict[node_addr(n)]) for n in todo]
    cnt, dead_total = write_class_files(probed, dead)

    # 主产物门槛 = 判定通过,按 CF 内响应时间升序
    passed = sorted((r for r in probed if r[1]), key=lambda r: r[2] or float('inf'))
    final_nodes = ensure_regions([r[0] for r in passed])
    if not final_nodes:
        print('❌ 没有任何判定通过的节点，退出')
        sys.exit(1)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_nodes) + '\n')

    print(f'\n💾 已写入 {OUTPUT_FILE}：{fmt(len(final_nodes))} 个判定通过的节点')
    print(f'🧭 分类:{dict(cnt)} · Invalid 在册 {fmt(dead_total)}（满 {DEAD_ROUNDS} 轮无效才拉黑）')
    print(f'📚 采集总库:本轮 {fmt(all_new)} · 累计 {fmt(all_total)} → {ALL_FILE}')
    print(f'\n🎉 全部完成 · 耗时 {time.time() - started:.0f} 秒')


if __name__ == '__main__':
    # 自检：未满 DEAD_ROUNDS 的节点不进死单（下轮照常复测），满轮数才拉黑
    probe = ['1.1.1.1:443#US', '2.2.2.2:443#US']
    assert not load_dead_list(probe * (DEAD_ROUNDS - 1)), '未满轮数不应拉黑'
    assert len(load_dead_list(probe * DEAD_ROUNDS)) == 2, '满轮数应拉黑'
    # 自检：响应时间解析
    assert (parse_ms('5ms'), parse_ms('1.2s'), parse_ms('x')) == (5.0, 1200.0, 0.0)
    main()
