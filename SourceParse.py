#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" 数据源解析模块 """

import base64
import ipaddress
import json
import re
from urllib.parse import urlsplit, unquote

REGION_RE = re.compile(r'(?<![A-Z])([A-Z]{2,3})(?![A-Z])')
FLAG_RE = re.compile('[\U0001F1E6-\U0001F1FF]{2}')  # 国旗 emoji:两个区域指示符码点
CN_RE = re.compile(r'[\u4e00-\u9fff（）()]+')
DEFAULT_PORT = 443

# 中文国名 → 两位地区码(含常见别名与全/半角括号变体)
COUNTRY_MAP = {
    '阿富汗': 'AF', '奥兰群岛': 'AX', '阿尔巴尼亚': 'AL', '阿尔及利亚': 'DZ',
    '美属萨摩亚': 'AS', '安道尔': 'AD', '安哥拉': 'AO', '安圭拉': 'AI',
    '南极洲': 'AQ', '安提瓜和巴布达': 'AG', '阿根廷': 'AR', '亚美尼亚': 'AM',
    '阿鲁巴': 'AW', '澳大利亚': 'AU', '奥地利': 'AT', '阿塞拜疆': 'AZ',
    '巴哈马': 'BS', '巴林': 'BH', '孟加拉国': 'BD', '孟加拉': 'BD',
    '巴巴多斯': 'BB', '白俄罗斯': 'BY', '比利时': 'BE', '伯利兹': 'BZ',
    '贝宁': 'BJ', '百慕大': 'BM', '不丹': 'BT', '玻利维亚': 'BO',
    '波黑': 'BA', '波斯尼亚和黑塞哥维那': 'BA', '博茨瓦纳': 'BW',
    '布维岛': 'BV', '巴西': 'BR', '英属印度洋领地': 'IO',
    '文莱': 'BN', '保加利亚': 'BG', '布基纳法索': 'BF', '布隆迪': 'BI',
    '柬埔寨': 'KH', '喀麦隆': 'CM', '加拿大': 'CA', '佛得角': 'CV',
    '开曼群岛': 'KY', '中非': 'CF', '乍得': 'TD', '智利': 'CL',
    '中国': 'CN', '圣诞岛': 'CX', '科科斯(基林)群岛': 'CC',
    '哥伦比亚': 'CO', '科摩罗': 'KM', '刚果(布)': 'CG', '刚果(布)': 'CG',
    '刚果(金)': 'CD', '刚果(金)': 'CD', '库克群岛': 'CK',
    '哥斯达黎加': 'CR', '科特迪瓦': 'CI', '克罗地亚': 'HR', '古巴': 'CU',
    '塞浦路斯': 'CY', '捷克': 'CZ', '丹麦': 'DK', '吉布提': 'DJ',
    '多米尼克': 'DM', '多米尼加': 'DO', '厄瓜多尔': 'EC', '埃及': 'EG',
    '萨尔瓦多': 'SV', '赤道几内亚': 'GQ', '厄立特里亚': 'ER',
    '爱沙尼亚': 'EE', '埃塞俄比亚': 'ET', '福克兰群岛(马尔维纳斯)': 'FK',
    '法罗群岛': 'FO', '斐济': 'FJ', '芬兰': 'FI', '法国': 'FR',
    '法属圭亚那': 'GF', '法属波利尼西亚': 'PF', '法属南部领地': 'TF',
    '加蓬': 'GA', '冈比亚': 'GM', '格鲁吉亚': 'GE', '德国': 'DE',
    '加纳': 'GH', '直布罗陀': 'GI', '希腊': 'GR', '格陵兰': 'GL',
    '格林纳达': 'GD', '瓜德罗普': 'GP', '关岛': 'GU', '危地马拉': 'GT',
    '根西岛': 'GG', '几内亚': 'GN', '几内亚比绍': 'GW', '圭亚那': 'GY',
    '海地': 'HT', '赫德岛和麦克唐纳群岛': 'HM', '梵蒂冈': 'VA',
    '洪都拉斯': 'HN', '香港': 'HK', '匈牙利': 'HU', '冰岛': 'IS',
    '印度': 'IN', '印尼': 'ID', '印度尼西亚': 'ID', '伊朗': 'IR', '伊拉克': 'IQ',
    '爱尔兰': 'IE', '马恩岛': 'IM', '以色列': 'IL', '意大利': 'IT',
    '牙买加': 'JM', '日本': 'JP', '泽西岛': 'JE', '约旦': 'JO',
    '哈萨克斯坦': 'KZ', '肯尼亚': 'KE', '基里巴斯': 'KI', '朝鲜': 'KP',
    '韩国': 'KR', '科威特': 'KW', '吉尔吉斯斯坦': 'KG', '老挝': 'LA',
    '拉脱维亚': 'LV', '黎巴嫩': 'LB', '莱索托': 'LS', '利比里亚': 'LR',
    '利比亚': 'LY', '列支敦士登': 'LI', '立陶宛': 'LT', '卢森堡': 'LU',
    '澳门': 'MO', '北马其顿': 'MK', '马其顿': 'MK', '马达加斯加': 'MG',
    '马拉维': 'MW', '马来西亚': 'MY', '马尔代夫': 'MV', '马里': 'ML',
    '马耳他': 'MT', '马绍尔群岛': 'MH', '马提尼克': 'MQ',
    '毛里塔尼亚': 'MR', '毛里求斯': 'MU', '马约特': 'YT', '墨西哥': 'MX',
    '密克罗尼西亚': 'FM', '摩尔多瓦': 'MD', '摩纳哥': 'MC', '蒙古': 'MN',
    '黑山': 'ME', '蒙特塞拉特': 'MS', '摩洛哥': 'MA', '莫桑比克': 'MZ',
    '缅甸': 'MM', '纳米比亚': 'NA', '瑙鲁': 'NR', '尼泊尔': 'NP',
    '荷兰': 'NL', '新喀里多尼亚': 'NC', '新西兰': 'NZ', '尼加拉瓜': 'NI',
    '尼日尔': 'NE', '尼日利亚': 'NG', '纽埃': 'NU', '诺福克岛': 'NF',
    '北马里亚纳群岛': 'MP', '挪威': 'NO', '阿曼': 'OM', '巴基斯坦': 'PK',
    '帕劳': 'PW', '巴勒斯坦': 'PS', '巴拿马': 'PA', '巴布亚新几内亚': 'PG',
    '巴拉圭': 'PY', '秘鲁': 'PE', '菲律宾': 'PH', '皮特凯恩': 'PN',
    '波兰': 'PL', '葡萄牙': 'PT', '波多黎各': 'PR', '卡塔尔': 'QA',
    '留尼汪': 'RE', '罗马尼亚': 'RO', '俄罗斯': 'RU', '卢旺达': 'RW',
    '圣巴泰勒米': 'BL', '圣赫勒拿': 'SH', '圣基茨和尼维斯': 'KN',
    '圣卢西亚': 'LC', '圣马丁': 'MF', '圣皮埃尔和密克隆': 'PM',
    '圣文森特和格林纳丁斯': 'VC', '萨摩亚': 'WS', '圣马力诺': 'SM',
    '圣多美和普林西比': 'ST', '沙特阿拉伯': 'SA', '沙特': 'SA',
    '塞内加尔': 'SN', '塞尔维亚': 'RS', '塞舌尔': 'SC', '塞拉利昂': 'SL',
    '新加坡': 'SG', '圣马丁(荷兰)': 'SX', '斯洛伐克': 'SK',
    '斯洛文尼亚': 'SI', '所罗门群岛': 'SB', '索马里': 'SO', '南非': 'ZA',
    '南乔治亚和南桑威奇群岛': 'GS', '南苏丹': 'SS', '西班牙': 'ES',
    '斯里兰卡': 'LK', '苏丹': 'SD', '苏里南': 'SR', '斯瓦尔巴和扬马延': 'SJ',
    '斯威士兰': 'SZ', '瑞典': 'SE', '瑞士': 'CH', '叙利亚': 'SY',
    '台湾': 'TW', '塔吉克斯坦': 'TJ', '坦桑尼亚': 'TZ', '泰国': 'TH',
    '东帝汶': 'TL', '多哥': 'TG', '托克劳': 'TK', '汤加': 'TO',
    '特立尼达和多巴哥': 'TT', '突尼斯': 'TN', '土耳其': 'TR',
    '土库曼斯坦': 'TM', '特克斯和凯科斯群岛': 'TC', '图瓦卢': 'TV',
    '乌干达': 'UG', '乌克兰': 'UA', '阿联酋': 'AE', '英国': 'GB',
    '美国': 'US', '美国本土外小岛屿': 'UM', '乌拉圭': 'UY',
    '乌兹别克斯坦': 'UZ', '瓦努阿图': 'VU', '委内瑞拉': 'VE',
    '越南': 'VN', '英属维尔京群岛': 'VG', '美属维尔京群岛': 'VI',
    '瓦利斯和富图纳': 'WF', '西撒哈拉': 'EH', '也门': 'YE',
    '赞比亚': 'ZM', '津巴布韦': 'ZW',
}
# 三位 ISO 3166-1 alpha-3 → 两位码
ALPHA3_MAP = {
    'AFG': 'AF', 'ALA': 'AX', 'ALB': 'AL', 'DZA': 'DZ', 'ASM': 'AS',
    'AND': 'AD', 'AGO': 'AO', 'AIA': 'AI', 'ATA': 'AQ', 'ATG': 'AG',
    'ARG': 'AR', 'ARM': 'AM', 'ABW': 'AW', 'AUS': 'AU', 'AUT': 'AT',
    'AZE': 'AZ', 'BHS': 'BS', 'BHR': 'BH', 'BGD': 'BD', 'BRB': 'BB',
    'BLR': 'BY', 'BEL': 'BE', 'BLZ': 'BZ', 'BEN': 'BJ', 'BMU': 'BM',
    'BTN': 'BT', 'BOL': 'BO', 'BIH': 'BA', 'BWA': 'BW', 'BVT': 'BV',
    'BRA': 'BR', 'IOT': 'IO', 'BRN': 'BN', 'BGR': 'BG', 'BFA': 'BF',
    'BDI': 'BI', 'KHM': 'KH', 'CMR': 'CM', 'CAN': 'CA', 'CPV': 'CV',
    'CYM': 'KY', 'CAF': 'CF', 'TCD': 'TD', 'CHL': 'CL', 'CHN': 'CN',
    'CXR': 'CX', 'CCK': 'CC', 'COL': 'CO', 'COM': 'KM', 'COG': 'CG',
    'COD': 'CD', 'COK': 'CK', 'CRI': 'CR', 'CIV': 'CI', 'HRV': 'HR',
    'CUB': 'CU', 'CYP': 'CY', 'CZE': 'CZ', 'DNK': 'DK', 'DJI': 'DJ',
    'DMA': 'DM', 'DOM': 'DO', 'ECU': 'EC', 'EGY': 'EG', 'SLV': 'SV',
    'GNQ': 'GQ', 'ERI': 'ER', 'EST': 'EE', 'ETH': 'ET', 'FLK': 'FK',
    'FRO': 'FO', 'FJI': 'FJ', 'FIN': 'FI', 'FRA': 'FR', 'GUF': 'GF',
    'PYF': 'PF', 'ATF': 'TF', 'GAB': 'GA', 'GMB': 'GM', 'GEO': 'GE',
    'DEU': 'DE', 'GHA': 'GH', 'GIB': 'GI', 'GRC': 'GR', 'GRL': 'GL',
    'GRD': 'GD', 'GLP': 'GP', 'GUM': 'GU', 'GTM': 'GT', 'GGY': 'GG',
    'GIN': 'GN', 'GNB': 'GW', 'GUY': 'GY', 'HTI': 'HT', 'HMD': 'HM',
    'VAT': 'VA', 'HND': 'HN', 'HKG': 'HK', 'HUN': 'HU', 'ISL': 'IS',
    'IND': 'IN', 'IDN': 'ID', 'IRN': 'IR', 'IRQ': 'IQ', 'IRL': 'IE',
    'IMN': 'IM', 'ISR': 'IL', 'ITA': 'IT', 'JAM': 'JM', 'JPN': 'JP',
    'JEY': 'JE', 'JOR': 'JO', 'KAZ': 'KZ', 'KEN': 'KE', 'KIR': 'KI',
    'PRK': 'KP', 'KOR': 'KR', 'KWT': 'KW', 'KGZ': 'KG', 'LAO': 'LA',
    'LVA': 'LV', 'LBN': 'LB', 'LSO': 'LS', 'LBR': 'LR', 'LBY': 'LY',
    'LIE': 'LI', 'LTU': 'LT', 'LUX': 'LU', 'MAC': 'MO', 'MKD': 'MK',
    'MDG': 'MG', 'MWI': 'MW', 'MYS': 'MY', 'MDV': 'MV', 'MLI': 'ML',
    'MLT': 'MT', 'MHL': 'MH', 'MTQ': 'MQ', 'MRT': 'MR', 'MUS': 'MU',
    'MYT': 'YT', 'MEX': 'MX', 'FSM': 'FM', 'MDA': 'MD', 'MCO': 'MC',
    'MNG': 'MN', 'MNE': 'ME', 'MSR': 'MS', 'MAR': 'MA', 'MOZ': 'MZ',
    'MMR': 'MM', 'NAM': 'NA', 'NRU': 'NR', 'NPL': 'NP', 'NLD': 'NL',
    'NCL': 'NC', 'NZL': 'NZ', 'NIC': 'NI', 'NER': 'NE', 'NGA': 'NG',
    'NIU': 'NU', 'NFK': 'NF', 'MNP': 'MP', 'NOR': 'NO', 'OMN': 'OM',
    'PAK': 'PK', 'PLW': 'PW', 'PSE': 'PS', 'PAN': 'PA', 'PNG': 'PG',
    'PRY': 'PY', 'PER': 'PE', 'PHL': 'PH', 'PCN': 'PN', 'POL': 'PL',
    'PRT': 'PT', 'PRI': 'PR', 'QAT': 'QA', 'REU': 'RE', 'ROU': 'RO',
    'RUS': 'RU', 'RWA': 'RW', 'BLM': 'BL', 'SHN': 'SH', 'KNA': 'KN',
    'LCA': 'LC', 'MAF': 'MF', 'SPM': 'PM', 'VCT': 'VC', 'WSM': 'WS',
    'SMR': 'SM', 'STP': 'ST', 'SAU': 'SA', 'SEN': 'SN', 'SRB': 'RS',
    'SYC': 'SC', 'SLE': 'SL', 'SGP': 'SG', 'SXM': 'SX', 'SVK': 'SK',
    'SVN': 'SI', 'SLB': 'SB', 'SOM': 'SO', 'ZAF': 'ZA', 'SGS': 'GS',
    'SSD': 'SS', 'ESP': 'ES', 'LKA': 'LK', 'SDN': 'SD', 'SUR': 'SR',
    'SJM': 'SJ', 'SWZ': 'SZ', 'SWE': 'SE', 'CHE': 'CH', 'SYR': 'SY',
    'TWN': 'TW', 'TJK': 'TJ', 'TZA': 'TZ', 'THA': 'TH', 'TLS': 'TL',
    'TGO': 'TG', 'TKL': 'TK', 'TON': 'TO', 'TTO': 'TT', 'TUN': 'TN',
    'TUR': 'TR', 'TKM': 'TM', 'TCA': 'TC', 'TUV': 'TV', 'UGA': 'UG',
    'UKR': 'UA', 'ARE': 'AE', 'GBR': 'GB', 'USA': 'US', 'UMI': 'UM',
    'URY': 'UY', 'UZB': 'UZ', 'VUT': 'VU', 'VEN': 'VE', 'VNM': 'VN',
    'VGB': 'VG', 'VIR': 'VI', 'WLF': 'WF', 'ESH': 'EH', 'YEM': 'YE',
    'ZMB': 'ZM', 'ZWE': 'ZW',
}
ALPHA2_SET = set(COUNTRY_MAP.values()) | set(ALPHA3_MAP.values())  # 合法两位码全集


