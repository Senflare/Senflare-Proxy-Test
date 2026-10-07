import json, socket, ssl

NODES = [
    '109.71.240.135:443', '209.38.109.246:2053', '185.184.120.13:443',
    '91.149.241.140:443', '104.248.84.93:2096', '132.243.249.238:8443',
    '31.58.137.143:8443', '159.65.197.125:2053',
    '159.60.146.81:443', '121.127.34.119:443', '129.158.198.241:2053',
    '172.93.167.175:443', '159.60.146.82:443', '143.47.108.112:443',
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def probe_a(addr):
    host, _, port = addr.rpartition(':')
    try:
        with socket.create_connection((host, int(port)), timeout=8) as s:
            with ctx.wrap_socket(s, server_hostname='www.cloudflare.com') as t:
                t.sendall(b'HEAD /cdn-cgi/trace HTTP/1.1\r\nHost: www.cloudflare.com\r\nConnection: close\r\n\r\n')
                data = b''
                while len(data) < 8192:
                    try:
                        chunk = t.recv(4096)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    data += chunk
                return 'ok' if b'cf-ray' in data.lower() else 'no-cf-ray'
    except Exception as e:
        return type(e).__name__


if __name__ == '__main__':
    print(json.dumps({a: probe_a(a) for a in NODES}, ensure_ascii=False, indent=2))