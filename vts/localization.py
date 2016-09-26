from pipeleaflet import *
import berrl as bl
import pandas as pd
import math
from berrl import get_extrema
import itertools
import os
import shutil
from rdp import rdp
import psycopg2

def get_delta(z):
	lat1 = -85.0511
	lat2 = 85.0511
	long1 = -180.0
	long2 = 180.0
	count = 0 
	while count < z:
		deltax = long2 - long1
		long2 = long2 + (deltax /2)
		deltay = lat2 - lat1
		lat2 = lat2 + (deltay /2)		

		count += 1
	return deltax,deltay

def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  xtile = int((lon_deg + 180.0) / 360.0 * n)
  ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
  return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
  n = 2.0 ** zoom
  lon_deg = xtile / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
  lat_deg = math.degrees(lat_rad)
  return (lat_deg, lon_deg)

# creates an extrema dataframe of one tile
def create_extrema_tile(zoom,x,y):
	lat1,long1 = num2deg(x,y,zoom)
	lat2,long2 = num2deg(x+1,y+1,zoom)
	label = str(zoom) + '/' + str(x) + '/' + str(y)

	return pd.DataFrame([[label,lat1,lat2,long1,long2]],columns=['LABEL','SOUTH','NORTH','WEST','EAST'])

def create_extrema_dict(x,y,zoom):
	lat1,long1 = num2deg(x,y,zoom)
	lat2,long2 = num2deg(x+1,y+1,zoom)
	return {'n':max([lat1,lat2]),'s':min([lat1,lat2]),'e':max([long1,long2]),'w':min([long1,long2])}

# will go in pipegeohash
def make_extrema_df(data):
	newdf = pd.DataFrame([],columns=['LAT1', 'LONG1', 'LAT2', 'LONG2', 'LAT3', 'LONG3', 'LAT4', 'LONG4'])
	# lr,ll,ul,ur
	newdf['LAT1'] = data['SOUTH']
	newdf['LONG1'] = data['EAST']

	newdf['LAT2'] = data['SOUTH']	
	newdf['LONG2'] = data['WEST']

	newdf['LAT3'] = data['NORTH'] 
	newdf['LONG3'] = data['WEST']

	newdf['LAT4'] = data['NORTH']
	newdf['LONG4'] = data['EAST']
	newdf['LABEL'] = data['LABEL']
	return newdf


# decoddes the string holding a tile level alignment or polygon field
def my_decode(geometry):
	# parsing through the text geometry to yield what will be rows
	try:
		geometry=str.split(geometry,'(')
		geometry=geometry[-1]
		geometry=str.split(geometry,')')
	except TypeError:
		return [[0,0],[0,0]] 
	# adding logic for if only 2 points are given 
	if len(geometry) == 3:
		newgeometry = str.split(str(geometry[0]),',')
		
	else:
		newgeometry=geometry[:-2][0]
		newgeometry=str.split(newgeometry,',')

	coords=[]
	for row in newgeometry:
		row=str.split(row,' ')
		long=int(row[0])
		lat=int(row[1])
		coords.append([long,lat])

	return coords

def make_extrema_row(zoomval):
	# getting extrema for the given zoom tile
	z,x,y = str.split(zoomval,'/')
	z,x,y = int(x),int(y),int(z)
	extrema = create_extrema_dict(z,x,y)

	return [zoomval,extrema['s'],extrema['n'],extrema['w'],extrema['e']]

# calculates out lat and longs for the level given 
def make_extrema_alignrow(data,level):
	if isinstance(data,pd.DataFrame):
		header = data.columns.values.tolist()
	else:
		data = pd.DataFrame([data[1]],columns=data[0])
		header = data.columns.values.tolist()

	zoomhead = 'zoom' + str(level)
	zoomalign = 'align' + str(level)
	zoomvals = data[zoomhead].values.tolist()[0]
	
	# getting extrema for the given zoom tile
	z,x,y = str.split(zoomvals,'/')
	z,x,y = int(x),int(y),int(z)
	extrema = create_extrema_dict(z,x,y)
	header = ['LABEL','SOUTH','NORTH','WEST','EAST']
	extrema = pd.DataFrame([[zoomvals,extrema['s'],extrema['n'],extrema['w'],extrema['e']]],columns=header)

	return make_extrema(extrema)

