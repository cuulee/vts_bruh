from math import fabs
from numbers import Number
from past.builtins import long
from past.builtins import unicode
from past.builtins import xrange

import decimal
from compat import PY3, vector_tile, apply_map

import geometry as h
# tiles are padded by this number of pixels for the current zoom level
padding = 0

cmd_bits = 3
tolerance = 0

CMD_MOVE_TO = 1
CMD_LINE_TO = 2
CMD_SEG_END = 7


def on_invalid_geometry_raise(shape):
    raise ValueError('Invalid geometry: %s' % shape.wkt)


def on_invalid_geometry_ignore(shape):
    return None


def on_invalid_geometry_make_valid(shape):
    if shape.type in ('Polygon', 'MultiPolygon'):
        shape = shape.buffer(0)
        assert shape.is_valid, \
            'buffer(0) did not make geometry valid: %s' % shape.wkt
    return shape


class VectorTile:
    """
    """

    def __init__(self, extents, on_invalid_geometry=None,
                 max_geometry_validate_tries=5, round_fn=None):
        self.tile = vector_tile.tile()
        self.extents = extents
        self.on_invalid_geometry = on_invalid_geometry
        self.max_geometry_validate_tries = max_geometry_validate_tries
        self.round_fn = round_fn

    def _round(self, val):
        # Prefer provided round function.
        if self.round_fn:
            return self.round_fn(val)

        # round() has different behavior in python 2/3
        # For consistency between 2 and 3 we use quantize, however
        # it is slower than the built in round function.
        d = decimal.Decimal(val)
        rounded = d.quantize(1, rounding=decimal.ROUND_HALF_EVEN)
        return float(rounded)

    def addFeatures(self, features, layer_name='',
                    quantize_bounds=None, y_coord_down=False):

        self.layer = self.tile.layers.add()
        self.layer.name = layer_name
        self.layer.version = 1
        self.layer.extent = self.extents

        self.key_idx = 0
        self.val_idx = 0
        self.seen_keys_idx = {}
        self.seen_values_idx = {}

        for feature in features:

            # skip missing or empty geometries
            shape = feature['geometry']['coordinates']
            featuretype = feature['geometry']['type']

            self.addFeature(feature, shape, featuretype)

    def enforce_winding_order(self, shape, y_coord_down, n_try=1):
        if shape.type == 'MultiPolygon':
            # If we are a multipolygon, we need to ensure that the
            # winding orders of the consituent polygons are
            # correct. In particular, the winding order of the
            # interior rings need to be the opposite of the
            # exterior ones, and all interior rings need to follow
            # the exterior one. This is how the end of one polygon
            # and the beginning of another are signaled.
            shape = self.enforce_multipolygon_winding_order(
                shape, y_coord_down, n_try)

        elif shape.type == 'Polygon':
            # Ensure that polygons are also oriented with the
            # appropriate winding order. Their exterior rings must
            # have a clockwise order, which is translated into a
            # clockwise order in MVT's tile-local coordinates with
            # the Y axis in "screen" (i.e: +ve down) configuration.
            # Note that while the Y axis flips, we also invert the
            # Y coordinate to get the tile-local value, which means
            # the clockwise orientation is unchanged.
            shape = self.enforce_polygon_winding_order(
                shape, y_coord_down, n_try)

        # other shapes just get passed through
        return shape

    def quantize(self, shape, bounds):
        minx, miny, maxx, maxy = bounds

        def fn(x, y, z=None):
            xfac = self.extents / (maxx - minx)
            yfac = self.extents / (maxy - miny)
            x = xfac * (x - minx)
            y = yfac * (y - miny)
            return self._round(x), self._round(y)

        return transform(fn, shape)

    def handle_shape_validity(self, shape, y_coord_down, n_try):
        if shape.is_valid:
            return shape

        if n_try >= self.max_geometry_validate_tries:
            # ensure that we don't recurse indefinitely with an
            # invalid geometry handler that doesn't validate
            # geometries
            return None

        if self.on_invalid_geometry:
            shape = self.on_invalid_geometry(shape)
            if shape is not None and not shape.is_empty:
                # this means that we have a handler that might have
                # altered the geometry. We'll run through the process
                # again, but keep track of which attempt we are on to
                # terminate the recursion.
                shape = self.enforce_winding_order(
                    shape, y_coord_down, n_try + 1)

        return shape

    def enforce_multipolygon_winding_order(self, shape, y_coord_down, n_try):
        assert shape.type == 'MultiPolygon'

        parts = []
        for part in shape.geoms:
            part = self.enforce_polygon_winding_order(
                part, y_coord_down, n_try)
            if part is not None and not part.is_empty:
                parts.append(part)

        if not parts:
            return None

        if len(parts) == 1:
            oriented_shape = parts[0]
        else:
            oriented_shape = MultiPolygon(parts)

        oriented_shape = self.handle_shape_validity(
            oriented_shape, y_coord_down, n_try)
        return oriented_shape

    def enforce_polygon_winding_order(self, shape, y_coord_down, n_try):
        assert shape.type == 'Polygon'

        def fn(point):
            x, y = point
            return self._round(x), self._round(y)

        exterior = apply_map(fn, shape.exterior.coords)
        rings = None

        if len(shape.interiors) > 0:
            rings = [apply_map(fn, ring.coords) for ring in shape.interiors]

        sign = 1.0 if y_coord_down else -1.0
        oriented_shape = orient(Polygon(exterior, rings), sign=sign)
        oriented_shape = self.handle_shape_validity(
            oriented_shape, y_coord_down, n_try)
        return oriented_shape

    def _load_geometry(self, geometry_spec):
        if isinstance(geometry_spec, BaseGeometry):
            return geometry_spec

        return load_wkt(geometry_spec)


    def addFeature(self, feature, shape, featuretype):
        f = self.layer.features.add()

        fid = feature.get('id')
        if fid is not None:
            if isinstance(fid, Number) and fid >= 0:
                f.id = fid

        # properties
        properties = feature.get('properties')
        if properties is not None:
            self._handle_attr(self.layer, f, properties)
        f.type = self._get_feature_type(featuretype)

        self._geo_encode(f, shape,featuretype)

    def _get_feature_type(self, shape):
        if shape == 'Point' or shape == 'MultiPoint':
            return self.tile.Point
        elif shape == 'LineString' or shape == 'MultiLineString':
            return self.tile.LineString
        elif shape == 'Polygon' or shape == 'MultiPolygon':
            return self.tile.Polygon
        elif shape.type == 'GeometryCollection':
            raise ValueError('Encoding geometry collections not supported')
        else:
            raise ValueError('Cannot encode unknown geometry type: %s' %
                             shape.type)

    def _encode_cmd_length(self, cmd, length):
        return (length << cmd_bits) | (cmd & ((1 << cmd_bits) - 1))

    def _chunker(self, seq, size):
        return [seq[pos:pos + size] for pos in xrange(0, len(seq), size)]

    def _can_handle_key(self, k):
        return isinstance(k, (str, unicode))

    def _can_handle_val(self, v):
        if isinstance(v, (str, unicode)):
            return True
        elif isinstance(v, bool):
            return True
        elif isinstance(v, (int, long)):
            return True
        elif isinstance(v, float):
            return True

        return False

    def _can_handle_attr(self, k, v):
        return self._can_handle_key(k) and \
            self._can_handle_val(v)

    def _handle_attr(self, layer, feature, props):
        for k, v in props.items():
            if self._can_handle_attr(k, v):
                if not PY3 and isinstance(k, str):
                    k = k.decode('utf-8')

                if k not in self.seen_keys_idx:
                    layer.keys.append(k)
                    self.seen_keys_idx[k] = self.key_idx
                    self.key_idx += 1

                feature.tags.append(self.seen_keys_idx[k])

                if v not in self.seen_values_idx:
                    self.seen_values_idx[v] = self.val_idx
                    self.val_idx += 1

                    val = layer.values.add()
                    if isinstance(v, bool):
                        val.bool_value = v
                    elif isinstance(v, str):
                        if PY3:
                            val.string_value = v
                        else:
                            val.string_value = unicode(v, 'utf-8')
                    elif isinstance(v, unicode):
                        val.string_value = v
                    elif isinstance(v, (int, long)):
                        val.int_value = v
                    elif isinstance(v, float):
                        val.double_value = v

                feature.tags.append(self.seen_values_idx[v])

    def _handle_skipped_last(self, f, skipped_index, cur_x, cur_y, x_, y_):
        last_x = f.geometry[skipped_index - 2]
        last_y = f.geometry[skipped_index - 1]
        last_dx = ((last_x >> 1) ^ (-(last_x & 1)))
        last_dy = ((last_y >> 1) ^ (-(last_y & 1)))
        dx = cur_x - x_ + last_dx
        dy = cur_y - y_ + last_dy
        x_ = cur_x
        y_ = cur_y
        f.geometry.__setitem__(skipped_index - 2, ((dx << 1) ^ (dx >> 31)))
        f.geometry.__setitem__(skipped_index - 1, ((dy << 1) ^ (dy >> 31)))

    def _parseGeometry(self, shape):
        coordinates = []
        lineType = "line"
        polygonType = "polygon"

        def _get_arc_obj(arc, type):
            cmd = CMD_MOVE_TO
            length = len(arc.coords)
            for i, (x, y) in enumerate(arc.coords):
                if i == 0:
                    cmd = CMD_MOVE_TO
                elif i == length - 1 and type == polygonType:
                    cmd = CMD_SEG_END
                else:
                    cmd = CMD_LINE_TO
                coordinates.append((x, y, cmd))

        if shape.type == 'GeometryCollection':
            # do nothing
            coordinates = []

        elif shape.type == 'Point':
            coordinates.append((shape.x, shape.y, CMD_MOVE_TO))

        elif shape.type == 'LineString':
            _get_arc_obj(shape, lineType)

        elif shape.type == 'Polygon':
            rings = [shape.exterior] + list(shape.interiors)
            for ring in rings:
                _get_arc_obj(ring, polygonType)

        elif shape.type == 'MultiPoint':
            coordinates += [(point.x, point.y, CMD_MOVE_TO)
                            for point in shape.geoms]

        elif shape.type == 'MultiLineString':
            for arc in shape.geoms:
                _get_arc_obj(arc, lineType)

        elif shape.type == 'MultiPolygon':
            for polygon in shape.geoms:
                rings = [polygon.exterior] + list(polygon.interiors)
                for ring in rings:
                    _get_arc_obj(ring, polygonType)

        else:
            raise NotImplementedError("Can't do %s geometries" % shape.type)

        return coordinates

    def _geo_encode(self, f, shape,featuretype):
        if featuretype == 'Point':
            h.make_point_geom(shape)
        elif featuretype == 'LineString':
            h.make_line_geom(shape,f)
            #elif isinstance(shape[0][0],list) or isinstance(shape[0][0],tuple):
             #   h.make_multiline_geom(shape,f)

        elif featuretype == 'Polygon':
            h.make_polygon_geom(shape,f)
        elif featuretype == 'MultiLineString':
            h.make_multiline_geom(shape,f)
 
