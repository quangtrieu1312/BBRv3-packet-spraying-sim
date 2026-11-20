A Mininet simulation for packet spraying using BBRv3 as TCP congestion control and compare with the default CUBIC as a baseline.

# Mininet
A programmable Linux tool for creating network namespaces and veth pairs

# ECMP versus packet spraying
<img src="docs/ECMP.svg"/>

# CUBIC versus BBR
<img src="docs/CongestionControl.svg"/>

# How to spray
Linux has routing policies (`ip rule`) to support multiple routing tables (`ip route`), and a policy can match against marked packets (`fwmark`) to decide which table to use.
The last piece is netfilter PREROUTING hook (`iptables/nftables`) which can mark packets before the kernel make routing decisions.