# returns a list that can be sent into make line
def make_alignment_level(data,level):
	if isinstance(data,pd.DataFrame):
		header = data.columns.values.tolist()
	else:
		data = pd.DataFrame([data[1]],columns=data[0])
		header = data.columns.values.tolist()
	zoomhead = 'zoom' + str(level)
	zoomalign = 'align' + str(level)
	zoomvals = data[zoomhead].values.tolist()[0]
	encodedalign = data[zoomalign].values.tolist()[0]

	# getting extrema for the given zoom tile
	z,x,y = str.split(zoomvals,'/')
	z,x,y = int(x),int(y),int(z)
	extrema = create_extrema_dict(z,x,y)

	# decoding polyline and taking to X, and Y ints
	alignment = my_decode(encodedalign)
	print alignment
	newdata = pd.DataFrame(alignment,columns=['X','Y'])
	newdata = newdata.astype(int)
	dimx = extrema['e'] - extrema['w']
	dimy = extrema['n'] - extrema['s']

	newdata['LONG'] = (((newdata['X']) / 4096.0 ) * dimx) + extrema['w']
	newdata['LAT'] = (((newdata['Y']) / 4096.0 ) * dimy) + extrema['s']
	
	return newdata

# makes coordinates for each 
def make_cords(zoomvals,xystring):
	alignment = my_decode(xystring)

	# getting extrema for the given zoom tile
	z,x,y = str.split(zoomvals,'/')
	z,x,y = int(x),int(y),int(z)
	extrema = create_extrema_dict(z,x,y)

	# decoding polyline and taking to X, and Y ints
	newdata = pd.DataFrame(alignment,columns=['X','Y'])
	newdata = newdata.astype(int)
	dimx = extrema['e'] - extrema['w']
	dimy = extrema['n'] - extrema['s']

	newdata['LONG'] = (((newdata['X']) / 4096.0 ) * dimx) + extrema['w']
	newdata['LAT'] = -(((newdata['Y']) / 4096.0 ) * dimy) + extrema['n']
 	
	cordstring = my_encode(newdata[['LONG','LAT']].values.tolist())

	return cordstring



# encodes a single cordlist to a string in a simple manner to what postgis databases contain
def my_encode(cordlist):
	total = '(('
	for row in cordlist:
		string = str(row[0]) + ' ' + str(row[1]) + ','
		total += string
	total = total[:-1]
	total = total + '))'
	return total



# trying some functions that will get the layer label as well
# getting and encoding the geometry
# function that relates every df in a grid to  
# df on an alignment or geometric shape
def df_to_grid(df,sizex,sizey,extrema):

	ll = [extrema['w'],extrema['s']]
	dimy = extrema['n'] - extrema['s']
	dimx = extrema['e'] - extrema['w']

	# getting the raw values that each df will use
	df['X'] = ((df['LONG'] - ll[0]) / dimx) * sizex
	df['Y'] = ((extrema['n'] - df['LAT']) / dimy) * sizey

	#df['IND'] = df['X'].astype(int).astype(str) + ',' + df['Y'].astype(int).astype(str)
	df[['X','Y']] = df[['X','Y']].round(0)
	df[['X','Y']] = df[['X','Y']].astype(int)
	
	#df['LONG'] = ll[0] + ((df['X'] / sizex) * dimx)
	#df['LAT'] = ll[1] + ((df['Y'] / sizey) * dimy)

	return df

def add_update_columns(data,dbname):
	print 'starting update'
	# columns to add or update
	row1 = data.columns.values.tolist()[:-1]
	print row1
	
	# connection to database
	string = "dbname=%s user=postgres password=secret" % (dbname)
	conn = psycopg2.connect(string)
	cursor = conn.cursor()

	# adding each column header if it doesn't already exist
	for c in row1:
		if not '5' == c[-1] and not '15' == c[-2:] and not '10' == c[-2:]:
			query = "alter table %s add column %s text" % (dbname,c)	
			cursor.execute(query)

	conn.commit()
	# connection to database
	string = "dbname=%s user=postgres password=secret" % (dbname)
	conn = psycopg2.connect(string)
	cursor = conn.cursor()
	header = data.columns.values.tolist()
	print header
	for row in data[header].values.tolist():
		oldrow = row
		count = 0
		for row in row1:
			string = "update philly set %s='%s' where gid=%s;" % (row,oldrow[count],oldrow[-1])
			cursor.execute(string)
			count += 1

	conn.commit()