def valid_host(host):
    """主机是否为合法 IPv4/IPv6 地址（域名与非 IP 形态一律拒绝）"""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def valid_port(port):
    """端口是否合法（1-65535）"""
    return port.isdigit() and 1 <= int(port) <= 65535


def b64decode_str(text):
    """base64 解码（容忍 URL-safe 字母表与缺 padding），失败返回 None"""
    compact = ''.join(text.split()).replace('-', '+').replace('_', '/')
    if not compact or not re.fullmatch(r'[A-Za-z0-9+/=]+', compact):
        return None
    try:
        return base64.b64decode(compact + '=' * (-len(compact) % 4)).decode('utf-8', 'ignore')
    except Exception:
        return None


def extract_region(tag):
    """从标签提取地区码：emoji 国旗 → 独立字母段（两位验证 / 三位归一）→ 中文国名；提取不到返回 ''"""
    tag = tag.upper()
    m = FLAG_RE.search(tag)
    if m:
        a, b = ord(m.group(0)[0]) - 0x1F1E6, ord(m.group(0)[1]) - 0x1F1E6
        code = chr(a + 65) + chr(b + 65)
        if code in ALPHA2_SET:
            return code
    for seg in REGION_RE.findall(tag):
        if len(seg) == 2 and seg in ALPHA2_SET:
            return seg
        if len(seg) == 3 and seg in ALPHA3_MAP:
            return ALPHA3_MAP[seg]
    for cn in CN_RE.findall(tag):
        code = COUNTRY_MAP.get(cn)
        if code:
            return code
    return ''


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
        ip_port, region = line[:idx].strip(), extract_region(line[idx + 1:])
    else:
        ip_port, region = line, ''
    if ':' in ip_port:
        host, _, port = ip_port.rpartition(':')
        if not host or not valid_port(port):
            return None
    else:
        host, port = ip_port, str(DEFAULT_PORT)
    if not valid_host(host.strip('[]')):
        return None
    return f'{host}:{port}#{region}'


