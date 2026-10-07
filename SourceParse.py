#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" 数据源解析模块 """

import re

REGION_RE = re.compile(r'[A-Z]{2,3}')
IPV4_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')
DEFAULT_PORT = 443


def valid_host(host):
    """主机是否合法（IPv4 或 IPv6 形态）"""
    return bool(IPV4_RE.match(host) or ':' in host)


def normalize_line(line):
    """格式为 ip:port#Region，非法返回 None，默认端口 443"""
    line = line.strip().lstrip(chr(65279))  # 去 BOM
    if not line:
        return None
    # 兼容空格分隔的 "IP 端口"
    parts = line.split()
    if len(parts) == 2 and parts[1].isdigit():
        line = f'{parts[0]}:{parts[1]}'
    if '#' in line:
        idx = line.find('#')
        ip_port, tag = line[:idx].strip(), line[idx + 1:]
        # 竖线分段标签取首个独立地区码段，无匹配留空
        region = ''
        if '|' in tag:
            for seg in tag.split('|'):
                seg = seg.strip().upper()
                if re.fullmatch(r'[A-Z]{2,3}', seg):
                    region = seg
                    break
        else:            # 其余标签取第一个大写字母段
            m = REGION_RE.search(tag.upper())
            region = m.group(0) if m else ''
    else:
        ip_port, region = line, ''
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
    """按列位解析 CSV → ip:port#Region columns：(IP列, 端口列, 地区码列, 是否跳表头)"""
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
            out.append(f'{ip}:{port}#')  # 地区列非标准代码，留给地区补全
    return out


def parse_source(text, source):
    """按源声明分发解析：columns → CSV，默认逐行"""
    if 'columns' in source:
        return parse_columns(text, *source['columns'])
    return [n for n in map(normalize_line, text.splitlines()) if n]
