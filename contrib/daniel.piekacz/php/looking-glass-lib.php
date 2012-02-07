<?php

function time_diff($start, $end="NOW")
{
 $sdate = strtotime($start);
 $edate = strtotime($end);
 $time = $edate - $sdate;

 if($time>=0 && $time<=59) {
  // Seconds
  $timeshift = $time.'s';
 } elseif($time>=60 && $time<=3599) {
  // Minutes + Seconds
  $pmin = ($edate - $sdate) / 60;
  $premin = explode('.', $pmin);

  $presec = $pmin-$premin[0];
  $sec = $presec*60;

  $timeshift = $premin[0].'m'.round($sec,0).'s';
 } elseif($time>=3600 && $time<=86399) {
  // Hours + Minutes
  $phour = ($edate - $sdate) / 3600;
  $prehour = explode('.',$phour);

  $premin = $phour-$prehour[0];
  $min = explode('.',$premin*60);

  $presec = '0.'.$min[1];
  $sec = $presec*60;

  $timeshift = $prehour[0].'h'.$min[0].'m'.round($sec,0).'s';
 } elseif($time>=86400) {
  // Days + Hours + Minutes
  $pday = ($edate - $sdate) / 86400;
  $preday = explode('.',$pday);

  $phour = $pday-$preday[0];
  $prehour = explode('.',$phour*24); 

  $premin = ($phour*24)-$prehour[0];
  $min = explode('.',$premin*60);

  $presec = '0.'.$min[1];
  $sec = $presec*60;

  $timeshift = $preday[0].'d'.$prehour[0].'h'.$min[0].'m'.round($sec,0).'s';
 }
 return $timeshift;
}

function printError ($message)
{
 echo "<font color=\"red\"><code><strong>" . $message . "</strong></code></font><br>\n";
}

function safeOutput ($string)
{
 return htmlentities (substr ($string, 0, 50));
}

function printRouterList ($router, $type)
{
 if ($type == "select") echo "<select name=\"routerid\">";
 while (list ($id, $attribute) = each ($router))
 if (strcmp ($id, "default") && !empty($attribute["address"]))
 {
  if ($type == "select") echo "<option value=\"{$id}\"";
  if ($type == "radio") echo "<input type=\"radio\" name=\"routerid\" value=\"{$id}\"";
  if ($_REQUEST["routerid"] == $id)
  {
   if ($type == "select") echo " selected=\"selected\"";
   if ($type == "radio") echo " checked=\"checked\"";
  }
  echo ">";
  echo $attribute["title"] ? $attribute["title"] : $attribute["address"];
  if ($type == "select") echo "</option>\n";
  if ($type == "radio") echo "</input><br/>\n";
 }
 if ($type == "select") echo "</{$type}>\n";
}

function printRequestList ($request, $type)
{
 if ($type == "select") echo "<select name=\"requestid\">";
 while (list($id, $attribute) = each ($request))
 if (!empty ($attribute["command"]) && !empty ($attribute["handler"]) && isset ($attribute["argc"]))
 {
  if ($type == "select") echo "<option value=\"{$id}\"";
  if ($type == "radio") echo "<input type=\"radio\" name=\"requestid\" value=\"{$id}\"";
  if ($_REQUEST["requestid"] == $id)
  {
   if ($type == "select") echo " selected=\"selected\"";
   if ($type == "radio") echo " checked=\"checked\"";
  }
  echo ">";
  echo $attribute["title"] ? $attribute["title"] : $attribute["command"];
  if ($type == "select") echo "</option>\n";
  if ($type == "radio") echo "</input><br/>\n";
 }
 echo "</{$type}>\n";
}

function ip_valid($ip, $ver, $net) {
 $val_ip = false;
 $val_prefix = 0;

 if ($ver==4) {
  $slash_pos = strpos($ip, "/");
  if ($slash_pos == false) {
   $ip_address = $ip;
   $val_ip = filter_var($ip_address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4);
   $val_prefix = 2;
  } else {
   $ip_address = substr($ip, 0, $slash_pos);
   $val_ip = filter_var($ip_address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4);
   $ip_prefix  = (int)substr($ip, $slash_pos+1, strlen($ip));
   if (($ip_prefix>0) && ($ip_prefix<=32)) { $val_prefix = 1; };
  }
  if ($net == true) {
   if (($val_ip!=false) && ($val_prefix==1)) { return $ip_address."/".$ip_prefix; } else { return false; };
  } else {
   if (($val_ip!=false) && ($val_prefix==2)) { return $ip_address; } else { return false; };
  }
 } else {
  $slash_pos = strpos($ip, "/");
  if ($slash_pos == false) {
   $ip_address = $ip;
   $val_ip = filter_var($ip_address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6);
   $val_prefix = 2;
  } else {
   $ip_address = substr($ip, 0, $slash_pos);
   $val_ip = filter_var($ip_address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6);
   $ip_prefix  = (int)substr($ip, $slash_pos+1, strlen($ip));
   if (($ip_prefix>0) && ($ip_prefix<=128)) { $val_prefix = 1; };
  }
  if ($net == true) {
   if (($val_ip!=false) && ($val_prefix==1)) { return $ip_address."/".$ip_prefix; } else { return false; };
  } else {
   if (($val_ip!=false) && ($val_prefix==2)) { return $ip_address; } else { return false; };
  }
 }
}

