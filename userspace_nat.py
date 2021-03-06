from netfilterqueue import NetfilterQueue
import subprocess
import traceback
import signal
import socket
from ctypes import *
import shlex
import struct

import dpkt


nfct = CDLL('libnetfilter_conntrack.so')

raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
raw_socket.setsockopt(socket.SOL_IP, socket.IP_HDRINCL, 1)

NFCT_CALLBACK = CFUNCTYPE(c_int, c_int, c_void_p, c_void_p)

# conntrack
CONNTRACK = 1
EXPECT = 2

# netlink groups
NF_NETLINK_CONNTRACK_NEW = 0x00000001
NF_NETLINK_CONNTRACK_UPDATE = 0x00000002
NF_NETLINK_CONNTRACK_DESTROY = 0x00000004
NF_NETLINK_CONNTRACK_EXP_NEW = 0x00000008
NF_NETLINK_CONNTRACK_EXP_UPDATE = 0x00000010
NF_NETLINK_CONNTRACK_EXP_DESTROY = 0x00000020

NFCT_ALL_CT_GROUPS = (NF_NETLINK_CONNTRACK_NEW | NF_NETLINK_CONNTRACK_UPDATE \
                      | NF_NETLINK_CONNTRACK_DESTROY)

# nfct_*printf output format
NFCT_O_PLAIN = 0
NFCT_O_DEFAULT = NFCT_O_PLAIN
NFCT_O_XML = 1
NFCT_O_MAX = 2

# output flags
NFCT_OF_SHOW_LAYER3_BIT = 0
NFCT_OF_SHOW_LAYER3 = (1 << NFCT_OF_SHOW_LAYER3_BIT)
NFCT_OF_TIME_BIT = 1
NFCT_OF_TIME = (1 << NFCT_OF_TIME_BIT)
NFCT_OF_ID_BIT = 2
NFCT_OF_ID = (1 << NFCT_OF_ID_BIT)

# query
NFCT_Q_CREATE = 0
NFCT_Q_UPDATE = 1
NFCT_Q_DESTROY = 2
NFCT_Q_GET = 3
NFCT_Q_FLUSH = 4
NFCT_Q_DUMP = 5
NFCT_Q_DUMP_RESET = 6
NFCT_Q_CREATE_UPDATE = 7

# callback return code
NFCT_CB_FAILURE = -1   # failure
NFCT_CB_STOP = 0    # stop the query
NFCT_CB_CONTINUE = 1    # keep iterating through data
NFCT_CB_STOLEN = 2    # like continue, but ct is not freed

