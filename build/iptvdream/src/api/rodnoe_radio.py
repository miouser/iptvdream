#  Dreambox Enigma2 KartinaTV/RodnoeTV player! (by technic)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

from abstract_api import MODE_STREAM, AbstractStream
import urllib
from xml.etree.cElementTree import fromstring
import datetime
from md5 import md5
from . import tdSec, secTd, setSyncTime, syncTime, EpgEntry, Channel
from rodnoe_api import RodnoeAPI

class Ktv(RodnoeAPI, AbstractStream):
	
	iName = "RodnoeRadio"
	MODE = MODE_STREAM
	
	locked_cids = []
	
	def __init__(self, username, password):
		RodnoeAPI.__init__(self, username, password)
		AbstractStream.__init__(self)
	
	def setChannelsList(self):
		root = self.getChannelsList()
		t = int(root.findtext('servertime'))
		self.trace('server time %s' % datetime.datetime.fromtimestamp(t))
		setSyncTime(datetime.datetime.fromtimestamp(t))
		
		groups = root.find('groups')
		for group in groups.findall('item'):
			gid = int(group.findtext('id').encode('utf-8'))
			groupname = group.findtext('name').encode('utf-8')
			channels = group.find('channels')
			for channel in channels.findall('item'): 
				id = int(channel.findtext('id').encode('utf-8'))
				name = channel.findtext('name').encode('utf-8')
				num = int(channel.findtext('number').encode('utf-8')) 
				self.channels[id] = Channel(name, groupname, num, gid)
				
	def getChannelsList(self):
		params = {  }
		return self.getData(self.site+"/get_list_radio"+urllib.urlencode(params), "channels list") 

	def getStreamUrl(self, cid, pin, time = None):
		params = {"cid": cid}
		root = self.getData(self.site+"/get_url_radio?"+urllib.urlencode(params), "stream url")
		return root.findtext("url").encode("utf-8")