function execPreviousRequest ($router, $request)
{
 if (!isset($_REQUEST["routerid"])) return;
 $routerid = $_REQUEST["routerid"];
 if (!isset ($router[$routerid]["address"])) return;
 if (!isset($_REQUEST["requestid"])) return;
 $requestid = $_REQUEST["requestid"];
 if (!isset ($request[$requestid]["argc"])) return;
 $handler = $request[$requestid]["handler"];
 if (empty ($handler) || strpos ($router[$routerid]["services"], $handler) === false)
 {
  printError ("This request is not permitted for this router by administrator.");
  return;
 }
 if ($request[$requestid]["argc"] > 0)
 {
  if (trim ($_REQUEST["argument"]) == '')
  {
   $router_defined = isset ($router[$routerid]["ignore_argc"]);
   $router_permits = $router[$routerid]["ignore_argc"] == 1;
   $default_defined = isset ($router["default"]["ignore_argc"]);
   $default_permits = $router["default"]["ignore_argc"] == 1;
   $final_permits =
   (!$router_defined && $default_defined && $default_permits) ||
   ($router_defined && $router_permits);
   if (!$final_permits)
   {
    printError ("Argument is needed for this command");
    return;
   }
  } else {
   switch ($requestid) {
    case 20:
     $argument_tmp4 = ip_valid(trim($_REQUEST["argument"]), 4, $request[$requestid]["net"]);
     $argument_tmp6 = ip_valid(trim($_REQUEST["argument"]), 6, $request[$requestid]["net"]);
     if ($argument_tmp4!=false) {
      $argument = $argument_tmp4;
     } else {
      if ($argument_tmp6!=false) {
       $argument = $argument_tmp6;
      } else {
       printError ("A valid IP address or network is needed as argument");
       return;
      }
     }
     break;
    case 30:
     if (preg_match('/[^0-9\_]/', trim($_REQUEST["argument"]))) {
      printError ("A valid BGP regexp is needed as argument");
      return;
     } else {
      $argument_tmp = trim($_REQUEST["argument"]);
      if (is_numeric($argument_tmp)) {
       $argument = $argument_tmp;
      } else {
       $argument = str_replace("_", "% ", $argument_tmp);
      }
     }
     break;
    default:
     printError ("Argument is not valid");
     break;
   }
  }
 }

 include 'looking-glass-config.php';

 $mid = mysql_connect($lookup_db_host,$lookup_db_user,$lookup_db_password);
 if (!$mid) { die('Could not connect: ' . mysql_error()); };

  $dbs = mysql_select_db($lookup_db_database, $mid);
  if (!$dbs) { die('Can\'t use db: ' . mysql_error()); };

  switch ($requestid) {
   case 10:
    $res = mysql_query("SELECT * FROM `members` ORDER BY `type`,(neighbor+0),`neighbor`", $mid);
?>
<table id="rounded-corner">
<thead>
<tr>
<th scope="col">Neighbor</th>
<th scope="col">IPv4/6</th>
<th scope="col">ASN</th>
<th scope="col">AS name</th>
<th scope="col">RIR</th>
<th scope="col">Country</th>
<th scope="col">State</th>
<th scope="col">PfxRcd</th>
<th scope="col">Up/Down</th>
<th scope="col">Last update</th>
<th scope="col">Up since/last</th>
<th scope="col">Down since/last</th>
</tr>
</thead>
<tbody>
<?php
    while ($d = mysql_fetch_assoc($res)) {
     $as_info_dns = dns_get_record("AS" . $d['asn'] . ".asn.cymru.com", DNS_TXT);
     list($as_info['as'], $as_info['country'], $as_info['rir'], $as_info['date'], $as_info['desc']) = explode("|", $as_info_dns[0]['txt']);
     $asinfo = explode(" ", $as_info['desc']);
     echo "<tr>";
     echo "<td>" . $d['neighbor'] . "</td>";
     echo "<td>" . $d['type'] . "</td>";
     echo "<td>" . $d['asn'] . "</td>";
     echo "<td>" . $asinfo[1] . "</td>";
     echo "<td>" . strtoupper($as_info['rir']) . "</td>";
     echo "<td>" . $as_info['country'] . "</td>";
     if ($d['status']==1) { echo "<td>up</td>"; }
     else { echo "<td>down</td>"; };
     echo "<td>" . $d['prefixes'] . "</td>";
     echo "<td>" . $d['updown'] . "</td>";

     if ($d['time']=='0000-00-00 00:00:00') { echo "<td>never</td>"; }
     else { echo "<td>" . time_diff($d['time']) . "</td>"; };

     if ($d['lastup']=='0000-00-00 00:00:00') { echo "<td>never</td>"; }
     else {
      if ($d['status']==0) { echo "<td>" . $d['lastup'] . "</td>"; }
      else { echo "<td>" . time_diff($d['lastup']) . "</td>"; };
     }

     if ($d['lastdown']=='0000-00-00 00:00:00') { echo "<td>never</td>"; }
     else {
      if ($d['status']==1) { echo "<td>" . $d['lastdown'] . "</td>"; }
      else { echo "<td>" . time_diff($d['lastdown']) . "</td>"; };
     }
     echo "</tr>";
    }
    echo "</tbody>";
    echo "</table>";
    break;
   case 20:
    $res = mysql_query("SELECT * FROM `prefixes` WHERE (`prefix`='$argument') ORDER BY LENGTH(aspath),`neighbor`,(neighbor+0),`neighbor`", $mid);
    $nr = mysql_num_rows($res);
?>
<table id="rounded-corner">
<thead>
<tr>
<th scope="col">Network</th>
<th scope="col">IPv4/6</th>
<th scope="col">Next Hop</th>
<th scope="col">Path</th>
<th scope="col">Community</th>
<th scope="col">Extended<br/>community</th>
<th scope="col">Origin</th>
<th scope="col">Last seen</th>
</tr>
</thead>
<tfoot>
<tr>
<td colspan="8">Total number of paths <?php echo $nr; ?></td>
</tr>
</tfoot>
<tbody>
<?php
    while ($d = mysql_fetch_assoc($res)) {
     echo "<tr>";
     echo "<td>" . $d['prefix'] . "</td>";
     echo "<td>" . $d['type'] . "</td>";
     echo "<td>" . $d['nexthop'] . "</td>";
     echo "<td>" . $d['aspath'] . "</td>";
     echo "<td>" . $d['community'] . "</td>";
     echo "<td>" . $d['extended_community'] . "</td>";
     echo "<td>" . $d['origin'] . "</td>";
     echo "<td>" . $d['time'] . "</td>";
     echo "</tr>";
    }
    echo "</tbody>";
    echo "</table>";
    break;
   case 30:
    $res = mysql_query("SELECT * FROM `prefixes` WHERE (`aspath` LIKE '$argument') ORDER BY `type`,(prefix+0),LENGTH(aspath)", $mid);
    $nr = mysql_num_rows($res);
    if ($nr > 2000) {
     printError ("Number of prefixes greater then 2000");
     return;
    }
?>
<table id="rounded-corner">
<thead>
<tr>
<th scope="col">Network</th>
<th scope="col">IPv4/6</th>
<th scope="col">Next Hop</th>
<th scope="col">Path</th>
<th scope="col">Community</th>
<th scope="col">Extended<br/>community</th>
<th scope="col">Origin</th>
<th scope="col">Last seen</th>
</tr>
</thead>
<tfoot>
<tr>
<td colspan="8">Total number of prefixes <?php echo $nr; ?></td>
</tr>
</tfoot>
<tbody>
<?php
    while ($d = mysql_fetch_assoc($res)) {
     echo "<tr>";
     echo "<td>" . $d['prefix'] . "</td>";
     echo "<td>" . $d['type'] . "</td>";
     echo "<td>" . $d['nexthop'] . "</td>";
     echo "<td>" . $d['aspath'] . "</td>";
     echo "<td>" . $d['community'] . "</td>";
     echo "<td>" . $d['extended_community'] . "</td>";
     echo "<td>" . $d['origin'] . "</td>";
     echo "<td>" . $d['time'] . "</td>";
     echo "</tr>";
    }
    echo "</tbody>";
    echo "</table>";
    break;
   default:
    printError ("Request not supported by router");
    break;
  }

 mysql_close($mid);
}
?>
