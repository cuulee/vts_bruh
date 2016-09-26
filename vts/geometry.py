

cmd_bits = 3

CMD_MOVE_TO = 1
CMD_LINE_TO = 2
CMD_SEG_END = 7


def param_int(dx):
	return  (dx << 1) ^ (dx >> 31)

def make_multipolygon_geom(listofpolygonlists,f):
	count = 0
	total = []
	for row in listofpolygonlists:
		if count == 0:
			row,lastline = make_cord_list(row,False,multipolygon=True)
			count = 1
		else:
			firstpoint = row[0]
			dx = firstpoint[0] - lastline[0]
			dy = firstpoint[1] -lastline[0]
			row[0] = [dx,dy]
			row,lastline = make_cord_list(row,False,multipolygon=True)
			total += row
		oldrow = row
	return total

def make_multiline_geom(listoflines,f,**kwargs):
	test = False
	for key,value in kwargs.iteritems():
		if key == 'test':
			test = value
	if test == True:
		f = ''
	count = 0
	total = []
	for row in listoflines:
		if count == 0:
			row,lastline = make_cord_list(row,True,f,multipolygon=True,test=test)
			count = 1
			total = row
		else:
			firstpoint = row[0]
			dx = firstpoint[0] - lastline[0]
			dy = firstpoint[1] -lastline[1]
			row[0] = (dx,dy)
			row,lastline = make_cord_list(row,True,f,multipolygon=True,test=test,start=firstpoint)
			total += row
		oldrow = row
	print total
	return total	


def make_point_geom(coords,f):
	geometry = []
	coords = x,y
	f.geometry.append(param_int(x))
	f.geometry.append(param_int(y))
	return geometry

# makes the line geometry list 
def make_line_geom(coords,f):
	return make_cord_list(coords,True,f)

# makes the polygon geometry list
def make_polygon_geom(coords,f):
	return make_cord_list(coords,False,f)

# makes cordinate lists for vector tiles
def make_cord_list(coords,linebool,f,**kwargs):
	multipolygon = False
	multiline = False
	test = False
	start = False
	for key,value in kwargs.iteritems():
		if key == 'multipolygon':
			multipolygon = value 
		if key == 'multiline':
			multiline = value
		if key == 'test':
			test = value
		if key == 'start':
			start = value


	count = 0
	newlist = []
	extents = 8192
	boolthing = False
	geometry = []
	lineto = []
	for row in coords:
		if count == 0:
			count = 1
			dx = row[0]
			dy = row[1]
		else:
			if not start == False:
				oldrow = start
			dx = row[0] - oldrow[0]
			dy = row[1] - oldrow[1]
			count += 1
		# logic for which command to use
		if row == coords[0] and count == 1:
			cmd = CMD_MOVE_TO
		elif row == coords[-1] and count == len(coords) and linebool == False:
			cmd = CMD_SEG_END
		else:
			cmd = CMD_LINE_TO
		oldrow = row

		newrow = (dx,dy,cmd)

		# analyying commands
		if cmd == CMD_MOVE_TO:
			count = 1
			comint = (cmd & 0x7) | (count << 3)
			if test == False:
				f.geometry.append(comint)
			else:
				geometry.append(comint)

			dx,dy = param_int(dx),param_int(dy)
			if test == False:	
				f.geometry.append(dx)
				f.geometry.append(dy)
			else:
				geometry.append(dx)
				geometry.append(dy)
		elif cmd == CMD_LINE_TO:
			lineto.append(param_int(dx))
			lineto.append(param_int(dy))
			linetocmd = cmd
			lastline = [row[0],row[1]]
		elif CMD_SEG_END:
			count = len(lineto) / 2
			comint = (linetocmd & 0x7) | (count << 3)
			if test == False:
				f.geometry.append(comint)
			else:
				geometry.append(comint)
			for row in lineto:
				if test == False:
					f.geometry.append(row)
				else:
					geometry.append(row)

	# logic for if the desired output is a single line
	if linebool == True:

		count = len(lineto) / 2 
		comint = (linetocmd & 0x7) | (count << 3)
		
		if test == False:
			f.geometry.append(comint)
		else:
			geometry.append(comint)
		for row in lineto:
			if test == False:
				f.geometry.append(row)	
			else:
				geometry.append(row)

	# logic for multipolygon
	if multipolygon == True or multiline == True:
		return geometry,lastline

	return f

'''
multiline = [[(2,2),(2,10),(10,10)],[(1,1),(3,5)]]
normie = [(2,2),(2,10),(10,10)]
shape = multiline
for shape in [multiline,normie]:	
	if isinstance(shape[0][0],list) or isinstance(shape[0][0],tuple):
		print 'here'
	else:
		print 'not'

make_multiline_geom(multiline,'',test=True)
'''
'''
print newlist
lineto = []
geometry = []
for row in newlist:
	dx,dy,cmd = row

	if cmd == CMD_MOVE_TO:
		count = 1
		comint = (cmd & 0x7) | (count << 3)
		geometry.append(comint)
		dx,dy = param_int(dx),param_int(dy)
		geometry += [dx,dy]
	elif cmd == CMD_LINE_TO:
		lineto.append(param_int(dx))
		lineto.append(param_int(dy))
		linetocmd = cmd
	elif CMD_SEG_END:
		count = len(lineto) / 2
		comint = (linetocmd & 0x7) | (count << 3)
		geometry.append(comint)
		geometry += lineto

		count = 1
		comint = (cmd & 0x7) | (count << 3)
		geometry.append(comint)


if linebool == True:
	count = len(lineto) / 2 
	comint = comint = (linetocmd & 0x7) | (count << 3)
	geometry.append(comint)
	geometry += lineto
print geometry
print len(geometry)
'''