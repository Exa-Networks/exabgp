<?php
 require 'looking-glass-lib.php';
 include 'looking-glass-config.php';
 if (!isset ($router) || !isset ($request))
 {
  printError ('Oops. This installation misses a configuration file (looking-glass-config.php)');
  die();
 }
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<title>looking glass</title>
<style type="text/css">
<!--
@import url("looking-glass.css");
-->
</style>
</head>
<body><center>
<form method="post" action="/">
<table id="hor-minimalist-a">
<thead>
<tr>
<th colspan="2" scope="col" align="center">looking glass</th>
</tr>
</thead>
<tfoot>
<tr>
<td colspan="2"><em>Copyright &copy; Daniel Piekacz, based on modified version of MRLG for PHP by Denis Ovsienkoby</em></td>
</tr>
</tfoot>
<tbody>
<tr>
 <td align="right"><b>router</b><br/><?php printRouterList ($router, $router_list_style); ?></td>
 <td align="left"><b>request</b><br/><?php printRequestList ($request, $request_list_style) ?></td>
</tr>
<tr>
 <td align="right"><b>argument</b><br/><input type="text" name="argument" maxlength="50" value="<?php echo safeOutput (trim ($_REQUEST["argument"])); ?>"/></td>
 <td align="left"><br/><input type="submit" value="Execute"/></td>
</tr>
<tr><td colspan="2"><?php execPreviousRequest ($router, $request); ?></td></tr>
</tbody>
</table>
</form>
</center></body>
</html>