# attributes
ATTR_ORIG_IPV4_SRC = 0                    # u32 bits
ATTR_IPV4_SRC = ATTR_ORIG_IPV4_SRC        # alias
ATTR_ORIG_IPV4_DST = 1                    # u32 bits
ATTR_IPV4_DST = ATTR_ORIG_IPV4_DST        # alias
ATTR_REPL_IPV4_SRC = 2                    # u32 bits
ATTR_REPL_IPV4_DST = 3                    # u32 bits
ATTR_ORIG_IPV6_SRC = 4                    # u128 bits
ATTR_IPV6_SRC = ATTR_ORIG_IPV6_SRC        # alias
ATTR_ORIG_IPV6_DST = 5                    # u128 bits
ATTR_IPV6_DST = ATTR_ORIG_IPV6_DST        # alias
ATTR_REPL_IPV6_SRC = 6                    # u128 bits
ATTR_REPL_IPV6_DST = 7                    # u128 bits
ATTR_ORIG_PORT_SRC = 8                    # u16 bits
ATTR_PORT_SRC = ATTR_ORIG_PORT_SRC        # alias
ATTR_ORIG_PORT_DST = 9                    # u16 bits
ATTR_PORT_DST = ATTR_ORIG_PORT_DST        # alias
ATTR_REPL_PORT_SRC = 10                   # u16 bits
ATTR_REPL_PORT_DST = 11                   # u16 bits
ATTR_ICMP_TYPE = 12                       # u8 bits
ATTR_ICMP_CODE = 13                       # u8 bits
ATTR_ICMP_ID = 14                         # u16 bits
ATTR_ORIG_L3PROTO = 15                    # u8 bits
ATTR_L3PROTO = ATTR_ORIG_L3PROTO          # alias
ATTR_REPL_L3PROTO = 16                    # u8 bits
ATTR_ORIG_L4PROTO = 17                    # u8 bits
ATTR_L4PROTO = ATTR_ORIG_L4PROTO          # alias
ATTR_REPL_L4PROTO = 18                    # u8 bits
ATTR_TCP_STATE = 19                       # u8 bits
ATTR_SNAT_IPV4 = 20                       # u32 bits
ATTR_DNAT_IPV4 = 21                       # u32 bits
ATTR_SNAT_PORT = 22                       # u16 bits
ATTR_DNAT_PORT = 23                       # u16 bits
ATTR_TIMEOUT = 24                         # u32 bits
ATTR_MARK = 25                            # u32 bits
ATTR_ORIG_COUNTER_PACKETS = 26            # u32 bits
ATTR_REPL_COUNTER_PACKETS = 27            # u32 bits
ATTR_ORIG_COUNTER_BYTES = 28              # u32 bits
ATTR_REPL_COUNTER_BYTES = 29              # u32 bits
ATTR_USE = 30                             # u32 bits
ATTR_ID = 31                              # u32 bits
ATTR_STATUS = 32                          # u32 bits
ATTR_TCP_FLAGS_ORIG = 33                  # u8 bits
ATTR_TCP_FLAGS_REPL = 34                  # u8 bits
ATTR_TCP_MASK_ORIG = 35                   # u8 bits
ATTR_TCP_MASK_REPL = 36                   # u8 bits
ATTR_MASTER_IPV4_SRC = 37                 # u32 bits
ATTR_MASTER_IPV4_DST = 38                 # u32 bits
ATTR_MASTER_IPV6_SRC = 39                 # u128 bits
ATTR_MASTER_IPV6_DST = 40                 # u128 bits
ATTR_MASTER_PORT_SRC = 41                 # u16 bits
ATTR_MASTER_PORT_DST = 42                 # u16 bits
ATTR_MASTER_L3PROTO = 43                  # u8 bits
ATTR_MASTER_L4PROTO = 44                  # u8 bits
ATTR_SECMARK = 45                         # u32 bits
ATTR_ORIG_NAT_SEQ_CORRECTION_POS = 46     # u32 bits
ATTR_ORIG_NAT_SEQ_OFFSET_BEFORE = 47      # u32 bits
ATTR_ORIG_NAT_SEQ_OFFSET_AFTER = 48       # u32 bits
ATTR_REPL_NAT_SEQ_CORRECTION_POS = 49     # u32 bits
ATTR_REPL_NAT_SEQ_OFFSET_BEFORE = 50      # u32 bits
ATTR_REPL_NAT_SEQ_OFFSET_AFTER = 51       # u32 bits
ATTR_SCTP_STATE = 52                      # u8 bits
ATTR_SCTP_VTAG_ORIG = 53                  # u32 bits
ATTR_SCTP_VTAG_REPL = 54                  # u32 bits
ATTR_HELPER_NAME = 55                     # string (30 bytes max)
ATTR_DCCP_STATE = 56                      # u8 bits
ATTR_DCCP_ROLE = 57                       # u8 bits
ATTR_DCCP_HANDSHAKE_SEQ = 58              # u64 bits
ATTR_MAX = 59
ATTR_GRP_ORIG_IPV4 = 0                    # struct nfct_attr_grp_ipv4
ATTR_GRP_REPL_IPV4 = 1                    # struct nfct_attr_grp_ipv4
ATTR_GRP_ORIG_IPV6 = 2                    # struct nfct_attr_grp_ipv6
ATTR_GRP_REPL_IPV6 = 3                    # struct nfct_attr_grp_ipv6
ATTR_GRP_ORIG_PORT = 4                    # struct nfct_attr_grp_port
ATTR_GRP_REPL_PORT = 5                    # struct nfct_attr_grp_port
ATTR_GRP_ICMP = 6                         # struct nfct_attr_grp_icmp
ATTR_GRP_MASTER_IPV4 = 7                  # struct nfct_attr_grp_ipv4
ATTR_GRP_MASTER_IPV6 = 8                  # struct nfct_attr_grp_ipv6
ATTR_GRP_MASTER_PORT = 9                  # struct nfct_attr_grp_port
ATTR_GRP_ORIG_COUNTERS = 10               # struct nfct_attr_grp_ctrs
ATTR_GRP_REPL_COUNTERS = 11               # struct nfct_attr_grp_ctrs
ATTR_GRP_MAX = 12
ATTR_EXP_MASTER = 0                       # pointer to conntrack object
ATTR_EXP_EXPECTED = 1                     # pointer to conntrack object
ATTR_EXP_MASK = 2                         # pointer to conntrack object
ATTR_EXP_TIMEOUT = 3                      # u32 bits
ATTR_EXP_MAX = 4


