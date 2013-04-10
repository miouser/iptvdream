#  Dreambox Enigma2 IPtvDream player! (by technic)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
#########################################################################
####  								BluePointTV created by Snake										###
#########################################################################

from abstract_api import MODE_STREAM, AbstractAPI, AbstractStream
import cookielib, urllib, urllib2 #TODO: optimize imports
from json import loads as json_loads
from datetime import datetime
from . import tdSec, secTd, setSyncTime, syncTime, Bouquet, EpgEntry, Channel, unescapeEntities, Timezone, APIException, SettEntry

# hack !
class JsonWrapper(dict):
	def find(self, key):
		if isinstance(self[key], dict):
			return JsonWrapper(self[key])
		if isinstance(self[key], list):
			return map(JsonWrapper, self[key])
		else:
			return self[key]
	def findtext(self, key):
		return unicode(self[key])

def loads(jsonstr):
	return JsonWrapper(json_loads(jsonstr))

class BluePointAPI(AbstractAPI):
	
	iProvider = "bluepoint"
	NUMBER_PASS = True
	
	site = "http://api.bluepointtv.com"
	
	def __init__(self, username, password):
		AbstractAPI.__init__(self, username, password)

		self.opener = urllib2.build_opener()
		self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 technic-plugin-2.0')]
	
	def start(self):
		self.authorize()
		
	def authorize(self):
		self.trace("Authorization started")
		self.trace("username = %s" % self.username)

		params = urllib.urlencode({"abonement" : self.username,
								  "password" : self.password,
								  "settings" : "all"})
		try:
			reply = self.opener.open(self.site+'/login/login/?'+params+'&dataformat=json&device=enigma').read()
		except IOError as e:
			raise APIException(e)
		try:
			reply = loads(reply)
		except ValueError as e:
			raise APIException(e)
		if reply.has_key("error"):
			err = reply["error"]
			raise APIException(err['message'].encode('utf-8'))
	
		self.sidval = urllib.urlencode({reply['sid_name']: reply['sid'] })
		self.trace(self.sidval)
		
		try:
			self.packet_expire = datetime.fromtimestamp(int(reply['account']['packet_expire']))
		except ValueError:
			pass
		self.trace("Packet expire: %s" % self.packet_expire)
		
		#Load settings here, because kartina api isn't friendly
		self.settings = []
		sett = reply["settings"]
		for (tag,s) in sett.items():
			if tag == "http_caching": continue
			value = s['value']
			vallist = []
			if tag == "stream_server":
				for x in s['list']:
					vallist += [(x['id'].encode('utf-8'), x['descr'].encode('utf-8'))]
			elif s.has_key('list'):
				for x in s['list']:
					vallist += [str(x)]
			self.settings += [SettEntry(tag, value, vallist)]
		for x in self.settings:
			self.trace(x)
		self.SID = True
	
	def getData(self, url, name):
		self.SID = False
		url = self.site + url + "&" + self.sidval + "&dataformat=json&device=enigma"
		
		def doget():
			self.trace("Getting %s" % (name))
			try:
				reply = self.opener.open(url).read()
				print url
				#print reply
			except IOError as e:
				raise APIException(e)
			if reply.startswith('1234'):
				reply = reply[4:]
			try:
				reply = loads(reply)
			except ValueError as e:
				raise APIException(e)
			if reply.has_key("error"):
				err = reply["error"]
				raise APIException(err['message'].encode('utf-8'))
			self.SID = True
			return reply
		
		# First time error occures we retry, next time raise to plugin
		try:
			return doget()
		except APIException as e:
			self.trace("Error %s, retry" % str(e))
			# restart and try again
			self.start()
			return doget()

class Ktv(BluePointAPI, AbstractStream):
	
	iName = "BluePointTV"
	MODE = MODE_STREAM
	
	HAS_PIN = True
	
	def __init__(self, username, password):
		BluePointAPI.__init__(self, username, password)
		AbstractStream.__init__(self)
		self.locked_cids = []
	
	def setChannelsList(self):
		root = self.getData("/channel/list/?autotime=1&", "channels list")
		lst = []
		t_str = root.findtext("servertime").encode("utf-8")
		t_cur = datetime.fromtimestamp(int(t_str))
		setSyncTime(t_cur)
		num = -1
		for group in root.find("groups"):
			title = group.findtext("name").encode("utf-8")
			gnum = int(group.findtext("id"))
			for channel in group.find("channels"):
				num += 1
				name = channel.findtext("name").encode("utf-8")
				id = int(channel.findtext("id").encode("utf-8"))
				archive = channel.findtext("have_archive") and channel.findtext("have_archive") == '1' or 0
				self.channels[id] = Channel(name, title, num, gnum, archive)
				if channel.findtext("protected") and channel.findtext("protected") == '1':
					self.locked_cids += [id]
	
	def setTimeShift(self, timeShift):
		params = {"var" : "timeshift",
				  "val" : timeShift}
		self.getData("/settings/set/?"+urllib.urlencode(params), "time shift new api %s" % timeShift) 

	def getStreamUrl(self, cid, pin, time = None):
		params = {"cid" : cid}
		if time:
			params["gmt"] = time.strftime("%s")
		if pin:
			params["protect_code"] = pin
		root = self.getData("/channel/channel/?"+urllib.urlencode(params)+"&autotime=1", "URL of stream %s" % cid)
		url = root.findtext("url").encode("utf-8").split(' ')[0].replace('http/ts://', 'http://')
		if url == "protected": return self.ACCESS_DENIED
		return url
	
	def getChannelsEpg(self, cids):
		root = self.getData("/channel/list/?autotime=1&", "channels list epg")
		for group in root.find("groups"):
			for channel in group.find("channels"):
				id = int(channel.findtext("id").encode("utf-8"))
				if channel.findtext("epg_start"):
					prog = channel.findtext("epg_progname").encode("utf-8")
					try:
						t_str = channel.findtext("epg_start")
						t_start = datetime.fromtimestamp(int(t_str))
						t_str = channel.findtext("epg_end")
						t_end = datetime.fromtimestamp(int(t_str))
					except ValueError:
						pass
					self.channels[id].epg = EpgEntry(prog, t_start, t_end)
				else:
					print "[KartinaTV] there is no epg for id=%d on ktv-server" % id
					pass

	def getGmtEpg(self, cid, time):
		self.getDayEpg(cid, time)
		self.getDayEpg(cid, time-secTd(24*60*60))

	def getNextGmtEpg(self, cid, time):
		return self.getDayEpg(cid, time)
	
	def getDayEpg(self, cid, date):
		params = {"channel_id" : cid,
		          "date" : date.strftime("%d.%m.%Y")}
		root = self.getData("/channel/program/?"+urllib.urlencode(params)+"&hideprevious=0&autotime=1", "day EPG for channel %s" % cid)
		epglist = []
		for program in root.find('epg'):
			t = int(program.findtext("utc_start"))
			time = datetime.fromtimestamp(t)
			progname = unescapeEntities(program.findtext("progname")).encode("utf-8")
			epglist += [EpgEntry(progname, time, None)]
		self.channels[cid].pushEpgSorted(epglist)

	#FIXME: do we need to load so much data?
	def getCurrentEpg(self, cid):
		return self.getDayEpg(cid, syncTime())

	def getNextEpg(self, cid):
		return self.getDayEpg(cid, syncTime())
		
	def getSettings(self):
		return self.settings
	
	def pushSettings(self, sett):
		for x in sett:
			params = {"var" : x[0],
			          "val" : x[1]}
			self.getData("/settings/set/?"+urllib.urlencode(params), "setting %s" % x[0])
