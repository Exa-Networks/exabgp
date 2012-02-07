<?php
$lookup_db_host='192.168.127.130';
$lookup_db_user='collector';
$lookup_db_password='collector';
$lookup_db_database='collector';

// Specify the look you wish lists to have here: ('radio'/'select')
$router_list_style = 'select';
$request_list_style = 'select';
$socket_timeout = 5;

/*
Describe your routers here.
* [title] is what you will see at the web-page, e.g. 'border router' or 'core-1-2-net15-gw'.
If omitted, <address> will be used.
* <address> is IP dotted quad or DNS name, to which this script will telnet. If omitted,
corresonding router will be removed from the page automatically. Pay attention to be able to
resolve DNS name from the web server's side.
* [services] is a list of following words: zebra, ripd,	ripngd, ospfd, bgpd, ospf6d.
It defines availability to execute certain command on the router.
If omitted, no commands will be allowed on the router, although it will remain on the list.
* [ignore_argc] lets get full routing table, when set to true, therefore disabled by default
* <username> sets optional username to send before the password for the router. If not set, username is not sent.
* [password] sets default password for all daemons on the router
* [DAEMON_password] redefines password for DAEMON on the router
* [DAEMON_port] redefines TCP port for the DAEMON. See examples below.
*/

// default values for all routers, used if there is no more specific setting
$router['default']['zebra_port'] = 2601;
$router['default']['ripd_port'] = 2602;
$router['default']['ripngd_port'] = 2603;
$router['default']['ospfd_port'] = 2604;
$router['default']['bgpd_port'] = 2605;
$router['default']['ospf6d_port'] = 2606;
$router['default']['password'] = '';
$router['default']['ignore_argc'] = FALSE;

// your routers
// I recommend using of key numbers with step of 10, it allows to insert new
// declarations without reordering the rest of list. As in BASIC or DNS MX.
$router[10]['title'] = 'route collector IPv4 + IPv6';
$router[10]['address'] = '1';
$router[10]['services'] = 'bgpd';
$router[10]['password'] = '';

/*
Requests definitions.
[title] is what you see on the web-page. If omitted, <command> is used instead.
<command> is what is sent to the CLI.
<handler> is processing daemon's name
<argc> is minimal argument count
*/
$request[10]['title'] = 'show ip bgp summary';
$request[10]['command'] = 'show ip bgp summary';
$request[10]['handler'] = 'bgpd';
$request[10]['argc'] = 0;
$request[10]['net'] = 0;

$request[20]['title'] = 'show ip bgp [arg NETv4 or NETv6]';
$request[20]['command'] = 'show ip bgp';
$request[20]['handler'] = 'bgpd';
$request[20]['argc'] = 1;
$request[20]['net'] = 1;

$request[30]['title'] = 'show ip bgp regexp [arg ASN] - kind of :)';
$request[30]['command'] = 'show ip bgp regexp';
$request[30]['handler'] = 'bgpd';
$request[30]['argc'] = 1;
$request[30]['net'] = 0;

?>
