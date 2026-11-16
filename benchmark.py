#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel
import json, argparse, time, math
from subprocess import PIPE

CC_SWEEP = ("cubic", "bbr")
CLIENTS = (
    ("C1", "192.168.0.2/24"),
    ("C2", "192.168.0.3/24"),
    ("C3", "192.168.0.4/24"),
    ("C4", "192.168.0.5/24"),
    ("C5", "192.168.0.6/24"),
    ("C6", "192.168.0.7/24"),
)
SERVERS = (
    ("S1", "192.168.1.2/24"),
    ("S2", "192.168.1.3/24"),
    ("S3", "192.168.1.4/24"),
    ("S4", "192.168.1.5/24"),
    ("S5", "192.168.1.6/24"),
    ("S6", "192.168.1.7/24"),
)
LINK_COUNT = 0
LATENCY = 0
LOSS = 0
BANDWIDTH = 100
CUBIC_PAIR = 0
REP = 5
DEBUG = False
TROUBLESHOOT = False
FAIRNESS = False


class MyTopo(Topo):
    def build(self):
        clientSwitch = self.addSwitch("CS", failMode="standalone", dpid="1")
        serverSwitch = self.addSwitch("SS", failMode="standalone", dpid="2")
        middleSwitch = self.addSwitch("MS", failMode="standalone", dpid="3")
        clientRouter = self.addHost("CR", ip="192.168.0.1/24")
        serverRouter = self.addHost("SR", ip="192.168.1.1/24")
        self.addLink("CS", "CR")
        self.addLink("SS", "SR")
        clients = []
        for name, ip in CLIENTS:
            clients.append(
                self.addHost(name, ip=f"{ip}", defaultRoute="via 192.168.0.1")
            )
        for c in clients:
            self.addLink(c, clientSwitch)
        servers = []
        for name, ip in SERVERS:
            servers.append(
                self.addHost(name, ip=f"{ip}", defaultRoute="via 192.168.1.1")
            )
        for s in servers:
            self.addLink(s, serverSwitch)
        BDP = math.ceil(
            BANDWIDTH * 10 / 12
        )  # since BDP = number of packets, MTU is 1500 bytes = 12kb, bandwidth is in 10^6 bit/s, latency is in 10^-3 sec
        self.addLink(
            clientRouter,
            middleSwitch,
            intfName1="wan0",
            params1={
                "ip": "10.1.0.1/24",
                "bw": BANDWIDTH,
                "delay": "10ms",
                "loss": LOSS,
                "max_queue_size": BDP * 2,
            },
        )
        self.addLink(
            middleSwitch,
            serverRouter,
            intfName2="wan0",
            params2={"ip": f"10.1.0.2/24"},
        )
        for i in range(1, LINK_COUNT + 1):
            QUEUE = math.ceil(BANDWIDTH * 10 / 12)
            BDP = math.ceil(
                BANDWIDTH * (10 + (LATENCY if i == 1 else 0)) / 12
            )  # since BDP = number of packets, MTU is 1500 bytes = 12kb, bandwidth is in 10^6 bit/s, latency is in 10^-3 sec
            self.addLink(
                clientRouter,
                middleSwitch,
                intfName1=f"wan{i}",
                params1={
                    "ip": f"10.1.{i}.1/24",
                    "bw": BANDWIDTH,
                    "delay": f"{10 + (LATENCY if i == 1 else 0)}ms",
                    "loss": LOSS,
                    "max_queue_size": QUEUE + BDP,
                },
            )
            self.addLink(
                middleSwitch,
                serverRouter,
                intfName2=f"wan{i}",
                params2={"ip": f"10.1.{i}.2/24"},
            )


def measure(node, cc):
    iperf = node.cmd(f"iperf3 -c {SERVERS[0][1].split('/')[0]} -i 0 -P1 -C {cc} -J")
    try:
        sent = json.loads(iperf)["end"]["sum_sent"]
    except Exception:
        return measure(node, cc)
    return sent["bits_per_second"] / 1e6, sent["retransmits"]


def measureAll(cubicPair):
    procs = []
    for i in range(cubicPair + 1):
        cc = "bbr" if i == 0 else "cubic"
        dst = SERVERS[i][1].split("/")[0]
        node = net.get(CLIENTS[i][0])
        procs.append(
            (
                CLIENTS[i][0],
                cc,
                node.popen(
                    f"iperf3 -c {dst} -t 30 -O 10 -i 0 -P1 -C {cc} -J".split(),
                    stdout=PIPE,
                ),
            )
        )
    results = []
    failed = False
    for name, cc, p in procs:
        try:
            sent = json.loads(p.communicate(timeout=180)[0])["end"]["sum_sent"]
            results.append(
                (name, cc, sent["bits_per_second"] / 1e6, sent["retransmits"])
            )
        except Exception:
            p.kill()
            failed = True
    if failed:
        return measureAll(cubicPair)
    return results


def configRouter(router, peer):
    router.cmd("nft flush ruleset")
    router.cmd("nft add table ip spray")
    router.cmd(
        "nft add chain ip spray pre '{ type filter hook prerouting priority mangle; }'"
    )
    router.cmd(
        "nft add chain ip spray forward '{ type filter hook forward priority mangle; }'"
    )
    if DEBUG:
        router.cmd('nft add rule ip spray forward oifname "wan0" counter')

    router.cmd(f"ip route add default via 10.1.0.{peer}")
    for i in range(1, LINK_COUNT + 1):
        if DEBUG:
            router.cmd(f"nft add rule ip spray forward meta mark {i} counter")
            router.cmd(f'nft add rule ip spray forward oifname "wan{i}" counter')
        router.cmd(f"ip rule del table 10{i}")
        router.cmd(f"ip route flush table 10{i}")
        router.cmd(f"ip rule add fwmark {i} table 10{i}")
        router.cmd(f"ip route add default via 10.1.{i}.{peer} dev wan{i} table 10{i}")
    router.cmd(
        "for interface in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 >$interface; done"
    )
    router.cmd(
        "for interface in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 1 >$interface; done"
    )
    router.cmd("sysctl -w net.ipv4.ip_forward=1")
    router.cmd("sysctl -w net.ipv4.conf.all.arp_ignore=1")


