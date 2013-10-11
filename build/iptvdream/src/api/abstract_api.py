#  Dreambox Enigma2 iptvDream player! (by technic - git)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

from . import Bouquet

DEBUG = True
MODE_STREAM = 0
MODE_VIDEOS = 1

class AbstractAPI(object):
	
	MODE = MODE_STREAM
	iProvider = "free"
	iName = "example"
	iTitle = None #Defaults to iName
	NEXT_API = None 
	NUMBER_PASS = False
	HAS_PIN = False
	URL_DYNAMIC = True
	
	def __init__(self, username, password):
		self.username = username
		self.password = password
		self.SID = False
		self.packet_expire = None
		self.settings = []
	
	def start(self):
		"""Functions that runs on start, and needs exception handling"""
		pass
		
	def trace(self, msg):
		"""Use for API debug"""
		if DEBUG:
			print "[iptvDream] %s: %s" % (self.iName, msg)
	
	def get_hashID(self):
		return hash(self.iName)
	hashID = property(get_hashID)

class AbstractStream(object):
	
	ACCESS_DENIED = 0
	locked_cids = []
	
	def __init__(self):
		self.channels = {}
	
	def setTimeShift(self, timeShift):	
		"""Some services provide timeshift. In hours"""
		pass
	
	def setChannelsList(self): 
		"""Main function for your API: load channel list here.
		   May depend on timeshift. setTimeShift() called first"""
		pass
	
	def getStreamUrl(self, cid, pin, time = None):
		"""Return url of stream here. If <time> is specified then get stream from archive
		   or raise APIException if feature is not supported
		   if <cid> is in locked_cids then <pin> is not None"""
		pass
	
	def getChannelsEpg(self, cids):
		"""Plugin call this fucntion if it wants to access epg current (and next if available)
		   of channel list <cids>.
		   Usually we call this function before show channel list"""
		pass
	
	def getCurrentEpg(self, cid):
		"""Plugin call this fucntion if it wants to access epg current of channel <cid>.
		   If you can download epg next also in this request, do it here to avoid future getNextEpg() calls"""
		pass

	def getNextEpg(self, cid):
		"""Plugin call this fucntion if it wants to access epg next of channel <cid>. 
		   Note, usually epgCurrent() was called just before."""
		pass
	
	def getDayEpg(self, cid, date):
		"""Plugin call this fucntion if it wants to access epg for one day(date) of the channel <cid>.
		   Should push epg to channel."""
		return []
	
	def getPeriodEpg(self, cid, tstart, tend):
		"""Plugin call this fucntion if it wants to access epg for the period from
		   tstart to tend. Time is in datetime format. Should return list of EpgEntry objects"""
		return []
	
	def getGmtEpg(self, cid, time):
		"""Plugin call this function if it wants to access epg that was at give <time>.
		   If you can download epg next that was at give <time> also in this request, do it here."""
		pass
	
	def getNextGmtEpg(self, cid, time):
		pass
	
	def getSettings(self):
		"""Return dict of {"Name": SettEntry, ...}. "Name" is title that user see on screen,
		   SettEntry defined in utils.py"""
		return {}
	
	def pushSettings(self, sett):
		"""<sett> is list of (key, value) tuples.
		   There <key> is SettEntry.name and <value> is SettEntry.value"""
		pass
		
	def getPiconName(self, cid):
		"""You can return reference to cid or to channel name, anything you want ;)"""
		return "%s:%s:" % (self.iName, cid)
	
	def selectAll(self):
		"""You don't need to override this function"""
		services = Bouquet(Bouquet.TYPE_MENU, 'all')
		for cid in self.channels:
			ch = self.channels[cid]
			services.append(Bouquet(Bouquet.TYPE_SERVICE, cid, ch.name, ch.num )) #two sort args [channel_name, number]
		return services
	
	def selectByGroup(self):
		"""You don't need to override this function"""
		glist = {}
		groups = Bouquet(Bouquet.TYPE_MENU, 'By group')
		for cid in self.channels:
			ch = self.channels[cid]
			groupname = ch.group
			if not (groupname in glist.keys()):
				group = Bouquet(Bouquet.TYPE_MENU, groupname, ch.group, ch.groupnum) #two sort args [group_name, number]
				groups.append(group)
				glist[groupname] = group
			glist[groupname].append(Bouquet(Bouquet.TYPE_SERVICE, cid, ch.name, ch.num))
		return groups
