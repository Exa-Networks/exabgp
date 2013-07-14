#!/usr/bin/env python
# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import unittest

from exabgp.configuration.environment import environment
env = environment.setup('')

from exabgp.configuration.file import Configuration


class TestConfiguration (unittest.TestCase):
	def setUp(self):
		pass

	def test_valid (self):
		for config in self.valid:
			configuration = Configuration(config,True)
			try:
				self.assertEqual(configuration.reload(),True,configuration.error)
			except:
				print
				print config
				print
				print configuration.error
				print
				raise
#		for ip in self.configuration.neighbor:
#			print self.configuration.neighbor[ip]

	def test_reload (self):
		configuration = Configuration(self.valid[0],True)
		configuration.reload()

	valid = [
"""\
neighbor 192.168.127.128 {
	description "a quagga test peer";
	router-id 192.168.127.1;
	local-address 192.168.127.1;
	local-as 65000;
	peer-as 65000;

	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.1;
		}
		route 10.0.2.0/24 {
			next-hop 10.0.255.2;
			community 30740:30740;
		}
		route 10.0.3.0/24 {
			next-hop 10.0.255.3;
			community [ 30740:30740 30740:0 ];
		}
		route 10.0.4.0/24 {
			next-hop 10.0.255.4;
			local-preference 200;
		}
		route 10.0.5.0/24 next-hop 10.0.255.5 local-preference 200;
		route 10.0.6.0/24 next-hop 10.0.255.6 community 30740:30740;
		route 10.0.7.0/24 next-hop 10.0.255.7 local-preference 200 community 30740:30740;
		route 10.0.8.0/24 next-hop 10.0.255.8 community 30740:30740 local-preference 200;
		route 10.0.9.0/24 next-hop 10.0.255.9 local-preference 200 community [30740:0 30740:30740];
		route 10.0.10.0/24 next-hop 10.0.255.10 community [30740:0 30740:30740] local-preference 200;
	}
}
"""
,
"""\
neighbor 192.168.127.128 {
	description "Configuration One";
	router-id 192.168.127.2;
	local-address 192.168.127.1;
	local-as 65001;
	peer-as 65000;

	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.1;
		}
		route 10.0.2.0/24 {
			next-hop 10.0.255.2;
			community 30740:30740;
		}
		route 10.0.3.0/24 {
			next-hop 10.0.255.3;
			community [ 30740:30740 30740:0 ];
		}
		route 10.0.4.0/24 {
			next-hop 10.0.255.4;
			local-preference 200;
		}
	}
}
neighbor 10.0.0.10 {
	description "Configuration Two";
	local-address 10.0.0.2;
	local-as 65001;
	peer-as 65001;

	static {
		route 10.0.5.0/24 next-hop 10.0.255.5 local-preference 200;
		route 10.0.6.0/24 next-hop 10.0.255.6 community 30740:30740;
		route 10.0.7.0/24 next-hop 10.0.255.7 local-preference 200 community 30740:30740;
		route 10.0.8.0/24 next-hop 10.0.255.8 community 30740:30740 local-preference 200;
		route 10.0.9.0/24 next-hop 10.0.255.9 local-preference 200 community [30740:0 30740:30740];
		route 10.0.10.0/24 next-hop 10.0.255.10 community [30740:0 30740:30740] local-preference 200;
	}
}
"""
]

	def test_faults (self):
		for config,error in self._faults.iteritems():
			configuration = Configuration(config,True)

			try:
				self.assertEqual(configuration.reload(),False)
				self.assertEqual(config + ' '*10 + configuration.error,config + ' '*10 + error)
			except AssertionError:
				print
				print config
				print
				print configuration.error
				print
				raise



	_faults = {
"""\
	neighbor A {
	}
""" : 'syntax error in section neighbor\nline 1 : neighbor a {\n"a" is not a valid IP address'
,
"""\
neighbor 10.0.0.10 {
	invalid-command value ;
}
""": 'syntax error in section neighbor\nline 2 : invalid-command value ;\ninvalid keyword "invalid-command"'
,
"""\
neighbor 10.0.0.10 {
	description A non quoted description;
}
""" : 'syntax error in section neighbor\nline 2 : description a non quoted description ;\nsyntax: description "<description>"'
,
"""\
neighbor 10.0.0.10 {
	description "A quoted description with "quotes" inside";
}
""" : 'syntax error in section neighbor\nline 2 : description "a quoted description with "quotes" inside" ;\nsyntax: description "<description>"'
,
"""\
neighbor 10.0.0.10 {
	local-address A;
}
""" : 'syntax error in section neighbor\nline 2 : local-address a ;\n"a" is an invalid IP address'
,
"""\
neighbor 10.0.0.10 {
	local-as A;
}
""" : 'syntax error in section neighbor\nline 2 : local-as a ;\n"a" is an invalid ASN'
,
"""\
neighbor 10.0.0.10 {
	peer-as A;
}
""" : 'syntax error in section neighbor\nline 2 : peer-as a ;\n"a" is an invalid ASN'
,
"""\
neighbor 10.0.0.10 {
	router-id A;
}
""" : 'syntax error in section neighbor\nline 2 : router-id a ;\n"a" is an invalid IP address'
,
"""\
neighbor 10.0.0.10 {
	static {
		route A/24 next-hop 10.0.255.5;
	}
}
""" : 'syntax error in section static\nline 3 : route a/24 next-hop 10.0.255.5 ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route 10.0.5.0/A next-hop 10.0.255.5;
	}
}
""" : 'syntax error in section static\nline 3 : route 10.0.5.0/a next-hop 10.0.255.5 ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route A next-hop 10.0.255.5;
	}
}
""" : 'syntax error in section static\nline 3 : route a next-hop 10.0.255.5 ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route 10.0.5.0/24 next-hop A;
	}
}
""" : 'syntax error in section static\nline 3 : route 10.0.5.0/24 next-hop a ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route 10.0.5.0/24 next-hop 10.0.255.5 local-preference A;
	}
}
""" : 'syntax error in section static\nline 3 : route 10.0.5.0/24 next-hop 10.0.255.5 local-preference a ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route 10.0.5.0/24 next-hop 10.0.255.5 community a;
	}
}
""" : 'syntax error in section static\nline 3 : route 10.0.5.0/24 next-hop 10.0.255.5 community a ;\n' + Configuration._str_route_error
,
"""\
neighbor 10.0.0.10 {
	static {
		route 10.0.5.0/24 next-hop 10.0.255.5 community [ A B ];
	}
}
""" : 'syntax error in section static\nline 3 : route 10.0.5.0/24 next-hop 10.0.255.5 community [ a b ] ;\n' + Configuration._str_route_error
,
"""\
neighbor 192.168.127.128 {
	local-address 192.168.127.1;
	local-as 65000;
	peer-as 65000;
	static {
		route 10.0.1.0/24 {
		}
	}
}
""" : 'syntax error in section static\nline 7 : }\nsyntax: route IP/MASK { next-hop IP; }'
,
"""\
neighbor 192.168.127.128 {
	static {
		route 10.0.1.0/24 {
			next-hop A;
		}
	}
}
""" : 'syntax error in section route\nline 4 : next-hop a ;\n' + Configuration._str_route_error
,
"""\
neighbor 192.168.127.128 {
	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.5;
			local-preference A;
		}
	}
}
""" : 'syntax error in section route\nline 5 : local-preference a ;\n' + Configuration._str_route_error
,
"""\
neighbor 192.168.127.128 {
	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.5;
			community A;
		}
	}
}
""" : 'syntax error in section route\nline 5 : community a ;\n' + Configuration._str_route_error
,
"""\
neighbor 192.168.127.128 {
	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.5;
			community [ A B ];
		}
	}
}
""" : 'syntax error in section route\nline 5 : community [ a b ] ;\n' + Configuration._str_route_error
,
"""\
neighbor 192.168.127.128 {
	local-address 192.168.127.1;
	local-as 65000;
	peer-as 65000;

	static {
		route 10.0.1.0/24 {
			next-hop 10.0.255.1;
		}
	}
""" : 'syntax error in section neighbor\nline 10 : }\nconfiguration file incomplete (most likely missing })'
,

}


if __name__ == '__main__':
	unittest.main()
