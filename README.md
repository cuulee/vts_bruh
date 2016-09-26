# vts_bruh
a half made module to parse vector tiles 

This module was something I half made about a month of go, its primarily or almost entirely based on mapzens vector tile parser but I rewrote the geometry module. Basically it uses dataframes as a control structure to parse entire vector tile directories. It works pretty decent except I didn't bother to format my postgis database to what it needs for vts to be effective. Basically I found it wasn't worth messing with, using only leaflet-vector-tiles, which is essentially just geojson anyway.

So ya this halfway produces vector tiles from raw dataframes pretty quickly with vector (postgis database style) data and dynamic data like points, if I had a better use for vts currently it would probably be alot better.

Also it makes no attempts to comply with the vt geometry spec, in regards to linting and handling polygons everything else should work.

Thats about it.
