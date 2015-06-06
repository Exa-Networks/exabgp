
def formated (line):
	changed_line = '#'
	new_line = line.strip().replace('\t',' ').replace(']',' ]').replace('[','[ ').replace(')',' )').replace('(','( ').replace(',',' , ')
	while new_line != changed_line:
		changed_line = new_line
		new_line = new_line.replace('  ',' ')
	return new_line
