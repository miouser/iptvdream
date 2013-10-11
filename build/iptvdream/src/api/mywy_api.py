#  Dreambox Enigma2 iptvDream plugin! (by technic - git)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

from abstract_api import MODE_STREAM, AbstractAPI, AbstractStream
import cookielib, urllib, urllib2
from xml.etree.cElementTree import fromstring
from datetime import datetime, time
from md5 import md5
from . import tdSec, secTd, setSyncTime, syncTime, Bouquet, EpgEntry, Channel, unescapeEntities, Timezone, APIException, SettEntry

class MyWyAPI(AbstractAPI):
	
	iProvider = "mywy"
	NUMBER_PASS = False
	
	site = "http://core.sogno.tv/iptv/api/v1/xml"

	def __init__(self, username, password):
		AbstractAPI.__init__(self, username, password)
		
		#self.time_shift = 0
		self.protect_code = ''
		self.cookiejar = cookielib.CookieJar()
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
		self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 technic-plugin-2.x')]
		
	def start(self):
		self.authorize()
		#if self.authorize():
			#params = {'var': 'time_zone,time_shift',
					  #'val':  '%s,%s' % (Timezone, 0) }
			#root = self.getData("/set?"+urllib.urlencode(params), "setting time zone %s and time shift %s" % (Timezone, self.time_shift) )
	
	#def setTimeShift(self, timeShift): #in hours - also timezone 
		#return
		#params = {'var': 'time_shift', #FIXME api bug!!!!
				  #'val': timeShift*60 }
		#return self.getData("/set?"+urllib.urlencode(params), "setting time shift to %s" % timeShift)

	def authorize(self):
		self.trace("Username is "+self.username)
		self.cookiejar.clear()
		params = urllib.urlencode({"login" : self.username,
		                           "pass" : md5(md5(self.username).hexdigest()+md5(self.password).hexdigest()).hexdigest()})
		self.trace("Authorization started (%s)" % (self.site+"/login?with_cfg&with_acc&"+ params))
		try:
			httpstr = self.opener.open(self.site+"/login?with_cfg&with_acc&"+ params).read()
		except IOError as e:
			raise APIException(e)
		try:
			root = fromstring(httpstr)
		except SyntaxError as e:
			raise APIException(e)
		if root.find('error'):
			err = root.find('error')
			raise APIException(err.findtext('code').encode('utf-8')+" "+err.findtext('message').encode('utf-8'))
		self.sid = root.find('sid').text.encode('utf-8')
		self.trace(self.sid)
		self.SID = True
		self.packet_expire = None #XXX: no info in api..
		
		settings = root.find('settings')
		self.protect_code = settings.findtext('parental_pass').encode("utf-8")
		self.trace('protectcode %s' % self.protect_code)
		#print settings.findtext('time_zone')
	 	#if Timezone != int(settings.findtext('time_zone')) or self.time_shift*60 != int(settings.findtext('time_shift')):
	 		#return 1
	 	#return 0
				
	def getData(self, url, name):
		self.SID = False
		url = self.site + url + "&sid=" + self.sid
		
		def doget():
			self.trace("Getting %s (%s)" % (name, url))
			try:
				reply = self.opener.open(url).read()
				#print url
			except IOError as e:
				raise APIException(e)
			try:
				root = fromstring(reply)
			except SyntaxError as e:
				raise APIException(e)
			if root.find('error'):
				err = root.find('error')
				raise APIException(err.find('code').text.encode('utf-8')+" "+err.find('message').text.encode('utf-8'))
			self.SID = True
			return root
		
		# First time error occures we retry, next time raise to plugin
		try:
			return doget()
		except APIException as e:
			self.trace("Error %s, retry" % str(e))
			# restart and try again
			self.start()
			return doget()

	
