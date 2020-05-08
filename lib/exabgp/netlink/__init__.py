# based on netlink.py at ....
# https://gforge.inria.fr/scm/viewvc.php/canso/trunk/tools/netlink.py?view=markup&revision=1360&root=mehani&pathrev=1360
# https://www.linuxjournal.com/article/7356?page=0,1
# http://smacked.org/docs/netlink.pdf
# RFC 3549 - https://tools.ietf.org/html/rfc3549


class NetLinkError(Exception):
    def __init__(self, error, message='', response=''):
        reported = error.strip() + '\n'
        if message:
            reported += '\nMessage: %s' % ' '.join('%02X' % ord(_) for _ in message)
        if message:
            reported += '\n        : %s' % ''.join(_ for _ in message if _.isalnum() or _.isspace())
        if response:
            reported += '\nResponse: %s' % ' '.join('%02X' % ord(_) for _ in response)
        if response:
            reported += '\n        : %s' % ''.join(_ for _ in response if _.isalnum() or _.isspace())
        Exception.__init__(self, reported)


class NetMask(object):
    CIDR = {
        32: '255.255.255.255',
        31: '255.255.255.254',
        30: '255.255.255.252',
        29: '255.255.255.248',
        28: '255.255.255.240',
        27: '255.255.255.224',
        26: '255.255.255.192',
        25: '255.255.255.128',
        24: '255.255.255.0',
        23: '255.255.254.0',
        22: '255.255.252.0',
        21: '255.255.248.0',
        20: '255.255.240.0',
        19: '255.255.224.0',
        18: '255.255.192.0',
        17: '255.255.128.0',
        16: '255.255.0.0',
        15: '255.254.0.0',
        14: '255.252.0.0',
        13: '255.248.0.0',
        12: '255.240.0.0',
        11: '255.224.0.0',
        10: '255.192.0.0',
        9: '255.128.0.0',
        8: '255.0.0.0',
        7: '254.0.0.0',
        6: '252.0.0.0',
        5: '248.0.0.0',
        4: '240.0.0.0',
        3: '224.0.0.0',
        2: '192.0.0.0',
        1: '128.0.0.0',
        0: '0.0.0.0',
    }