def cleanse_complete(data):
	newlist = []
	for row in data.columns.values.tolist():	
		if not 'zoom' in str(row).lower() and not 'align' in str(row).lower():
			newlist.append(row)
	return data[newlist]


# create flat map of alignment data DataFrame
# this function does a few things 
# maps each label tile to 
# unparses the stringed alignment as the name implies
# translates the lat,longs into grid coordinates
# encodes eachset of grid coordinates into a polyline string
def add_postgis_columns(data,zoomsizes,dbname):
	data = cleanse_complete(data)
	header = data.columns.values.tolist()

	newheaders = []
	# geometrtting new zoom headers 
	for row in zoomsizes:
		newheaders.append('ZOOM'+str(row))
		newheaders.append('ALIGN'+str(row))
	header = header + newheaders	

	encodings = []
	newlist = []
	# iterating through each alignment
	for row in data.values.tolist():
		print row[0]
		# holding just the values within a row
		oldrow = row
		
		# extracting the alignment from the string
		alignment = bl.get_lat_long_align(header,row,False)

		# taking the alignment to a dataframes
		alignment = pd.DataFrame(alignment,columns=['LONG','LAT'])

		# getting centroid longx,laty of entire area or line alignment
		longx,laty = alignment['LONG'].mean(),alignment['LAT'].mean()

		# getting which tile it belongs in for each zoom size
		for row in zoomsizes:
			# creating and adding label to the dataframe row
			x,y = deg2num(laty,longx,int(row))
			label = str(row) + '/' + str(x) + '/' + str(y)
			oldrow.append(label)

			# getting the extrema for the tile position we just found
			extrema = create_extrema_dict(x,y,row)
			#bl.make_line(alignment,f='')
			# encodingstringg the linestring or polygon and adding a field for that as well
			data = df_to_grid(alignment,4096,4096,extrema)
			encodingstring = my_encode(data[['X','Y']].values.tolist())

			oldrow.append(encodingstring)
		newlist.append(oldrow)


	newlist = pd.DataFrame(newlist,columns=header)
	sliceheader =  newheaders + ['gid']
	newlist = newlist[sliceheader]
	newlist.to_csv('update.csv',index=False)
	add_update_columns(newlist,dbname)

# this function removes all aspects of geometry and other layers 
# so that dataframes can be smaller in memory 
def cleanse_data(data,size):
	keep1 = 'zoom' + str(size)
	keep2 = 'align' + str(size)
	newheader = []
	for row in data.columns.values.tolist():
		if 'align' in str(row).lower() or 'zoom' in str(row).lower():
			if keep1 == str(row).lower() or keep2 == str(row).lower():
				newheader.append(row)
		elif not 'geom' in str(row).lower() and not 'st_asewkt' in str(row).lower() and not 'update' in str(row).lower() and not 'newsegdate' in str(row).lower():
			newheader.append(row)

	data = data[newheader]
	return data

# groups a data frame by the size a specific size 
# iterates through the dataframe creating dict structure for this size
# this dict structure is used so other things like points or other polygons
# or other lines can later be used in conjunction with it
def group_set_size(data,size,dictionary):
	testfield = 'zoom' + str(size)
	for row in data.columns.values.tolist():
		if testfield == str(row).lower():
			zoomfield = row

	# cleansing data from the fields we dont want
	data = cleanse_data(data,size)
	
	# grouping data by the field just found
	data = data.groupby(zoomfield)

	for name,group in data:
		try:
			dictionary[name].append(group)
		except KeyError:
			dictionary[name] = [group]

	return dictionary

