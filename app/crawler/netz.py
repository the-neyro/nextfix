"""Netzziele für Website-Abrufe: die geprüfte Adresse ist auch das Verbindungsziel."""

import ipaddress
import socket

import httpcore
import httpx

LOKALE_NETZE = tuple(map(ipaddress.ip_network, (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "fc00::/7", "::1/128",
)))
# Übergangstechniken können IPv4-Ziele in scheinbar öffentliche IPv6-Adressen einbetten.
IPV6_UEBERGANGSNETZE = tuple(map(ipaddress.ip_network, ("64:ff9b::/96", "64:ff9b:1::/48", "2001::/32", "2002::/16")))
IP = ipaddress.IPv4Address | ipaddress.IPv6Address


def _ip(text: str) -> IP:
    ip = ipaddress.ip_address(text)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _oeffentlich(ip: IP) -> bool:
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and not any(
        ip in netz for netz in IPV6_UEBERGANGSNETZE
    )


def _lokaler_name(host: str) -> bool:
    return host == "localhost" or host.endswith(".localhost")


class Zielbereich:
    def __init__(self, start_url: str | None = None):
        self.start = httpx.URL(start_url) if start_url else None

    def erlaubt_lokal(self, host: str, port: int, adressen: list[IP]) -> bool:
        if self.start is None:
            return False
        start_host = self.start.raw_host.decode("ascii").lower().rstrip(".")
        start_port = self.start.port or (443 if self.start.scheme == "https" else 80)
        if (host, port) != (start_host, start_port):
            return False
        if _lokaler_name(host):
            return all(ip.is_loopback for ip in adressen)
        try:
            start_ip = _ip(host)
        except ValueError:
            return False
        return all(ip == start_ip for ip in adressen) and any(start_ip in netz for netz in LOKALE_NETZE)

    def adressen(self, host: str, port: int) -> list[str]:
        host = host.lower().rstrip(".")
        try:
            adressen = [_ip(host)]
        except ValueError:
            adressen = list(dict.fromkeys(
                _ip(info[4][0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ))
        if not adressen or (
            not self.erlaubt_lokal(host, port, adressen)
            and (_lokaler_name(host) or not all(_oeffentlich(ip) for ip in adressen))
        ):
            raise OSError("Nicht öffentliches Netzziel")
        return [str(ip) for ip in adressen]

    def verbinden(self, host: str, port: int, timeout: float) -> socket.socket:
        for adresse in self.adressen(host, port):
            try:
                return socket.create_connection((adresse, port), timeout=timeout)
            except OSError as fehler:
                letzter_fehler = fehler
        raise letzter_fehler


class _Backend(httpcore.SyncBackend):
    def __init__(self, zielbereich: Zielbereich):
        self.zielbereich = zielbereich

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            adressen = self.zielbereich.adressen(host, port)
        except (OSError, ValueError) as fehler:
            raise httpcore.ConnectError(str(fehler)) from None
        for adresse in adressen:
            try:
                return super().connect_tcp(adresse, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as fehler:
                letzter_fehler = fehler
        raise letzter_fehler


class _Transport(httpx.HTTPTransport):
    def __init__(self, zielbereich: Zielbereich):
        # HTTPTransport übersetzt httpcore-Fehler und lässt Host/SNI unverändert.
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(), network_backend=_Backend(zielbereich)
        )


def http_client(start_url: str | None, *, user_agent: str, timeout: float) -> httpx.Client:
    return httpx.Client(
        transport=_Transport(Zielbereich(start_url)),
        trust_env=False,  # Systemproxies würden die Zielprüfung beim Verbinden umgehen.
        timeout=timeout,
        headers={"User-Agent": user_agent},
    )