# message type
NFCT_T_UNKNOWN = 0
NFCT_T_NEW_BIT = 0
NFCT_T_NEW = (1 << NFCT_T_NEW_BIT)
NFCT_T_UPDATE_BIT = 1
NFCT_T_UPDATE = (1 << NFCT_T_UPDATE_BIT)
NFCT_T_DESTROY_BIT = 2
NFCT_T_DESTROY = (1 << NFCT_T_DESTROY_BIT)

NFCT_T_ALL = NFCT_T_NEW | NFCT_T_UPDATE | NFCT_T_DESTROY
NFCT_T_ERROR_BIT = 31
NFCT_T_ERROR = (1 << NFCT_T_ERROR_BIT)

# set option
NFCT_SOPT_UNDO_SNAT = 0
NFCT_SOPT_UNDO_DNAT = 1
NFCT_SOPT_UNDO_SPAT = 2
NFCT_SOPT_UNDO_DPAT = 3
NFCT_SOPT_SETUP_ORIGINAL = 4
NFCT_SOPT_SETUP_REPLY = 5


def handle_two_side_traffic(nfqueue_element):
    try:
        ip_packet = dpkt.ip.IP(nfqueue_element.get_payload())
        src = socket.inet_ntoa(ip_packet.src)
        dst = socket.inet_ntoa(ip_packet.dst)
        sport = ip_packet.udp.sport
        dport = ip_packet.udp.dport
        print(src, sport, dst, dport)
        ct = nfct.nfct_new()
        if not ct:
            raise Exception("nfct_new failed!")
        nfct.nfct_set_attr_u8(ct, ATTR_L3PROTO, socket.AF_INET)
        nfct.nfct_set_attr_u32(ct, ATTR_IPV4_SRC, socket.htonl(struct.unpack('!I', ip_packet.src)[0]))
        nfct.nfct_set_attr_u32(ct, ATTR_IPV4_DST, socket.htonl(struct.unpack('!I', ip_packet.dst)[0]))
        nfct.nfct_set_attr_u8(ct, ATTR_L4PROTO, socket.IPPROTO_UDP)
        nfct.nfct_set_attr_u16(ct, ATTR_PORT_SRC, socket.htons(sport))
        nfct.nfct_set_attr_u16(ct, ATTR_PORT_DST, socket.htons(dport))
        nfct.nfct_setobjopt(ct, NFCT_SOPT_SETUP_REPLY)
        nfct.nfct_set_attr_u32(ct, ATTR_DNAT_IPV4, socket.htonl(struct.unpack('!I', socket.inet_aton('8.8.8.8'))[0]))
        nfct.nfct_set_attr_u16(ct, ATTR_DNAT_PORT, socket.htons(53))
        nfct.nfct_set_attr_u32(ct, ATTR_TIMEOUT, 120)
        h = nfct.nfct_open(CONNTRACK, 0)
        if not h:
            raise Exception("nfct_open failed!")
        try:
            ret = nfct.nfct_query(h, NFCT_Q_CREATE, ct)
            if ret == -1:
                raise Exception("nfct_query failed!")
        finally:
            nfct.nfct_close(h)
        raw_socket.sendto(str(ip_packet), (dst, 0))
        nfqueue_element.drop()
    except:
        traceback.print_exc()
        nfqueue_element.accept()


nfqueue = NetfilterQueue()
nfqueue.bind(0, handle_two_side_traffic)


def clean_up(*args):
    # will be called twice, don't know why
    subprocess.call(shlex.split('iptables -t nat -D OUTPUT -o eth0 -p udp --dport 53 -j QUEUE'))


signal.signal(signal.SIGINT, clean_up)

try:
    subprocess.call(shlex.split('iptables -t nat -I OUTPUT -o eth0 -p udp --dport 53 -j QUEUE'))
    print('running..')
    nfqueue.run()
except KeyboardInterrupt:
    print('bye')