# from a dataframe creates input that will go into the encoder function
# will try to infer filetype eventually prob require specification
def create_input_df_multiline(df,size,tile):
	testfield = 'align' + str(size)
	current = 0
	dictlist = []
	for row in df:
		data = row
		# getting the header value and alignment field
		header = data.columns.values.tolist()
		count = 0
		for row in header:
			if str(row).lower() == testfield:
				alignmentrow = count
				geomtype = 'LineString'
			count += 1
		
		# getting a serial id in which names of features will be generated
		serialid = range(current,current+len(data))
		data['id'] = serialid

		alignments = []
		headerproperties = header[:alignmentrow] + header[alignmentrow+1:]
		for rowdf,idval in itertools.izip(data.values.tolist(),serialid):
			# getting alignment
			alignment = rowdf[alignmentrow]
			alignment = my_decode(alignment)
			#alignment = rdp(alignment,.1)

			# getting feature newame
			featurename = tile + 'id' + str(idval)
			
			# getting properites
			#valueproperties = rowdf[:alignmentrow] + rowdf[alignmentrow+1:]
			valueproperties = rowdf[-1]
			properties = dict(zip(['id'],[len(alignment)]))		

			# making geometry dict
			geom = {'type':geomtype,'coordinates':alignment}

			# parsing into features
			features = [{'geometry':geom,'properties':properties}]

			# making final dictionary entry that will be appended
			dictrow = {'name':featurename,'features':features}

			dictlist.append(dictrow)

		current += len(data)
	return dictlist

# creates a file structure if one doesn't exist for each entry
def create_file_structure(dictionary):
	for row in dictionary.keys():
		nextkeys = dictionary[row].keys()
		string = 'tiles/' + str(row)
		try:
			os.makedirs(string)
		except Exception:
			pass

	for row in dictionary.keys():		
		oldstring = string
		oldrow = row
		nextkeys = dictionary[row].keys()
		for row in nextkeys:
			addrow = str.split(row,'/')
			string = 'tiles/' + addrow[0] + '/' + addrow[1]
			print string
			if not os.path.exists(string):
				os.makedirs(string)

	print 'Directory stucture created.'

# gets the len of cords of alignment column
def derive_size(align):
	return len(str.split(align,' '))

# from a dictionary that will probably be multi level
# size:{tile:,} creates the inputs for each encoder for each tile
def encode_values(dictionary):
	create_file_structure(dictionary)
	# iterating through each dictionary size
	for row in dictionary.keys():
		oldrow = row
		for row in dictionary[oldrow].keys():
			filename = 'tiles/' + str(row) + '.pbf'
			inputdict = create_input_df_multiline(dictionary[oldrow][row],oldrow,row)
			string = vts.encode(inputdict)
			with open(filename,'w') as f:
				f.write(string)

# fora  given size returns a list df of lines with lat,long fields 
# reverse calculated out along with a list of extremas ready to be sent into blocks
def get_size_blocks_lines(data,size):
	print data.columns
	data = cleanse_data(data,size)
	alignfield = 'align' + str(size)
	zoomfield = 'zoom' + str(size)
	newlist = []
	extremas = []
	header = ['LABEL','SOUTH','NORTH','WEST','EAST']
	for row in data[[zoomfield,alignfield]].values.tolist():
		zoomval,alignstring = row
		alignstring = make_cords(zoomval,alignstring)
		extremarow = make_extrema_row(zoomval)
		newlist.append(alignstring)
		extremas.append(extremarow)

	extremadf = pd.DataFrame(extremas,columns=header)
	blocks = make_extrema_df(extremadf)	
	data['st_asewkt'] = newlist
	return data,blocks

def map_colorkey(label):
	global dictval
	return dictval[label]

'''
global dictval
cln()
size = 15
data = bl.get_database('philly')
lines,blocks = get_size_blocks_lines(data,size)
blocks = blocks.groupby('LABEL').first()
blocks = blocks.reset_index()
blocks = bl.unique_groupby(blocks,'LABEL')
dictval = {}
for row in blocks[['LABEL','COLORKEY']].values.tolist():
	dictval[row[0]] = row[1]


lines['COLORKEY'] = lines['zoom'+str(size)].map(map_colorkey)
print lines

bl.make_postgis_lines(lines,'0.geojson',bounds=True)
bl.make_blocks(blocks,f='')
'''
#a(styledicts=[{'color':'COLORKEY','zooms':[7,20]},{'color':'COLORKEY','zooms':[7,20]}])
