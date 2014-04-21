#!/usr/bin/php
<?php

/*

DATABASE:

table: blackholes
fields: prefix (TEXT), next-hop (TEXT), community (TEXT), refresh (BOOL);

*/

$dbhost = 'somedbhost';
$dbuser = 'someuser';
$dbpass = 'somepassword';
$dbname = 'somedbname';

// connect to database
try { 
	// dbh = Database Handle
	$dbh = new PDO("mysql:host=$dbhost;dbname=$dbname", $dbuser, $dbpass);
} catch(PDOException $e) {  
    echo $e->getMessage();  
} 



$cache = array();

do {

    // GET ROUTES FROM DATABASE
    $sth = $dbh->prepare('SELECT prefix, next_hop, community FROM blackholes');
    $sth->execute();
    $result = $sth -> fetchAll(); 

	$routes = array();

    foreach($result as $row) {
        $routes[$row["prefix"]]["next-hop"] = $row["next_hop"];
        $routes[$row["prefix"]]["community"] = $row["community"];
    }
    


	// COMPARE ROUTES

	$newroutes = array_diff_assoc($routes, $cache);
	$removedroutes = array_diff_assoc($cache, $routes);
	
	// NOW FEED UPDATES TO EXABGP


	foreach( $newroutes as $key => $route ) {

		echo "announce route " . $key . " next-hop " . $route['next-hop'];
		if($route['community']) echo " community [" . $route['community'] . "]";
		echo "\n";

        // ADD TO CACHE
		$cache[$key] = $route;

	}

    foreach( $removedroutes as $key => $route ) {

        echo "withdraw route " . $key . " next-hop " . $route['next-hop'];
        if($route['community']) echo " community [" . $route['community'] . "]";
        echo "\n";
    
        // REMOVE FROM CACHE
        unset($cache[$key]);

    }

	sleep(5);

} while( true );

?>
