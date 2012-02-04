create database collector;
use collector;

DROP TABLE IF EXISTS `members`;
CREATE TABLE IF NOT EXISTS `members` (
  `neighbor` varchar(50) NOT NULL,
  `asn` int(11) unsigned NOT NULL,
  `type` tinyint(3) unsigned NOT NULL,
  `status` tinyint(3) unsigned NOT NULL,
  `time` timestamp NOT NULL default '0000-00-00 00:00:00' on update CURRENT_TIMESTAMP,
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
  `neighbor` varchar(50) NOT NULL,
  `type` tinyint(3) unsigned NOT NULL,
  `prefix` varchar(50) NOT NULL,
  `aspath` varchar(255) NOT NULL,
  `nexthop` varchar(50) NOT NULL,
  `community` varchar(300) NOT NULL,
  `extended_community` varchar(300) NOT NULL,
  `origin` varchar(30) NOT NULL,
  `time` timestamp NOT NULL default '0000-00-00 00:00:00' on update CURRENT_TIMESTAMP,
  UNIQUE KEY `neighbor_prefix` (`neighbor`,`prefix`),
  KEY `neighbor` (`neighbor`),
  KEY `type` (`type`),
  KEY `prefix` (`prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

grant all on collector.* to 'collector' identified by 'collector';
flush privileges;