def parseArgs():
    p = argparse.ArgumentParser()
    p.add_argument("--link-count", type=int, default=2)
    p.add_argument("--loss", type=float, default=0)
    p.add_argument("--latency", type=int, default=0)
    p.add_argument("--bandwidth", type=int, default=100)
    p.add_argument("--cubic-pair", type=int, default=0)
    p.add_argument("--rep", type=int, default=3)
    p.add_argument("--fairness", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--troubleshoot", action="store_true")
    args = p.parse_args()
    global \
        LINK_COUNT, \
        LOSS, \
        LATENCY, \
        BANDWIDTH, \
        CUBIC_PAIR, \
        DEBUG, \
        TROUBLESHOOT, \
        FAIRNESS, \
        REP
    LINK_COUNT = args.link_count
    LOSS = args.loss
    LATENCY = args.latency
    BANDWIDTH = args.bandwidth
    CUBIC_PAIR = args.cubic_pair
    DEBUG = args.debug
    TROUBLESHOOT = args.troubleshoot
    FAIRNESS = args.fairness
    REP = args.rep
    print(
        f">>>>> ARGS: link count = {LINK_COUNT}, single link bandwidth = {BANDWIDTH} (Mbps), loss = {LOSS} (%), skewed latency = {LATENCY} (ms), pair count = {CUBIC_PAIR}, rep = {REP}"
    )


if __name__ == "__main__":
    if DEBUG:
        setLogLevel("info")
    else:
        setLogLevel("critical")

    parseArgs()
    if DEBUG:
        print("##### Phase 1: Loading topology #####")
    net = Mininet(topo=MyTopo(), link=TCLink, switch=OVSBridge, controller=None)
    net.start()
    if DEBUG:
        print("##### Phase 2: Bootstrap #####")
    for switch in ("CS", "SS", "MS"):
        s = net.get(switch)
        devs = " ".join([switch] + [i.name for i in s.intfList() if i.name != "lo"])
        s.cmd(f"for d in {devs}; do ethtool -K $d gso off tso off gro off; done")

    for clientName, _ in CLIENTS:
        client = net.get(clientName)
        client.cmd(
            "for interface in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 1 >$interface; done"
        )
        client.cmd("sysctl -w net.ipv4.tcp_no_metrics_save=1")
    for serverName, _ in SERVERS:
        server = net.get(serverName)
        server.cmd(
            "for interface in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 1 >$interface; done"
        )
        server.cmd("sysctl -w net.ipv4.tcp_no_metrics_save=1")
        server.cmd("iperf3 -s -D")
    clientRouter, serverRouter = net.get("CR", "SR")
    configRouter(clientRouter, 2)
    configRouter(serverRouter, 1)

    client1, server1 = net.get("C1", "S1")
    if DEBUG:
        print("##### Phase 3: Base line sanity check (no packet spraying) #####")
    clientRouter.cmd("nft reset rules table ip spray")
    if DEBUG:
        print("Client pings server 10 times")
        client1.cmd("ping -i 0.02 192.168.1.2 -c10")
        print("Packets should all land on 1 outbound interface")
        print(clientRouter.cmd("nft list ruleset | grep -E 'oifname.*counter'"))
        print(serverRouter.cmd("nft list ruleset | grep -E 'oifname.*counter'"))

    if DEBUG:
        print("##### Phase 4: Base line iperf: CUBIC, BBR #####")
        for cc in CC_SWEEP:
            print(measure(client1, cc))

    if DEBUG:
        print("##### Phase 5: Test sanity check (packet spraying) #####")
    clientRouter.cmd(
        f'nft add rule ip spray pre iifname != "wan*" meta mark set numgen inc mod {LINK_COUNT} offset 1'
    )
    clientRouter.cmd("nft reset rules table ip spray")
    serverRouter.cmd(
        f'nft add rule ip spray pre iifname != "wan*" meta mark set numgen inc mod {LINK_COUNT} offset 1'
    )
    serverRouter.cmd("nft reset rules table ip spray")
    if DEBUG:
        print("Client pings server 10 times")
        client1.cmd("ping -i 0.02 192.168.1.2 -c10")
        print("Packets should spread evenly on outbound interfaces (except for wan0)")
        print(clientRouter.cmd("nft list ruleset | grep -E 'oifname.*counter'"))
        print(serverRouter.cmd("nft list ruleset | grep -E 'oifname.*counter'"))

    if DEBUG:
        print("##### Phase 6: Test spray iperf: CUBIC, BBR #####")
    else:
        print("##### Spray iperf: CUBIC, BBR #####")
    for rep in range(REP):
        if FAIRNESS:
            for row in measureAll(CUBIC_PAIR):
                print(row)
        else:
            for cc in CC_SWEEP:
                print(measure(client1, cc))
    if TROUBLESHOOT:
        time.sleep(1000000000)
    for serverName, _ in SERVERS:
        server = net.get(serverName)
        server.cmd("pkill -x iperf3")
    net.stop()