def parse_proxy_link(line):
    """代理链接（vmess/ss/trojan/vless/hysteria2/tuic）→ ip:port#Region；域名节点与解析失败返回 None"""
    try:
        scheme, _, rest = line.strip().partition('://')
        scheme = scheme.lower()
        if scheme == 'vmess':
            cfg = json.loads(b64decode_str(rest.partition('#')[0]))
            host, port = cfg.get('add'), cfg.get('port')
            tag = str(cfg.get('ps') or '')
        elif scheme == 'ss':
            main, _, tag = rest.partition('#')
            if '@' not in main:               # 整体 base64 形态：解码后为 method:pass@host:port
                main = b64decode_str(main) or ''
            host, _, port = main.rpartition('@')[2].rpartition(':')
            tag = unquote(tag)
        elif scheme in ('trojan', 'vless', 'hysteria', 'hysteria2', 'hy2', 'tuic'):
            u = urlsplit(line)
            host, port, tag = u.hostname, u.port, unquote(u.fragment or '')
        else:
            return None
        host = str(host or '').strip().strip('[]')
        port = str(port if port is not None else DEFAULT_PORT).strip()
        if not host or not valid_host(host) or not valid_port(port):
            return None
        return f'{host}:{port}#{extract_region(tag)}'
    except Exception:
        return None


