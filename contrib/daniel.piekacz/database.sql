drop database if exists `collector`;
create database `collector`;
use `collector`;

DROP TABLE IF EXISTS `members`;
CREATE TABLE IF NOT EXISTS `members` (
  `neighbor` varchar(39) NOT NULL,
  `asn` int(10) unsigned NOT NULL,
  `type` tinyint(3) unsigned NOT NULL,
  `status` tinyint(3) unsigned NOT NULL,
  `time` timestamp NOT NULL default '0000-00-00 00:00:00',
  `lastup` timestamp NOT NULL default '0000-00-00 00:00:00',
  `lastdown` timestamp NOT NULL default '0000-00-00 00:00:00',
  `prefixes` int(10) unsigned NOT NULL,
  `updown` int(10) unsigned NOT NULL,
  UNIQUE KEY `neighbor` (`neighbor`),
  KEY `asn` (`asn`),
  KEY `type` (`type`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

DROP TABLE IF EXISTS `prefixes`;
CREATE TABLE IF NOT EXISTS `prefixes` (
  `neighbor` varchar(39) NOT NULL,
  `type` tinyint(3) unsigned NOT NULL,
  `prefix` varchar(43) NOT NULL,
  `aspath` varchar(500) NOT NULL,
  `nexthop` varchar(39) NOT NULL,
  `community` TEXT NOT NULL,
  `extended_community` TEXT NOT NULL,
  `origin` varchar(10) NOT NULL,
  `time` timestamp NOT NULL default '0000-00-00 00:00:00',
  UNIQUE KEY `neighbor_prefix` (`neighbor`,`prefix`),
  KEY `neighbor` (`neighbor`),
  KEY `type` (`type`),
  KEY `prefix` (`prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

grant all on collector.* to 'collector' identified by 'collector';
flush privileges;

-- insert IPv4 peer at IP 192.127.130.1 ASN 123456
insert into members values ('192.168.127.130',123456,4,0,'','','',0,0);


