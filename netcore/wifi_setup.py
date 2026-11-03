"""Portable hostname, scan and non-blocking portal connection diagnostics."""
import runtime_debug
from ticks import ticks_ms, ticks_diff


def valid_hostname(value):
    return (isinstance(value, str) and 1 <= len(value) <= 32
            and value[0] != '-' and value[-1] != '-'
            and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in value))


def apply_hostname(network_module=None, wlan=None):
    name = runtime_debug.setting('HOSTNAME', 'uhs-scale')
    if not valid_hostname(name):
        name = 'uhs-scale'
    if network_module is None:
        import network as network_module
    try:
        network_module.hostname(name)
        return True
    except Exception:
        pass
    if wlan is not None:
        for key in ('dhcp_hostname', 'hostname'):
            try:
                wlan.config(**{key: name})
                return True
            except Exception:
                pass
    return False


def station():
    import network
    wlan = network.WLAN(network.STA_IF)
    apply_hostname(network, wlan)
    return wlan


def link_status(wlan):
    result = {'connected': False, 'ip': '', 'rssi': None, 'code': 'disconnected'}
    try:
        if wlan.isconnected():
            result.update(connected=True, ip=wlan.ifconfig()[0], code='connected')
            try:
                result['rssi'] = wlan.status('rssi')
            except Exception:
                pass
            return result
        import network
        status = wlan.status()
        for name, code in (('STAT_WRONG_PASSWORD', 'wrong_password'),
                           ('STAT_NO_AP_FOUND', 'network_not_found'),
                           ('STAT_CONNECT_FAIL', 'connection_failed')):
            if hasattr(network, name) and status == getattr(network, name):
                result['code'] = code
                break
    except Exception:
        result['code'] = 'unavailable'
    return result


def scan_networks(wlan=None):
    wlan = wlan if wlan is not None else station()
    if not wlan.active():
        wlan.active(True)
    groups = {}
    for row in wlan.scan():
        ssid = row[0].decode('utf-8', 'replace') if isinstance(row[0], bytes) else str(row[0])
        if not ssid:
            continue
        item = {'ssid': ssid, 'rssi': int(row[3]), 'secure': bool(row[4]), 'channel': int(row[2])}
        if ssid not in groups or item['rssi'] > groups[ssid]['rssi']:
            groups[ssid] = item
    return sorted(groups.values(), key=lambda item: item['rssi'], reverse=True)[:20]


class ConnectionTest:
    """The setup AP remains active while STA changes. Never writes NVS."""
    def __init__(self, wlan, previous, wifi_device=None):
        self.wlan = wlan
        self.previous = previous
        self.wifi = wifi_device
        self.running = False
        self.result = 'idle'
        self.ssid = ''
        self.password = ''
        self.started = 0
        self.changed = False

    def start(self, ssid, password):
        if self.running:
            raise ValueError('A connection test is already running')
        self.ssid = ssid
        self.password = password
        if self.wifi:
            self.wifi._portal_test = True
        self.changed = True
        self.wlan.active(True)
        self.wlan.disconnect()
        self.started = ticks_ms()
        self.running = True
        self.result = 'connecting'
        try:
            self.wlan.connect(ssid, password)
        except Exception:
            self.running = False
            self.result = 'connection_failed'
            self.restore()

    def tick(self):
        if not self.running:
            return
        status = link_status(self.wlan)
        if status['connected']:
            self.running = False
            self.result = 'connected'
            if self.wifi:
                self.wifi.use_station(self.wlan)
        elif status['code'] in ('wrong_password', 'network_not_found', 'connection_failed', 'unavailable'):
            self.running = False
            self.result = status['code']
            self.restore()
        elif ticks_diff(ticks_ms(), self.started) >= 20000:
            self.running = False
            self.result = 'timeout'
            self.restore()

    def status(self):
        data = link_status(self.wlan)
        data.update(test=self.result, testing=self.running, testSsid=self.ssid)
        return data

    def restore(self):
        if not self.changed:
            return
        self.changed = False
        self.password = ""
        try:
            self.wlan.disconnect()
            if self.previous[0]:
                self.wlan.connect(self.previous[0], self.previous[1])
            if self.wifi:
                self.wifi.use_station(self.wlan)
        except Exception:
            pass
        self.running = False