class Ktv(MyWyAPI, AbstractStream):
	
	iName = "MyWyTV"
	MODE = MODE_STREAM
	
	HAS_PIN = True
	
	def __init__(self, username, password):
		MyWyAPI.__init__(self, username, password)
		AbstractStream.__init__(self)
		self.locked_cids = []
	
	def setChannelsList(self):
		params = {  }
		root = self.getData("/get_list_tv?with_epg&"+urllib.urlencode(params), "channels list")
		t = int(root.findtext('servertime'))
		self.trace('server time %s' % datetime.fromtimestamp(t))
		setSyncTime(datetime.fromtimestamp(t))
		
		groups = root.find('groups')
		for group in groups.findall('item'):
			gid = int(group.findtext('id').encode('utf-8'))
			groupname = group.findtext('user_title').encode('utf-8')
			channels = group.find('channels')
			for channel in channels.findall('item'): 
				id = int(channel.findtext('id').encode('utf-8'))
				name = channel.findtext('name').encode('utf-8')
				num = int(channel.findtext('number').encode('utf-8')) 
				archive = int(channel.findtext('has_archive').encode('utf-8'))
				self.channels[id] = Channel(name, groupname, num, gid, archive)
				if channel.findtext("protected") == '1':
					self.locked_cids += [id]
				if channel.findtext('epg_current_title') and channel.findtext('epg_current_start'):
					prog = channel.findtext('epg_current_title').encode('utf-8') + '\n'
					prog += channel.findtext('epg_current_info').encode('utf-8')
					try:
						t_start = datetime.fromtimestamp(int(channel.findtext('epg_current_start')))
						t_end = datetime.fromtimestamp(int(channel.findtext('epg_current_end').encode('utf-8')))
					except ValueError:
						pass
					self.channels[id].epg = EpgEntry(prog, t_start, t_end)
				if channel.findtext('epg_next_title') and channel.findtext('epg_next_start'):
					prog = channel.findtext('epg_next_title').encode('utf-8') + '\n'
					prog += channel.findtext('epg_next_info').encode('utf-8')
					try:
						t_start = datetime.fromtimestamp(int(channel.findtext('epg_next_start').encode('utf-8')))
						t_end = datetime.fromtimestamp(int(channel.findtext('epg_next_end').encode('utf-8')))
					except ValueError:
						pass
					self.channels[id].nepg = EpgEntry(prog, t_start, t_end)
				else:
					pass

	def getStreamUrl(self, cid, pin, time = None):
		params = {"cid": cid}
		if time:
			params["uts"] = time.strftime("%s")
		if pin:
			params["protect_code"] = pin
		root = self.getData("/get_url_tv?"+urllib.urlencode(params), "stream url")
		url = root.findtext("url").encode("utf-8")
		if url == "protected": return self.ACCESS_DENIED
		return url
	
	def getChannelsEpg(self, cids):
		params = {}
		if len(cids) == 1:
			params['cid'] = cids[0]
		root = self.getData("/get_epg_current?"+urllib.urlencode(params), "getting epg of all channels")
		for channel in root.find('channels'):
			id = int(channel.findtext('id').encode("utf-8"))
			prog = channel.find('current')
			if prog and prog.findtext('begin') and prog.findtext('title'):
				title = prog.findtext('title').encode('utf-8') + '\n'
				title += prog.findtext('info').encode('utf-8')
				try:
					t_start = datetime.fromtimestamp(int(prog.findtext('begin').encode('utf-8')))
					t_end = datetime.fromtimestamp(int(prog.findtext('end').encode('utf-8')))
				except ValueError:
						pass
				self.channels[id].epg = EpgEntry(title, t_start, t_end)
			prog = channel.find('next')
			if prog and prog.findtext('begin') and prog.findtext('title'):
				title = prog.findtext('title').encode('utf-8') + '\n'
				title += prog.findtext('info').encode('utf-8')
				try:
					t_start = datetime.fromtimestamp(int(prog.findtext('begin').encode('utf-8')))
					t_end = datetime.fromtimestamp(int(prog.findtext('end').encode('utf-8')))
				except ValueError:
						pass
				self.channels[id].epg = EpgEntry(title, t_start, t_end)
			else:
				self.channels[id].lastUpdateFailed = True
				pass
	
	def getCurrentEpg(self, cid):
		return self.getChannelsEpg([cid])
	
	def getDayEpg(self, id, date = None):
		if not date:
			date = syncTime()
		params = {"cid": id,
				  "from_uts": datetime(date.year, date.month, date.day).strftime('%s'),
				  "hours" : 24 }
		root = self.getData("/get_epg?"+urllib.urlencode(params), "EPG for channel %s" % id)
		epglist = []
		for prog in root.find('channels').find('item').find('epg'):
			title = prog.findtext('title').encode('utf-8') + '\n'
			title += prog.findtext('info').encode('utf-8')
			try:
				t_start = datetime.fromtimestamp(int(prog.findtext('begin').encode('utf-8')))
				t_end = datetime.fromtimestamp(int(prog.findtext('end').encode('utf-8')))
			except ValueError:
						pass
			epglist += [ EpgEntry(title, t_start, t_end) ]
		self.channels[id].pushEpgSorted(epglist)
	
	def getSettings(self):
		reply = self.getData("/get_settings?", "Get settings")
		return self.parseSettings(reply)
		
	def parseSettings(self, reply):
		settings = {}
#		settings["time zone"] = SettEntry("time_zone", reply.findtext("time_zone"), range(-12, 13))
#		settings["time shift"] = SettEntry("time_shift", reply.findtext("time_shift"), range(0, 24))
		settings["parental pass"] = SettEntry("parental_pass", int(reply.findtext("parental_pass")))
		settings["interface_lng"] = SettEntry("interface_lng", reply.findtext("interface_lng"), ["ru", "de", "en", "ua"])
		mid = reply.findtext("media_server_id")
		mlist = []
		for s in reply.find("media_servers"):
			mlist += [( s.findtext("id"), s.findtext("title").encode('utf-8') )]
		settings["media server"] = SettEntry("media_server_id", mid, mlist)
		
		for x in settings.values():
			self.trace(x)
		return settings

	def pushSettings(self, sett):
		print sett
		var = []
		val = []
		oldpass = self.protect_code
		for x in sett:
			var += [ x[0] ]
			if x[0] == "time_zone":
				val += [ str(int(x[1]) * 60) ]
			else:
				val += [ str(x[1]) ]
			if x[0] == 'parental_pass':
				self.protect_code = x[1]
		var = ','.join(var)
		val = ','.join(val)
		self.getData("/set?var=%s&val=%s&protect_code=%s" % (var, val, oldpass), "Set settings")