def parse_subscription(text):
    """订阅内容（整体 base64 或明文链接列表）→ 节点行列表"""
    decoded = b64decode_str(text)
    if decoded and '://' in decoded:
        text = decoded
    out = []
    for line in text.splitlines():
        line = line.strip()
        node = parse_proxy_link(line) if '://' in line else normalize_line(line)
        if node:
            out.append(node)
    return out


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
        if not valid_host(ip) or not valid_port(port):
            continue
        out.append(f'{ip}:{port}#{extract_region(cols[country_idx])}')  # 非标准代码留空，留给地区补全
    return out


def parse_source(text, source):
    """按源声明分发解析：sub → 订阅内容，columns → CSV，默认逐行"""
    if source.get('sub'):
        return parse_subscription(text)
    if 'columns' in source:
        return parse_columns(text, *source['columns'])
    return [n for n in map(normalize_line, text.splitlines()) if n]


if __name__ == '__main__':
    # 自检：代理链接解析（vmess / ss 整体 base64 / trojan URL / 域名丢弃）
    _vm = 'vmess://' + base64.b64encode(json.dumps(
        {'add': '1.2.3.4', 'port': 8443, 'ps': '🇺🇸 美国 US-01'}).encode()).decode()
    assert parse_proxy_link(_vm) == '1.2.3.4:8443#US', 'vmess 解析错'
    _ss = 'ss://' + base64.b64encode(b'aes-256-gcm:pass@5.6.7.8:443').decode() + '#%F0%9F%87%AF%F0%9F%87%B5'
    assert parse_proxy_link(_ss) == '5.6.7.8:443#JP', 'ss 解析错'
    assert parse_proxy_link('trojan://pass@9.9.9.9:443?sni=x#DE-Berlin') == '9.9.9.9:443#DE', 'trojan 解析错'
    _dom = 'vmess://' + base64.b64encode(b'{"add":"example.com","port":443,"ps":"US"}').decode()
    assert parse_proxy_link(_dom) is None, '域名节点应丢弃'
    # 自检：地区码提取（emoji / 三位归一 / 中文 / 垃圾段留空）
    assert extract_region('JPN Tokyo') == 'JP' and extract_region('香港 HKG|01') == 'HK', '三位归一错'
    assert extract_region('德国 法兰克福') == 'DE' and extract_region('SSL-01') == '', '中文/垃圾段错'
    # 自检：订阅解码（整体 base64 内混合链接与裸 ip:port）
    _sub = base64.b64encode((_vm + '\n' + '1.1.1.1:443#US\n').encode()).decode()
    assert parse_subscription(_sub) == ['1.2.3.4:8443#US', '1.1.1.1:443#US'], '订阅解码错'
    # 自检：逐行回归（原有格式不受影响；域名与非 IP 形态一律拒绝）
    assert normalize_line('1.2.3.4:443#US') == '1.2.3.4:443#US', '逐行回归错'
    assert normalize_line('1.2.3.4') == '1.2.3.4:443#', '默认端口错'
    assert normalize_line('example.com:443#US') is None, '域名应拒绝'
    assert normalize_line('johndoe.example.com:443') is None, '子域名应拒绝'
    assert normalize_line('999.1.1.1:443#US') is None, '非法 IPv4 应拒绝'
    assert normalize_line('[2001:db8::1]:443#US') == '[2001:db8::1]:443#US', 'IPv6 应保留'
    assert parse_columns('IP,端口,国家\n1.2.3.4,443,USA', 0, 1, 2, True) == ['1.2.3.4:443#US'], 'CSV 三位码归一错'
    print('SourceParse 自检通过')
