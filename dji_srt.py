#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

#	DJI-style .srt to .gpx converter
#
#	Copyright (c) 2018, Arvid Rudling
#	All rights reserved.
#	Licensed under the Modified BSD License (see LICENSE file)

import re
import os
import argparse
# timezone requires Python ≥ 3.2
import datetime

import xml.etree.ElementTree as etree

CHUNK_PARTS_RE = re.compile(
	'^(\d+)\s+([\d:,]+) --> ([\d:,]+)\s+HOME\((.+)\) ([\d\.]+ [\d:]+)\s+GPS\((.+)\) (.+)$', flags=re.S)
TIME_PATTERN = "%H:%M:%S,000"
DATETIME_PATTERN = "%Y.%m.%d %H:%M:%S"
VIDEO_TIME_FORMAT = "%M:%S"
GPX_UTC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
LOCAL_TIMEZONE = datetime.datetime.utcnow().astimezone().tzinfo
TIME_ZERO = datetime.timedelta(0)

GPX_VERSION = "1.1"


class DJITrackPoint(object):
	def __init__(self, lon, lat, ele, time, extra={}):
		self.lat = lat
		self.lon = lon
		self.ele = ele
		self.time = time
		self.extra = extra

	def __str__(self):
		return ("%s\t(%f,%f,%f)\n%s" % (self.time, self.lon, self.lat, self.ele, self.extra))

	def output_GPX(self, parent, option):
		wpt = etree.SubElement(parent, 'trkpt', lat=str(self.lat), lon=str(self.lon))
		if self.ele and self.ele != 0.0:
			ele = etree.SubElement(wpt, 'ele')
			ele.text = str(self.ele)
		if self.time:
			time = etree.SubElement(wpt, 'time')
			time.text = self.time.astimezone(datetime.timezone.utc).strftime(GPX_UTC_DATETIME_FORMAT)
		return wpt



class Track(object):
	"""Represents a GIS track (multi-segment path between two locations)"""

	def __init__(self, points, name='Untitled', description=None):
		self.points = points
		self.name = name.encode("ascii", errors="ignore").decode()
		self.description = description

	def _make_metadata(self, parent, option=''):
		name = etree.SubElement(parent, 'name')
		name.text = self.name

		if self.description:
			desc = etree.SubElement(parent, 'desc')

			if len(self.description) > 50:
				desc.text = self.description[0:49] + u"…"
			else:
				desc.text = self.description

	def output_GPX(self, parent, option):
		elem = etree.SubElement(parent, 'trk')
		seg = etree.SubElement(elem, 'trkseg')

		assert (len(self.points) > 0)
		for c in self.points:
			c.output_GPX(seg, option)

		self._make_metadata(elem, option)


class GPXDocument(object):
	"""GPX file writer"""

	def __init__(self, name='output'):
		# Make name pure ASCII
		self.name = name.encode("ascii", errors="ignore").decode()
		self.waypoints = []
		self.tracks = []

		self.data = etree.Element('gpx',
                            version=GPX_VERSION,
                            creator='DJI SRT converter',
                            xmlns="http://www.topografix.com/GPX/1/1"
    						)

		self.xml = etree.ElementTree(self.data)

	def add_points(self, wpoint_list):
		for wpoint in wpoint_list:
			self.add_point(wpoint)

	def add_point(self, wpoint):
		self.waypoints.append(wpoint)

	def add_track(self, track):
		self.tracks.append(track)

	def close(self, option=None):
		# Save to XML file

		output_file = open('%s.gpx' % (self.name), 'wb')

		for wp in self.waypoints:
			wp.output_GPX(self.data, option)

		for tr in self.tracks:
			tr.output_GPX(self.data, option)

		self.xml.write(output_file, xml_declaration=True, encoding='utf-8')

# Parse arguments

arg_parser = argparse.ArgumentParser(description='Convert DJI format .srt files to .gpx')

arg_parser.add_argument('input', metavar='SRT', help='Input .srt file path')
args = arg_parser.parse_args()

file_ = open(args.input, 'r')
chunks = re.split('\s{3}', file_.read())
file_.close()

chunk_counter = 1
points = []

for c in chunks:
	if not c:
		break

	chunk_parts = CHUNK_PARTS_RE.match(c).groups()
	chunk_number = int(chunk_parts[0])
	assert chunk_number == chunk_counter, "Inconsistent srt chunk number"
	chunk_counter += 1

	video_begin_time = datetime.datetime.strptime(chunk_parts[1], TIME_PATTERN)
	video_end_time = datetime.datetime.strptime(chunk_parts[2], TIME_PATTERN)
	home_lon, home_lat = chunk_parts[3].split(',')
	local_point_time = datetime.datetime.strptime(chunk_parts[4], DATETIME_PATTERN)
	point_time = datetime.datetime.fromtimestamp(local_point_time.timestamp(), LOCAL_TIMEZONE)

	aircraft_lon, aircraft_lat, aircraft_ele = map(lambda l: float(l), chunk_parts[5].split(','))

	points.append(DJITrackPoint(aircraft_lon, aircraft_lat, aircraft_ele, point_time))

dest_dir, input_filename = os.path.split(args.input)
dest_filename = os.path.splitext(input_filename)[0]
output_doc = GPXDocument(os.path.join(dest_dir, dest_filename))

track = Track(points, dest_filename)
output_doc.add_track(track)
output_doc.close()
