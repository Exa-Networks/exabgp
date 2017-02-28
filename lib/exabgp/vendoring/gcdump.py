# http://teethgrinder.co.uk/perm.php?a=Python-memory-leak-detector
import gc
import inspect


def dump():
	# force collection
	print "\nCollecting GARBAGE:"
	gc.collect()
	# prove they have been collected
	print "\nCollecting GARBAGE:"
	gc.collect()

	print "\nGARBAGE OBJECTS:"
	for x in gc.garbage:
		s = str(x)
		if len(s) > 80:
			s = "%s..." % s[:80]

		print "::", s
		print "		type:", type(x)
		print "   referrers:", len(gc.get_referrers(x))
		try:
			print "	is class:", inspect.isclass(type(x))
			print "	  module:", inspect.getmodule(x)

			lines, line_num = inspect.getsourcelines(type(x))
			print "	line num:", line_num
			for l in lines:
				print "		line:", l.rstrip("\n")
		except Exception:
			pass

		print
