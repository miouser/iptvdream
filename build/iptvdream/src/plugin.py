# -*- coding: utf-8 -*-
#  Dreambox Enigma2 iptvDream player! (by technic - git)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

#using external player by A. Latsch & Dr. Best (c)
#substantially improved by technic(c) for iptvDream compatibility and buffering possibility!!!
#import servicewebts
SERVICE_LIST = [('1', "enigma2 ts (1)"), ('4097', "gstreamer (4097)"), ('4112', "technic ts (4112)"), ('4114', "partnerbox (4114)")]
SERVICE_DEFAULT = '1'

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap, NumberActionMap, HelpableActionMap
from Components.config import config, ConfigSubsection, ConfigText, ConfigInteger, ConfigSelection, getConfigListEntry, ConfigYesNo, ConfigSubDict, ConfigElement, getKeyNumber, KEY_ASCII, KEY_NUMBERS
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Slider import Slider
from Components.Button import Button
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Components.ServiceEventTracker import ServiceEventTracker, InfoBarBase
from Screens.InfoBarGenerics import InfoBarMenu, InfoBarPlugins, InfoBarExtensions, InfoBarAudioSelection, NumberZap, InfoBarSubtitleSupport, InfoBarNotifications, InfoBarSeek
from Components.MenuList import MenuList
from Screens.MessageBox import MessageBox
from Screens.MinuteInput import MinuteInput
from Screens.ChoiceBox import ChoiceBox
from Screens.InputBox import PinInput, InputBox
from Components.Input import Input
from Components.SelectionList import SelectionList
from Screens.VirtualKeyBoard import VirtualKeyBoard as VirtualKeyBoard_generic
from Tools.BoundFunction import boundFunction
from enigma import eServiceReference, iServiceInformation, eListboxPythonMultiContent, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, gFont, eTimer, iPlayableServicePtr, iStreamedServicePtr, getDesktop, eLabel, eSize, ePoint, getPrevAsciiCode, iPlayableService, ePicLoad
from enigma import eDVBDB
from Screens.Standby import TryQuitMainloop
from Components.AVSwitch import AVSwitch
from urllib import urlretrieve, quote
from Components.ParentalControl import parentalControl
from threading import Thread, Lock, Condition
from enigma import ePythonMessagePump, eBackgroundFileEraser
from Tools.LoadPixmap import LoadPixmap
#from Components.Pixmap import Pixmap
from skin import loadSkin, parseFont, colorNames, SkinError
def parseColor(str): #FIXME: copy-paste form skin source
	if str[0] != '#':
		try:
			return colorNames[str]
		except:
			raise SkinError("color '%s' must be #aarrggbb or valid named color" % (str))
	return int(str[1:], 0x10)

from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_SKIN, SCOPE_SYSETC, SCOPE_CURRENT_PLUGIN
import os
from Components.GUIComponent import GUIComponent
from Components.Sources.Boolean import Boolean
from Components.Sources.StaticText import StaticText
import datetime
from utils import Bouquet, BouquetManager, tdSec, secTd, syncTime, APIException

#for localized messages
from . import _

SKIN_PATH = resolveFilename(SCOPE_SKIN, 'iptvdream_skin')
ENIGMA_CONF_PATH = resolveFilename(SCOPE_SYSETC, 'enigma2')
EPGMAP_PATH = resolveFilename(SCOPE_SYSETC, 'iptvdream')

try:
	sz_w = getDesktop(0).size().width()
	print "[iptvDream] skin width = ", sz_w
except:
	sz_w = 0
	print "[iptvDream] getDesktop fail!"
if sz_w > 1000:
	loadSkin(SKIN_PATH + '/iptvdream_skin.xml')
	NUMS_ON_PAGE = 18
else:
	loadSkin(SKIN_PATH + '/iptvdream_skinsd.xml')
	NUMS_ON_PAGE = 12


class StaticTextService(StaticText):
	service = property(StaticText.getText, StaticText.setText)
	
#text that contain only 0-9 characters..	
class ConfigNumberText(ConfigText):
	def __init__(self, default = ""):
		ConfigText.__init__(self, default, fixed_size = False)

	def handleKey(self, key):
		if key in KEY_NUMBERS or key == KEY_ASCII:
			if key == KEY_ASCII:
				ascii = getPrevAsciiCode()
				if not (48 <= ascii <= 57):
					return
			else:
				ascii = getKeyNumber(key) + 48
  			newChar = unichr(ascii)
			if self.allmarked:
				self.deleteAllChars()
				self.allmarked = False
			self.insertChar(newChar, self.marked_pos, False)
			self.marked_pos += 1
		else:
			ConfigText.handleKey(self, key)

	def onSelect(self, session):
		self.allmarked = (self.value != "")

	def onDeselect(self, session):
		self.marked_pos = 0
		self.offset = 0
		ConfigElement.onDeselect(self, session)
			
config.iptvdream = ConfigSubDict()
#Import apis
from os import path as os_path, listdir as os_listdir, mkdir as os_mkdir
from Tools.Import import my_import
from api.abstract_api import MODE_VIDEOS, MODE_STREAM
PLUGIN_PREFIX = 'Plugins.Extensions.iptvDream'
API_PREFIX = resolveFilename(SCOPE_CURRENT_PLUGIN, 'Extensions/iptvDream/')
API_DIR = 'api'
API_NAME = 'Ktv'
apis = {}
api_providers = []
api_modules = []

for afile in os_listdir(API_PREFIX + API_DIR):
	if afile.endswith('.py'):
		afile = afile[:-3]
	elif afile.endswith('.pyc') or afile.endswith('.pyo'):
		afile = afile[:-4]
	else:
		continue
	if afile in api_modules:
		continue
	else:
		api_modules += [afile]
	print "[iptvDream] found %s" % afile
	_api = my_import('.'.join([PLUGIN_PREFIX, API_DIR, afile]))
	if _api.__dict__.has_key(API_NAME):
		_api = getattr(_api, API_NAME)
		aprov = _api.iProvider
		aname = _api.iName
		if _api.iTitle is None:
			_api.iTitle = _api.iName
		apis[aname] = _api
		if not aprov in api_providers:
			api_providers += [aprov]
		#create config
			config.iptvdream[aprov] = ConfigSubsection()
			if _api.NUMBER_PASS:
				config.iptvdream[aprov].login = ConfigNumberText(default="1111")
				config.iptvdream[aprov].password = ConfigNumberText(default="1111")			
			else:
				config.iptvdream[aprov].login = ConfigText(default="nologin", visible_width = 50, fixed_size = False)
				config.iptvdream[aprov].password = ConfigText(default="nopassword", visible_width = 50, fixed_size = False)
		config.iptvdream[aname] = ConfigSubsection()
		config.iptvdream[aname].in_mainmenu = ConfigYesNo(default=False) 
		config.iptvdream[aname].lastroot = ConfigText(default="[]")
		config.iptvdream[aname].lastcid = ConfigInteger(0, (0,1000))
		config.iptvdream[aname].favourites = ConfigText(default="[]")
		config.iptvdream[aname].service = ConfigSelection(SERVICE_LIST, SERVICE_DEFAULT)
		if _api.MODE == MODE_STREAM:
			config.iptvdream[aname].inbouquet = ConfigYesNo(default=False)
			config.iptvdream[aname].sortkey = ConfigSubDict()
			config.iptvdream[aname].sortkey["all"] = ConfigInteger(1, (1,2))
			config.iptvdream[aname].sortkey["By group"] = ConfigInteger(1, (1,2))
			config.iptvdream[aname].sortkey["in group"] = ConfigInteger(1,(1,2))
		if _api.HAS_PIN == True:
			config.iptvdream[aname].parental_code = ConfigNumberText(default="")
		print "[iptvDream] import api %s:%s" % (aprov, aname)

#buftime is general
config.plugins.iptvDream = ConfigSubsection()
config.plugins.iptvDream.buftime = ConfigInteger(1500, (300,7000) ) #milliseconds!!!


def Plugins(path, **kwargs):
	res = []
	for aname in apis.keys():
		res += [
		PluginDescriptor(name=apis[aname].iTitle, description="IPtvDream plugin by technic", where = PluginDescriptor.WHERE_PLUGINMENU, fnc = boundFunction(AOpen, aname), icon=aname+".png" ),
		PluginDescriptor(name=aname, description="IPtvDream plugin by technic", where = PluginDescriptor.WHERE_MENU, fnc = boundFunction(menuOpen, aname) )]
	res.append(PluginDescriptor(name="IPtvDream config", description="Configure all IPtvDream services", where = PluginDescriptor.WHERE_PLUGINMENU, fnc = selectConfig, icon="iptvdream.png" ))
	return res

class VirtualKeyBoard(VirtualKeyBoard_generic):

	def setLang(self):
		if self.lang == 'ru_RU':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"а", u"б", u"в", u"г", u"д", u"е", u"ж", u"з", u"и", u"й", u"к", u"л"],
				[u"м", u"н", u"о", u"п", u"р", u"с", u"т", u"у", u"ф", u"х", u"ц", "ч"],
				[u"ш", u"щ", u"ь", u"ы", u"ъ", u"э", u"ю", u"я", u"-", ".", u",", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"№", u";", u"%", u":", u"?", u"*", u"(", u")", u"BACKSPACE"],
				[u"А", u"Б", u"В", u"Г", u"Д", u"Е", u"Ж", u"З", u"И", u"Й", u"К", u"Л"],
				[u"М", u"Н", u"О", u"П", u"Р", u"С", u"Т", u"У", u"Ф", u"Х", u"Ц", "Ч"],
				[u"Ш", u"Щ", u"Ь", u"Ы", u"Ъ", u"Э", u"Ю", u"Я", u"ё", "\\", u"/", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.lang = 'ru_RU'
			self.nextLang = 'en_EN'
		else:
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"+", u"@"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"#", u"\\"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"§", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"'", u"?"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.lang = 'en_EN'
			self.nextLang = 'ru_RU'
		self["country"].setText(self.lang)
		self.max_key=47+len(self.keys_list[4])

	def backClicked(self):
		self.text = self["text"].getText().decode('utf-8')[:-1].encode('utf-8')
		self["text"].setText(self.text)


def menuOpen(aname, menuid):
	if menuid == "mainmenu" and config.iptvdream[aname].in_mainmenu.value:
		return [(aname, boundFunction(AOpen, aname), "iptvdream_"+aname, -4)]
	return []
	
def loadEpgMap():
	global epgmap
	epgmap = {}
	f = None
	for fn in os.listdir(EPGMAP_PATH):
		if f: f.close()
		if not fn.endswith('.epgmap'):
			continue
		print "[iptvDream] read", fn
		f = open(EPGMAP_PATH + '/' + fn)
		while True:
			l = f.readline()
			if not l:
				break
			l = l.strip()
			if l.startswith("#"):
				continue
			x = l.split()
			if len(x) < 4:
				print "[iptvDream] Error in epgmap"
				continue
			x[3] = ' '.join(x[3:])
			try:
				epgmap[x[3]] = tuple([int(a, 16) for a in x[:3]])
			except ValueError:
				print "[iptvDream] ValueError in epgmap"
				continue
			except Exception as e:
				print "[iptvDream] epgmap: %s" % e
				continue
		
	
def switchBouquets():
	import re
	added = []
	fname = ENIGMA_CONF_PATH + '/bouquets.tv'
	try:
		f = open(fname)
	except IOError:
		return
	f = f.readlines()
	reg = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"userbouquet\.(.*)\.tv\" ORDER BY bouquet'
	mask = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"userbouquet.%s.tv\" ORDER BY bouquet\n'
	newf = []
	for x in f:
		r = re.match(reg, x)
		if r:
			bname = r.group(1)
			added += [bname]
			if apis.has_key(bname) and not config.iptvdream[bname].inbouquet.value:
				print "[iptvDream] removing %s from bouquets" % bname
				continue
		newf += [x]
	for aname in apis:
		if apis[aname].MODE == MODE_STREAM and config.iptvdream[aname].inbouquet.value and not aname in added:
			print "[iptvDream] adding %s to bouquets" % aname
			newf += [mask % aname]
	f = open(fname, 'w')
	f.writelines(newf)

class RunManager():
	def __init__(self):
		self.session = None
		#Timer to avoid modal open exceptions
		self.timer = eTimer()
		self.timer.callback.append(self._recursiveClose)
		#Standby notifier!!
		config.misc.standbyCounter.addNotifier(self.standbyCountChanged, initial_call = False)
		self.aname = None
		#started apis
		self.started = {}
		self.autostart()
	
	# Start inbouquet apis.
	def autostart(self):
		for aname in apis:
			if apis[aname].MODE == MODE_STREAM and config.iptvdream[aname].inbouquet.value:
				print "[iptvDream] autostart of", aname
				self.apiGetInstance(aname)
		#setup bouqet list
		switchBouquets()
	
	#Player main gui instance
	def _get_kartina_instance(self):
		return KartinaPlayer.instance
	instance = property(_get_kartina_instance)
	
	#Gui is running
	def running(self):
		return self.instance != None
	
	#TODO: fix session staff
	def init(self, session):
		if not self.session:
			self.session = session
	
	#Open gui
	def run(self, aname):
		if self.aname == aname and self.running():
			print "[iptvDream] %s already running" % aname
			return
		self.aname = aname
		if self.running():
			print "[iptvDream] try close recursive to KartinaPlayer"
			self.startRecClose()
		else:
			self.open()
	
	def open(self):
		aname = self.aname
		global Ktv, cfg, cfg_prov, favouritesList
		Ktv = apis[aname]
		cfg = config.iptvdream[aname]
		cfg_prov = config.iptvdream[apis[aname].iProvider]
		favouritesList = eval(cfg.favourites.value)
		if Ktv.MODE == MODE_STREAM:
			self.session.open(KartinaStreamPlayer)
		elif Ktv.MODE == MODE_VIDEOS:
			self.session.open(KartinaVideoPlayer)
	
	#close all dialogs till KartinaPlayer
	def startRecClose(self):
		self.__run_open = False
		assert self.running()
		self._recursiveClose()		  	
		
	def _recursiveClose(self):
		#This may crash if retval needed
		if self.__run_open:
			self.open()
		elif self.session.current_dialog != self.instance:
			print "[iptvDream] closing", self.session.in_exec, self.session.current_dialog 
			try:
				self.session.close(self.session.current_dialog)
			except:
				print "[iptvDream] recursiveClose FAILED!!"
				return
			self.timer.start(1,1)		
		else:
			self.instance.close()
			self.__run_open = True
			self.timer.start(1,1)
	
	def apiStart(self, aname):
		print "[iptvDream] starting", aname
		assert not aname in self.started.keys()
		conf = config.iptvdream[apis[aname].iProvider]
		api = apis[aname](conf.login.value, conf.password.value)
		api.start()
		if api.MODE == MODE_STREAM:
			api.setChannelsList()
			if config.iptvdream[aname].inbouquet.value:
				f = open(ENIGMA_CONF_PATH + '/userbouquet.%s.tv' % aname, 'w')
				f.write('#NAME %s (iptvdream)\n' % api.iTitle)
				mask = '#SERVICE 1:0:1:%X:%X:%X:5A0000:%X:0:%X:%s:%s\n'
				for b in api.selectAll().content:
					cid = b.name
					try:
						sidtuple = epgmap[api.channels[cid].name]
					except KeyError:
						sidtuple = (0,0,0)
					if api.URL_DYNAMIC:
						url = quote('http://127.0.0.1:9000/%s/%s' % (aname, cid))
					else:
						url = api.getStreamUrl(cid, None).replace(":", "%3a")
					f.write(mask % (sidtuple + (api.hashID, cid, url,  api.channels[cid].name)))
					f.write('#DESCRIPTION %s\n' % api.channels[cid].name)
				f.close()
				db = eDVBDB.getInstance()
				db.reloadServicelist()
				db.reloadBouquets()
		self.started[aname] = api
		return api
	
	def apiGetInstance(self, aname):
		if not aname in self.started.keys():
			return self.apiStart(aname)
		else:
			return self.started[aname]

	def apiFailed(self, aname):
		del self.started[aname]

	def getStream(self, aname, cid, *args):
		if not apis[aname].MODE == MODE_STREAM:
			return None
		def do_getStream():
			api = self.apiGetInstance(aname)
			pin = api.HAS_PIN and config.iptvdream[aname].parental_code.value
			return api.getStreamUrl(cid, pin=pin)
		try:
			url = do_getStream()
		except APIException:
			self.apiFailed(aname)
			try:
				url = do_getStream()
			except APIException:
				self.apiFailed(aname)
				return None
		return url

	def standbyCountChanged(self, configElement):
		from Screens.Standby import inStandby
		#FIXME: this is hack!!!
		self.inStandby_cached = inStandby #inStanby resets to None before our onClose :(
		#TODO: think more when run.
		print "[KaritinaTV] add standby callback"
		inStandby.onClose.append(self.leaveStandby)

	#you can use this function to handle standby events ;)
	def leaveStandby(self):
		#next calls of inStandby.close() should not try to run KartinaPlayer.play()
		self.inStandby_cached.onClose.pop()
		print "[iptvDream] debug:", self.inStandby_cached.onClose
		if self.instance:
			self.instance.leaveStandby()


#read epgmap file
loadEpgMap()
#start api runManager
global runManager
runManager = RunManager()
#start server
import server

#We need to save settings before shutdown.
#Small hack here, sorry no alternative
orig_fnc = TryQuitMainloop.close
def edited_fnc(obj, value):
	if value and runManager.running():
		"[iptvDream] shutting down... doExit()"
		runManager.instance.doExit()
	orig_fnc(obj, value)
TryQuitMainloop.close = edited_fnc

def AOpen(aname, session, **kwargs):	
	print "[iptvDream] %s plugin starting" % aname
	runManager.init(session)
	runManager.run(aname)

def atime():
	if bouquet.aTime:
		return syncTime() + secTd(bouquet.aTime)
	else:
		return None


rec_png = LoadPixmap(cached=True, path='/usr/share/enigma2/iptvdream_skin/rec.png')
EPG_UPDATE_INTERVAL = 60 #Seconds, in channel list.
PROGRESS_TIMER = 1000*60 #Update progress in infobar.
PROGRESS_SIZE = 500
ARCHIVE_TIME_FIX = 5 #sec. When archive paused, we could miss some video
AUTO_AUDIOSELECT = True
UPDATE_ON_TOGGLE = True #In video list, when genre selected
USE_VIRTUAL_KB = 1 #XXX: not used!
CLEAN_POSTER_CACHE = 10 #Max posters count to save on hdd. 0 - unlimited 
POSTER_PATH = '/tmp/iptvdream/'

#Manual change aspect ratio in player.
#If videmode system-plugin installed (enigma2 > 20080309)
#Replace "None" with ('16:9 policy', '4:3 policy')
#example:
#MANUAL_ASPECT_RATIO = ('letterbox', 'pillarbox')

MANUAL_ASPECT_RATIO = None

if not os_path.exists(POSTER_PATH):
	os_mkdir(POSTER_PATH)
	

def fakeReference(cid):
	sref = eServiceReference(4112, 0, '') #these are fake references;) #always 4112 because of parental control
	#This big hash is for parentalControl only.
	sref.setData(7, int(str(cid), 16) )
	sref.setData(6, ktv.hashID)
	return sref

#  Reimplementation of InfoBarShowHide
class MyInfoBarShowHide:
	STATE_HIDDEN = 0
	STATE_SHOWN = 1
	
	def __init__(self):
		self.__state = self.STATE_SHOWN
		
		self["ShowHideActions"] = ActionMap( ["InfobarShowHideActions"] ,
			{
				"toggleShow": self.toggleShow,
				"hide": self.hide,
			}, 1) # lower prio to make it possible to override ok and cancel..


		self.hideTimer = eTimer()
		self.hideTimer.callback.append(self.doTimerHide)
		self.hideTimer.start(5000, True)
		
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)
		self.__locked = 0
	
	def serviceStarted(self):
		if self.execing:
			if config.usage.show_infobar_on_zap.value:
				self.doShow()

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		self.startHideTimer()

	def startHideTimer(self):
		if self.__state == self.STATE_SHOWN:
			idx = config.usage.infobar_timeout.index
			if idx:
				self.hideTimer.start(idx*1000, True)

	def __onHide(self):
		self.__state = self.STATE_HIDDEN

	def doShow(self):
		self.show()
		self.startHideTimer()

	def doTimerHide(self):
		self.hideTimer.stop()
		if self.__state == self.STATE_SHOWN:
			self.hide()

	def toggleShow(self):
		if self.__state == self.STATE_SHOWN:
			self.hide()
			self.hideTimer.stop()
		elif self.__state == self.STATE_HIDDEN:
			self.show()
	
	def lockShow(self):
		self.__locked = self.__locked + 1
		if self.execing:
			self.show()
			self.hideTimer.stop()

	def unlockShow(self):
		self.__locked = self.__locked - 1
		if self.execing:
			self.startHideTimer()
	

class KartinaPlayer(Screen, InfoBarBase, InfoBarMenu, InfoBarPlugins, InfoBarExtensions, InfoBarAudioSelection, MyInfoBarShowHide, InfoBarSubtitleSupport, InfoBarNotifications, InfoBarSeek):
	
	subtitles_enabled = False
	ALLOW_SUSPEND = True
	
	instance = None
	
	NOCURR = -1
	
	def __init__(self, session):
		KartinaPlayer.instance = self
		Screen.__init__(self, session)
		InfoBarBase.__init__(self, steal_current_service=True)
		InfoBarMenu.__init__(self)
		InfoBarExtensions.__init__(self)
		InfoBarPlugins.__init__(self)
		InfoBarAudioSelection.__init__(self)
		InfoBarSubtitleSupport.__init__(self)
		InfoBarNotifications.__init__(self)
		MyInfoBarShowHide.__init__(self) #Use myInfoBar because image developers modify InfoBarGenerics
		
		self.setTitle(Ktv.iName)
		self["channelName"] = Label("") #Main label on infobar for all cases.
		
		self.__evtracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedInfo: self.audioSelect,
				iPlayableService.evUpdatedEventInfo: self.__event_play
			})
		self.__audioSelected = False
		
		self.__running = False

		
		self.oldService = self.session.nav.getCurrentlyPlayingServiceReference()
		self.oldAspectRatio = (config.av.policy_169.value, config.av.policy_43.value)
		
		self.onClose.append(self.__onClose)
		self.onShown.append(self.start)
	
	def __event_play(self):
		print "[iptvDream] event can seek"
		self.event_seek()
	
	def event_seek(self):
		pass
	
	#you can use this function to handle standby events ;)
	def leaveStandby(self):
		pass
	
	def __onClose(self):
		print "[iptvDream] closing"
		KartinaPlayer.instance = None
		print "[iptvDream] set instance to None"
		if MANUAL_ASPECT_RATIO:
			(config.av.policy_169.value, config.av.policy_43.value) = self.oldAspectRatio
		#XXX:
		if bouquet:
			self.doExit()
		self.session.nav.playService(self.oldService)
		print "[iptvDream] exiting"
	
	def start(self):		
		if self.start in self.onShown:
			self.onShown.remove(self.start)		
		#If start failed open config dialog
		if not self.go():
			askForRetry(self.session)
	
	def is_runnig(self):
		print "[iptvDream] Check if we running", self.__running
		return self.__running
		
	def go(self):
		self.__running = False			
		self.current = self.NOCURR
		self.oldcid = None
		
		global ktv
		
		global bouquet
		bouquet = BouquetManager()
		
		def processException():
			print "[iptvDream] ERROR login/init failed!"
			self.last_error = str(e)
			print e
		try:
			ktv = runManager.apiGetInstance(runManager.aname)
			self.safeGo()
		except APIException as e:
			processException()
			return False
		self.doGo()
		self.__running = True
		return True
		
			
	def safeGo(self):
		#Do some init functions which require exceptions handling
		pass
	
	def doGo(self):
		#Do other init functions in the end of go()
		pass
						
	#History and channel switching could be usefull in videothek, because they deals with bouquet. 
	def nextChannel(self):
		self.current = bouquet.goNext()
		bouquet.historyAppend()
		self.switchChannel()		
	
	def previousChannel(self):
		self.current = bouquet.goPrev()
		bouquet.historyAppend()
		self.switchChannel()
	
	#FIXME: history and channel zapping forget archive position!   
	def historyNext(self):
		if bouquet.historyNext():
			self.current = bouquet.getCurrent()
			self.switchChannel()
	
	def historyBack(self):
		if bouquet.historyPrev():
			self.current = bouquet.getCurrent()
			self.switchChannel()
		
	def play(self): #check parental control	here	
		print "[iptvDream] access channel id=", self.current 
		cid = self.current
		#if cid not changed (probably we are in  archive)
		if cid == self.oldcid:
			self.startPlay() 
			return
		self.session.nav.stopService()
		
		print "[iptvDream] api has pin", ktv.HAS_PIN
		if ktv.HAS_PIN and cid in ktv.locked_cids:
			codeval = cfg.parental_code.value
		else:
			codeval = None
		if codeval == '':
			print "[iptvDream] protected by api"
			self.session.openWithCallback(self.pinEntered, InputBox, title=_("Enter protect password"),windowTitle = _("Channel Locked"), type=Input.PIN)
			return
		
		#Use many hacks, because it's no possibility to change enigma :(
		#fake reference has no path and used for parental control
		fakeref = fakeReference(cid)
		print fakeref.toCompareString()
		if parentalControl.isServicePlayable(fakeref, boundFunction(self.startPlay)):
			self.pinEntered(codeval)
		else:
			self.playDenied()

	def pinEntered(self, pin):
		if self.startPlay(pin=pin) == 0:
			#this means api access denied
			self.session.openWithCallback(self.retryPlay, MessageBox, _("Access denied!\nTry again?"))
	
	def retryPlay(self, result):
		if result:
			self.play()
		else:
			self.playDenied()
	
	def playDenied(self):
		# clear all infobar fields
		pass

	#return codes:
	#-1 = error
	# 0 = access denied
	def startPlay(self, **kwargs): #TODO: think more..
		print "[iptvDream] play channel id=", self.current 
		self.__audioSelected = False
				

#TODO: Try pause when exit.
#		FIXME: This feature is brocken
#			self.videomode = False
#			if bouquet.aTime:
#				self.playpauseArchive()
#			else:
#				self.play()
			
	def switchChannel(self):
		pass
	
	def showList(self): #Open channels or videos
		pass
	
	def showListCB(self, changed=False):
		if changed:
			self.current = bouquet.getCurrent()
			bouquet.historyAppend()
			self.switchChannel()
		elif bouquet.current.type == Bouquet.TYPE_MENU:
			self.close()
			
	def errorCB(self, edit = False):
		if edit:
			self.kartinaConfig()
		else:
			self.close()

	def restart(self):
		self.session.nav.stopService()
		self.start()
	
	def doExit(self):
		pass
	
	def nextAPI(self):
		if Ktv.NEXT_API:
			runManager.run(Ktv.NEXT_API)
	
	def generate_error(self):
		print "[iptvDream] User generate error for debug"
		raise Exception("User generate error to view log")
	
	#Override and do it safe
	def runPlugin(self, plugin):
		try: 
			plugin(session = self.session)
		except:
			self.session.open(MessageBox, _("You can't run this plugin in iptvDream mode"), MessageBox.TYPE_ERROR)
	
	def audioSelect(self):
		print "[iptvDream] event audio select"
		if self.__audioSelected or not AUTO_AUDIOSELECT: return
		self.__audioSelected = True
		service = self.session.nav.getCurrentService()
		audio = service and service.audioTracks()
		n = audio and audio.getNumberOfTracks() or 0
		if n > 0:
			selectedAudio = audio.getCurrentTrack()
			for x in range(n):
				language = audio.getTrackInfo(x).getLanguage()
				print "[iptvDream] scan langstr:", x, language
				if language.find('rus') > -1 and x != selectedAudio:
					if self.session.nav.getCurrentService().audioTracks().getNumberOfTracks() > x:
						audio.selectTrack(x)
						break


class KartinaStreamPlayer(KartinaPlayer):
	
	def __init__(self, session):	
		KartinaPlayer.__init__(self, session)
		
		#Epg widgets
		self["currentName"] = Label("")
		self["nextName"] = Label("")
		self["currentTime"] = Label("")
		self["nextTime"] = Label("")
		self["currentDuration"] = Label("")
		self["nextDuration"] = Label("")
		self["progressBar"] = Slider(0, PROGRESS_SIZE)
		
		#TODO: think more
		self["archiveDate"] = Label("")
		self["state"] = Label("")
		self["KartinaInArchive"] = Boolean(False)
		self["KartinaPiconRef"] = StaticTextService()
		
		#TODO: actionmap add help.
		
		#disable/enable action map. This method used by e2 developers...
		self["actions"] = ActionMap(["IPdmInfobarActions", "ColorActions"], 
		{
			"closePlugin" : self.close,
			"openVideos" : self.nextAPI,
			"green" : self.openSettings
		}, -1)
		
		self["live_actions"] = ActionMap(["IPdmLiveInfobarActions"], 
		{
			"zapUp" : self.previousChannel,
			"zapDown" : self.nextChannel,
			"openServiceList" : self.showList,  
			"historyNext" : self.historyNext, 
			"historyBack" : self.historyBack,
			"showEPGList" : self.showEpg
		}, -1)
		
		self["archive_actions"] = ActionMap(["IPdmArchiveInfobarActions"], 
		{
			"exitArchive" : self.switchChannel,
			"playpause" : self.playpauseArchive,
			"seekForward" : self.archiveSeekFwd, 
			"seekBackward" : self.archiveSeekRwd,
			"openServiceList" : self.showList,  
			"historyNext" : self.historyNext, 
			"historyBack" : self.historyBack,
			"showEPGList" : self.showEpg
		}, -1)
		
		self["NumberActions"] = NumberActionMap(["NumberActions"],
		{
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
			"0": self.keyNumberGlobal,
		})
		
		self.epgTimer = eTimer()
		self.epgProgressTimer = eTimer()
		self.epgTimer.callback.append(self.epgEvent)
		self.epgProgressTimer.callback.append(self.epgUpdateProgress)
		
		self.archive_pause = 0
	
	def openSettings(self):
		self.session.open(RemoteConfig)
				
	def leaveStandby(self):
		KartinaPlayer.leaveStandby(self)
		#TODO: think more about if check
		if bouquet and KartinaPlayer.instance: #Don't run if plugin closed
			self.play() #in standby stream stops, so we need reconnect..
	
	def doGo(self):
		#init bouquets
		print "[iptvDream] Favourites ids", favouritesList
		fav = Bouquet(Bouquet.TYPE_MENU, 'favourites')
		for x in favouritesList:
			if x in ktv.channels.keys():
				fav.append(Bouquet(Bouquet.TYPE_SERVICE, x))
		bouquet.appendRoot(ktv.selectAll())
		bouquet.appendRoot(ktv.selectByGroup())
		bouquet.appendRoot(fav)
		
		#sort bouquets #TODO: move sorting to utils
		def sortBouquet():
			for x in range(len(bouquet.getList())):
				bouquet.goIn()
				if bouquet.current.type == Bouquet.TYPE_SERVICE:
					bouquet.goOut()
					return
				n = bouquet.current.name
				if cfg.sortkey.has_key(n):
					bouquet.current.sortByKey(cfg.sortkey[n].value)
				else:
					bouquet.current.sortByKey(cfg.sortkey['in group'].value)
				if bouquet.current.type == Bouquet.TYPE_MENU:
					sortBouquet()
				bouquet.goOut()
				bouquet.current.index += 1
			bouquet.current.index = 0
		
		sortBouquet()
		bouquet.current = bouquet.root
	
		#apply parentalControl
		for x in Ktv.locked_cids: #Ktv.locked_ids:
			sref = fakeReference(x)
			print "[iptvDream] protect", sref.toCompareString()
			parentalControl.protectService(sref.toCompareString())
		
		#startup service	
		self.setArchivemode(0)
		print "[iptvDream] set path to", cfg.lastroot.value, cfg.lastcid.value
		bouquet.setPath(eval(cfg.lastroot.value), cfg.lastcid.value)
		print "[iptvDream] now bouquet.current is", bouquet.current.name 
		if bouquet.current.type == Bouquet.TYPE_MENU:
			self.showList()
		elif bouquet.current.type == Bouquet.TYPE_SERVICE:
			self.current = bouquet.getCurrent()
			bouquet.historyAppend()
			self.play()
	
	def doExit(self):
		cfg.lastroot.value = str(bouquet.getPath())
		cfg.lastcid.value = self.current
		print "[iptvDream] save path", cfg.lastroot.value, cfg.lastcid.value
		cfg.lastroot.save()
		cfg.lastcid.save()
		cfg.favourites.value = str(favouritesList)
		cfg.favourites.save()
		cfg.sortkey.save()
		
	def archiveSeekFwd(self):
		self.session.openWithCallback(self.fwdJumpTo, MinuteInput)
			
	def archiveSeekRwd(self):
		self.session.openWithCallback(self.rwdJumpTo, MinuteInput)
	
	def fwdJumpTo(self, minutes):
		print "[iptvDream] Seek", minutes, "minutes forward"
		bouquet.aTime += minutes*60
		if bouquet.aTime > 0:
			self.setArchivemode(0)
		self.play()

	def rwdJumpTo(self, minutes):
		print "[iptvDream] rwdSeekTo", minutes
		bouquet.aTime -= minutes*60
		self.play()
		
	def playpauseArchive(self):
		if self.archive_pause: #do unpause
			bouquet.aTime -= tdSec(syncTime()-self.archive_pause)-ARCHIVE_TIME_FIX
			self.archive_pause = None
			self.play()
			self.unlockShow()
		else: #do pause
			self.archive_pause = syncTime()
			self.session.nav.stopService()
			self.lockShow()
	
	def startPlay(self, **kwargs):
		KartinaPlayer.startPlay(self)
		if kwargs.has_key('pin'):
			pin = kwargs['pin']
		else:
			pin = None
		
		cid = self.current
		try:
			uri = ktv.getStreamUrl(cid, pin, atime())
		except APIException:
			print "[iptvDream] Error: getting stream uri failed!"
			#self.session.open(MessageBox, _("Error while getting stream uri"), type = MessageBox.TYPE_ERROR, timeout = 5)
			return -1
		
		if not uri:
			return 0
		print "[iptvDream] play", uri
		srv = int(cfg.service.value)
#		if not uri.startswith('http://'):
#			srv = 4097
		if uri.startswith('mms://'):
			print "[iptvDream] Warning: mms:// protocol turned off"
			self.session.open(MessageBox, _("mms:// protocol turned off"), type = MessageBox.TYPE_ERROR, timeout = 5)
			return -1
			
		sref = eServiceReference(srv, 0, uri)
		self.session.nav.playService(sref)
		self.oldcid = self.current
		
		self["KartinaPiconRef"].text = ktv.getPiconName(cid)
		self["channelName"].setText(ktv.channels[cid].name)
		self.epgEvent()
	
	def playDenied(self):
		#show channel name infobar
		self["channelName"].setText(ktv.channels[self.current].name)
		self.epgEvent()


	
	def epgEvent(self):
		#first stop timers
		self.epgTimer.stop()
		self.epgProgressTimer.stop()
		cid = self.current
		
		#EPG is valid only if bouth tstart and tend specified!!! Check utils.
		time = syncTime() + secTd(bouquet.aTime)
		def setEpgCurrent():
			curr = ktv.channels[cid].epgCurrent(time)
			if not curr:
				return False

			self.currentEpg = curr
			self["currentName"].setText(curr.name)
			self["currentTime"].setText(curr.tstart.strftime("%H:%M"))
			self["nextTime"].setText(curr.tend.strftime("%H:%M"))
			self.epgTimer.start(curr.getTimeLeftmsec(time) +1000) #milliseconds
			self["currentDuration"].setText("+%d min" % (curr.getTimeLeft(time) / 60) )
			self["progressBar"].setValue(PROGRESS_SIZE * curr.getTimePass(time) / curr.duration)
			self.epgProgressTimer.start(PROGRESS_TIMER)
			if bouquet.aTime:
				self["archiveDate"].setText(curr.tstart.strftime("%d.%m"))
				self["archiveDate"].show()
			else:
				self["archiveDate"].hide()
			return True
		
		if not setEpgCurrent():
			try:
				if bouquet.aTime:
					ktv.getGmtEpg(cid, time)
				else:
					ktv.getCurrentEpg(cid)
			except APIException:
				print "[iptvDream] ERROR load epg failed! cid =", cid, bool(bouquet.aTime)
			if not setEpgCurrent():
				self["currentName"].setText('')
				self["currentTime"].setText('')
				self["nextTime"].setText('')
				self["currentDuration"].setText('')
				self["progressBar"].setValue(0)	
				
		def setEpgNext():
			next = ktv.channels[cid].epgNext(time)
			if not next:
				return False
			self['nextName'].setText(next.name)
			self['nextDuration'].setText("%d min" % (next.duration/ 60))
			return True
		
		if not setEpgNext():
			try:
				if bouquet.aTime:
					ktv.getNextGmtEpg(cid, time)
				else:
					ktv.getNextEpg(cid)
			except APIException:
				print "[iptvDream] load epg next failed!"
			if not setEpgNext():
				self["nextName"].setText('')
				self["nextDuration"].setText('')
						
		self.serviceStarted() #ShowInfoBar #FIXME: only if focused
		
	def epgUpdateProgress(self):
		time = syncTime() + secTd(bouquet.aTime)
		self["currentDuration"].setText("+%d min" % (self.currentEpg.getTimeLeft(time)/60) )
		self["progressBar"].setValue(PROGRESS_SIZE * self.currentEpg.getTimePass(time) / self.currentEpg.duration)
		self.epgProgressTimer.start(PROGRESS_TIMER)
	
	def setArchivemode(self, aTime):
		bouquet.aTime = aTime
		if aTime:
			self.archive_pause = None
			self["live_actions"].setEnabled(0)
			self["archive_actions"].setEnabled(1)
			self["KartinaInArchive"].setBoolean(True)
		else:
			self["archive_actions"].setEnabled(0)
			self["live_actions"].setEnabled(1)
			self["KartinaInArchive"].setBoolean(False)

	def showEpg(self):
		self.session.openWithCallback(self.showEpgCB, KartinaEpgList, self.current)
	
	def showEpgCB(self, time= None):
		if time:
			self.current = bouquet.getCurrent()
			self.setArchivemode(tdSec(time-syncTime())) #aTime < 0
			self.play()
	
	def showList(self):
		self.session.openWithCallback(self.showListCB, KartinaChannelSelection)
	
	def showListCB(self, changed=False, time = None):
		if time:
			print "[iptvDream] list returned archive" 
			self.showEpgCB(time)
			return
		else:
			return KartinaPlayer.showListCB(self, changed)
	
	def switchChannel(self):
		self.setArchivemode(0)
		self.play()
		
	def keyNumberGlobal(self, number):
		self.session.openWithCallback(self.numberEntered, NumberZap, number)
	
	def numberEntered(self, num):
		if num > 0:
			lastroot = bouquet.current
			bouquet.current = bouquet.root
			bouquet.goIn(2)
			num -= 1 #True enumeration starts from zero :)
			if num < len(bouquet.current.content):
				bouquet.setIndex(num)
				bouquet.goIn()
				self.current = bouquet.getCurrent()
				bouquet.historyAppend()
				self.switchChannel()
			else:
				bouquet.current = lastroot	



class KartinaVideoPlayer(KartinaPlayer):
	def __init__(self, session):
		KartinaPlayer.__init__(self, session)
			
		self["video_actions"] = ActionMap(["IPdmVideoInfobarActions"], 
		{
			"zapUp" : self.nextChannel,
			"zapDown" : self.previousChannel, 
			"openServiceList" : self.showList,  
			"openTV" : self.nextAPI,
			"stopVideo" : self.stop,
			"closePlugin" : self.close
		}, -1)
		
		self["poster"] = WeatherIcon()
		self["description"] = Label()
		
		InfoBarSeek.__init__(self)
		
		self.is_playing = False
	
	def startPlay(self, **kwargs):
		KartinaPlayer.startPlay(self)
		
		cid = self.current
		try:
			uri = ktv.getVideoUrl(cid)
		except APIException:
			print "[iptvDream] Error: getting video uri failed!"
			self.session.open(MessageBox, _("Error while getting video uri"), type = MessageBox.TYPE_ERROR, timeout = 5)
			return -1
		
		sref = eServiceReference(4097, 0, uri) #TODO: think about serviceID
		self.session.nav.playService(sref)
		self.is_playing = True
		
		if MANUAL_ASPECT_RATIO is not None:
			(config.av.policy_169.value, config.av.policy_43.value) = MANUAL_ASPECT_RATIO
		self["channelName"].setText(ktv.filmFiles[cid]['name']) #FIXME: videos dict could be cleaned empty o_O
		vid = bouquet.current.parent.name #Video is parent, episode is current
		self["description"].setText(ktv.videos[vid].descr)
		poster_path = POSTER_PATH + ktv.getPosterPath(vid, local = True)
		self["poster"].updateIcon(poster_path)
	
	def showList(self):
		self.session.openWithCallback(self.showListCB, KartinaVideoList)
	
	def switchChannel(self):
		self.play()
		
	def doGo(self):
		(vid, fid, play_pos) = eval(cfg.lastroot.value) or (0, 0, 0)
		self.play_pos = play_pos
		if play_pos == 0 or vid == self.NOCURR or fid == self.NOCURR:
			self.showList()
		else:
			ktv.getVideoInfo(vid)
			bouquet.appendRoot(ktv.buildEpisodesBouquet(vid))
			bouquet.goIn()
			for idx in range(len(bouquet.current.content)):
				if bouquet.current.content[idx].name == fid:
					break
			bouquet.goIn(idx)
			self.current = bouquet.getCurrent()
			bouquet.historyAppend()
			self.switchChannel()
			#print "[iptvDream] seek to saved", play_pos
			#self.doSeekRelative(play_pos)
	
	def event_seek(self):
		if self.play_pos == 0: return
		x = self.ptsGetPosition()
		print "[iptvDream] at", x
		print "[iptvDream] seek to saved", self.play_pos
		self.doSeekRelative(self.play_pos-x-10000)
		self.play_pos = 0
	
	def ptsGetPosition(self):
		seek = self.getSeek()
		if seek:
			p = seek.getPlayPosition()
			if not p[0]:
				return p[1]
		return 0
	
	def doExit(self):
		if bouquet.current.type == Bouquet.TYPE_MENU or self.is_playing == False:
			last = (0, 0, 0)
		elif self.is_playing:
			fid = self.current
			vid = bouquet.current.parent.name #Video is parent, episode is current
			play_pos = self.ptsGetPosition()
			last = (vid, fid, play_pos)
		print "[iptvDream] save play position", last[2]
		cfg.lastroot.value = str(last)
		cfg.lastroot.save()
	
	def doEofInternal(self, playing):
		#TODO: we can't figure out is it serial.
		print "[iptvDream] EOF. playing", playing
		seek = self.getSeek()
		if seek is None:
			return
		l = seek.getLength()
		p = seek.getPlayPosition()
		if not l[0] and not p[0]:
			l = l[1]
			p = p[1]
			if p*100.0/l > 90: #Hack to filter only eofs at end.
				self.is_playing = False
				print "[iptvDream] movie ended."
				if self.execing: self.showList()
				
		print "[iptvDream] l=", seek.getLength(), ' p=', seek.getPlayPosition()
	
	def stop(self):
		self.session.nav.stopService()
		self.is_playing = False
		print "[iptvDream] movie stop."
		bouquet.goOut()
		self.showList()
	
	def seekFwd(self):
		self.seekFwdManual()
	def seekBack(self):
		self.seekBackManual()
				
#TODO: BouquetManager guiContent. Don't recreate and refill ChannelSelection if possible
class ChannelList(MenuList):
	
	def __init__(self):
		MenuList.__init__(self, [], content = eListboxPythonMultiContent, enableWrapAround=True)
		self.col = {}
		
		self.pixmapProgressBar = None
		self.pixmapArchive = None
		self.itemHeight = 28
		self.l.setFont(0, parseFont("Regular;22", ((1,1),(1,1))) )
		self.l.setFont(1, parseFont("Regular;18", ((1,1),(1,1))) )
		self.l.setFont(2, parseFont("Regular;20", ((1,1),(1,1))) )
		self.num = 0
		
		for x in ["colorEventProgressbar", "colorEventProgressbarSelected", "colorEventProgressbarBorder", "colorEventProgressbarBorderSelected", "colorServiceDescription", "colorServiceDescriptionSelected"]:
			self.col[x] = None
	
	def postWidgetCreate(self, instance):
		MenuList.postWidgetCreate(self, instance)
		self.showEpgProgress = config.usage.show_event_progress_in_servicelist.value
		#Can't access eTextPara directly :(
		self.fontCalc = [eLabel(self.instance), eLabel(self.instance), eLabel(self.instance)]
		self.fontCalc[0].setFont(parseFont("Regular;22", ((1,1),(1,1))) )
		self.fontCalc[1].setFont(parseFont("Regular;18", ((1,1),(1,1))) )
		self.fontCalc[2].setFont(parseFont("Regular;20", ((1,1),(1,1))) )
		
		
	def applySkin(self, desktop, parent):
		attribs = [ ]
		if self.skinAttributes is not None:
			attribs = [ ]
			for (attrib, value) in self.skinAttributes:
#				if attrib == "foregroundColorMarked":
#					self.col[attrib] = parseColor(value)
#				elif attrib == "foregroundColorMarkedSelected":
#					self.col[attrib] = parseColor(value)
#				elif attrib == "backgroundColorMarked":
#					self.col[attrib] = parseColor(value)
#				elif attrib == "backgroundColorMarkedSelected":
#					self.col[attrib] = parseColor(value)
#				elif attrib == "foregroundColorServiceNotAvail":
#					self.col[attrib] = parseColor(value)
				if attrib == "colorEventProgressbar":
					self.col[attrib] = parseColor(value)
				elif attrib == "colorEventProgressbarSelected":
					self.col[attrib] = parseColor(value)
				elif attrib == "colorEventProgressbarBorder":
					self.col[attrib] = parseColor(value)
				elif attrib == "colorEventProgressbarBorderSelected":
					self.col[attrib] = parseColor(value)
				elif attrib == "colorServiceDescription":
					self.col[attrib] = parseColor(value)
				elif attrib == "colorServiceDescriptionSelected":
					self.col[attrib] = parseColor(value)
				elif attrib == "picServiceEventProgressbar":
					pic = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, value))
					if pic:
						self.pixmapProgressBar = pic
				elif attrib == "picServiceArchive":
					pic = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, value))
					if pic:
						self.pixmapArchive = pic
				elif attrib == "serviceItemHeight":
					self.itemHeight = int(value)
				elif attrib == "serviceNameFont":
					self.l.setFont(0, parseFont(value, ((1,1),(1,1))) )
					self.fontCalc[0].setFont( parseFont(value, ((1,1),(1,1))) )
				elif attrib == "serviceInfoFont":
					self.l.setFont(1, parseFont(value, ((1,1),(1,1))) )
					self.fontCalc[1].setFont( parseFont(value, ((1,1),(1,1))) )
				elif attrib == "serviceNumberFont":
					self.l.setFont(2, parseFont(value, ((1,1),(1,1))) )
					self.fontCalc[2].setFont( parseFont(value, ((1,1),(1,1))) )
				else:
					attribs.append((attrib, value))
					
		self.skinAttributes = attribs
		res = GUIComponent.applySkin(self, desktop, parent)
		
		self.l.setItemHeight(self.itemHeight)
		self.itemWidth = self.instance.size().width()
		for x in self.fontCalc:
			#resize and move away.			
			x.resize(eSize(self.itemWidth, self.itemHeight)) #?
			x.move(ePoint(int(self.instance.size().width()+10), int(self.instance.size().height()+10)))
			x.setNoWrap(1)
		return res
	
	def setEnumerated(self, enumerated):
		if enumerated:
			self.num = 1
		else:
			self.num = 0
	
	def setList(self, list):
		self.l.setList(map(self.buildChannelEntry, list))
		if self.num:
			self.num = 1
	
	def calculateWidth(self, text, font):
		self.fontCalc[font].setText(text)
		return int(round(self.fontCalc[font].calculateSize().width()*1.1))
	
	
	def buildChannelEntry(self, entry):
		defaultFlag = RT_HALIGN_LEFT | RT_VALIGN_CENTER
		if entry.type == Bouquet.TYPE_MENU:
			return [
				(entry.name),
				( eListboxPythonMultiContent.TYPE_TEXT, 0, 0, self.itemWidth, self.itemHeight, 0, defaultFlag, entry.name )]
		
		#Filling from left to rigth
		elif entry.type == Bouquet.TYPE_SERVICE:
			
			cid = entry.name
			lst = [(cid)]
			xoffset = 1
			
			if self.num:
				xoffset += 55
				text = str(self.num)
				lst += [(eListboxPythonMultiContent.TYPE_TEXT, 0, 0, xoffset-5, self.itemHeight, 2, RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text )]
				self.num += 1
			
			if self.pixmapArchive: 
				width = self.pixmapArchive.size().width()
				height = self.pixmapArchive.size().height()
				if ktv.channels[cid].archive:
					lst += [(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, xoffset, (self.itemHeight-height)/2, width, height, self.pixmapArchive)]  	
				xoffset += width+5
			
			epg = ktv.channels[cid].epgCurrent()
			
			if self.showEpgProgress: 
				width = 52
				height = 6
				if epg:
					percent = 100*epg.getTimePass() / epg.duration
					lst += [(eListboxPythonMultiContent.TYPE_PROGRESS, xoffset+1, (self.itemHeight-height)/2, width, height, percent, 0, self.col['colorEventProgressbar'], self.col['colorEventProgressbarSelected'] ),
							(eListboxPythonMultiContent.TYPE_PROGRESS, xoffset, (self.itemHeight-height)/2 -1, width+2, height+2, 0, 1, self.col['colorEventProgressbarBorder'], self.col['colorEventProgressbarBorderSelected'] )]	
				xoffset += width+7
			
			#skin_local colors...
			text = str(ktv.channels[cid].name)
			width = self.calculateWidth(text, 0)
			lst += [(eListboxPythonMultiContent.TYPE_TEXT, xoffset, 0, width, self.itemHeight, 0, defaultFlag, text )]
			xoffset += width+10
			
			if epg:
				text = '(%s)' % epg.progName #sholdn't contain \n
				#width = self.calculateWidth(text, 1)
				lst += [(eListboxPythonMultiContent.TYPE_TEXT, xoffset, 0, self.itemWidth, self.itemHeight, 1, defaultFlag, text, self.col['colorServiceDescription'], self.col['colorServiceDescriptionSelected'] )]
			
			return lst
	
class KartinaChannelSelection(Screen):

	def __init__(self, session):
		Screen.__init__(self, session)
		
		self["key_red"] = Button(_("All"))
		self["key_green"] = Button(_("Groups"))
		self["key_yellow"] = Button(_("Add"))
		self["key_blue"] = Button(_("Favourites"))
		
		self["list"] = ChannelList()
		self.list = self["list"]
		
		self["epgName"]=Label("")
		self["epgTime"]=Label("")
		self["epgDescription"] = Label("")
		self["channelName"]=Label()
		self["epgProgress"]=Slider(0, 100)
		self["epgNextTime"]=Label()
		self["epgNextName"]=Label()
		self["epgNextDescription"]=Label()
		
		self["packetExpire"] = Label()
		if ktv.packet_expire:
			self["packetExpire"].setText(_("Expire on")+" "+ktv.packet_expire.strftime('%d.%m %H:%M'))		
		
		self["actions"] = ActionMap(["OkCancelActions", "IPdmChannelListActions"], 
		{
			"cancel": self.exit,
			"ok" : self.ok,
			"showAll" : self.showAll,
			"showGroups" : self.showByGroup,
			"addFavourites" : self.addremoveFavourites,
			"showFavourites" : self.showFavourites,
			"contextMenu" : self.showMenu,
			"showEPGList" : self.showEpgList,
			"nextBouquet" : self.nextBouquet,
			"prevBouquet" : self.prevBouquet
		}, -1)
		
		self.list.onSelectionChanged.append(self.selectionChanged)
		self.lastroot = bouquet.current
		self.editMode = False
		self.editMoving = False
		self.lastEpgUpdate = None
		#need to create GUI first for changing it's parameters later
		#for example list.moveToIndex don't work otherwise		  
		self.onLayoutFinish.append(self.start)
		
		
	def start(self):
		if bouquet.root == bouquet.current:
			print "[iptvDream] lastroot not found show All"
			self.showByGroup()
		else:
			bouquet.goOut()
			self.fillList()
	
	def ok(self):
		if self.editMode:
			self.editMoving = not self.editMoving
			self.lastIndex = self.list.getSelectionIndex()
			return
		try:
			bouquet.goIn()
		except IndexError:
			print "[iptvDream] selection empty!"
		if bouquet.current.type == Bouquet.TYPE_SERVICE:
			print "[iptvDream] ChannelSelection close"
			self.list.onSelectionChanged.pop() #Do it before close, else event happed while close.
			self.close(True)
		elif bouquet.current.type == Bouquet.TYPE_MENU:
			self.fillList()
	
	def exit(self):
		self.list.onSelectionChanged.pop() #Do it before close, else event happed while close.
		bouquet.current = self.lastroot
		self.close(False)
	
	def fillList(self):
		#FIXME: optimizations? Autoupdate.
		uplist = []
		
		timeout = not self.lastEpgUpdate or syncTime() - self.lastEpgUpdate > secTd(EPG_UPDATE_INTERVAL)
		for x in ktv.channels.keys():
			if isinstance(x, int):
				if (not ktv.channels[x].epgCurrent(syncTime())) and timeout:
					uplist += [x]
		if uplist: 
			try:
				ktv.getChannelsEpg(uplist)
				self.lastEpgUpdate = syncTime()
			except APIException:
				print "[iptvDream] failed to get epg for uplist"
		
		self.setTitle(Ktv.iName+" / "+" / ".join(map(_, bouquet.getPathName())) )
	
		self.fillingList = True #simple hack
		if bouquet.current.name == 'favourites':
			self["key_yellow"].setText(_("Delete"))
			self.list.setEnumerated(1)
		else:
			self["key_yellow"].setText(_("Add"))
			n = bouquet.current.name
			if cfg.sortkey.has_key(n):
				bouquet.current.sortByKey(cfg.sortkey[n].value)
			else:
				bouquet.current.sortByKey(cfg.sortkey['in group'].value)
			self.list.setEnumerated(0)
		self.list.setList(bouquet.getList())
		self.list.moveToIndex(bouquet.current.index)
		self.fillingList = False
		self.selectionChanged()
		
	def showByGroup(self):
		if self.editMode: return
		if bouquet.current.parent == None or bouquet.current.parent == bouquet.root:
			bouquet.current = bouquet.root
			bouquet.goIn(1)
		else:
			bouquet.goOut()
		self.fillList()
	
	def showAll(self):
		if self.editMode: return
		bouquet.current = bouquet.root
		bouquet.goIn(0)
		self.fillList()
		
	def showFavourites(self):
		if self.editMode: return
		bouquet.current = bouquet.root
		bouquet.goIn(2)
		self.fillList()
	
	def nextBouquet(self):
		if self.editMode: return
		print bouquet.current.name, bouquet.current.parent.name
		if bouquet.current.parent.name != 'By group': return 
		bouquet.goNext()
		self.fillList()	

	def prevBouquet(self):
		if self.editMode: return
		if bouquet.current.parent.name != 'By group': return
		bouquet.goPrev()
		self.fillList()
	
	def addremoveFavourites(self):
		if self.editMode: return
		global favouritesList
		bouquet.setIndex(self.list.getSelectionIndex())
		c = bouquet.getCurrentSel()
		if not c:
			return
		cid = c.name
		if bouquet.getCurrent() == 'favourites':
			bouquet.current.remove()
			favouritesList.remove(cid)
			self.showFavourites()
		else:
			if c.type == Bouquet.TYPE_SERVICE:
				favouritesList += [cid]
				bouquet.root.content[2].append(Bouquet(Bouquet.TYPE_SERVICE, cid))
		print "[iptvDream] Now favouritesList is:", favouritesList
		
	def selectionChanged(self):
		if self.fillingList: return			#simple hack
		idx = self.list.getSelectionIndex()
		if self.editMoving and self.lastIndex != idx:
			print "[iptvDream] moving entry", idx
			if self.lastIndex > idx:
				bouquet.current.moveOneUp()
			else:
				bouquet.current.moveOneDown()
			self.lastIndex = idx
			self.fillList() #TODO: optimize!!!
		bouquet.setIndex(self.list.getSelectionIndex())
		self.updateEpgInfo()
				
	def updateEpgInfo(self):		
		print "[iptvDream]", bouquet.current.index, bouquet.current.name
		c = bouquet.getCurrentSel()
		if c and c.type == Bouquet.TYPE_SERVICE:
			cid = c.name
			self["channelName"].setText(ktv.channels[cid].name)
			self["channelName"].show()
			curr = ktv.channels[cid].epgCurrent()
			if curr:
				self["epgTime"].setText("%s - %s" % (curr.tstart.strftime("%H:%M"), curr.tend.strftime("%H:%M")))
				self["epgName"].setText(curr.progName)
				self["epgName"].show()
				self["epgTime"].show()
				self["epgProgress"].setValue(100*curr.getTimePass() / curr.duration) #Not bouquet.aTime but zero
				self["epgProgress"].show()
				self["epgDescription"].setText(curr.progDescr)
				self["epgDescription"].show()
			else:
				self.hideEpgLabels()
			curr = ktv.channels[cid].epgNext()
			if curr:
				self["epgNextTime"].setText("%s - %s" % (curr.tstart.strftime("%H:%M"), curr.tend.strftime("%H:%M")))
				self["epgNextName"].setText(curr.progName)
				self["epgDescription"].setText(curr.progDescr)
				self["epgNextName"].show()
				self["epgNextTime"].show()
				self["epgDescription"].show()
			else:
				self.hideEpgNextLabels()
			
		else:
			self["channelName"].setText("")
			self.hideEpgLabels()
			self.hideEpgNextLabels()
	
	def hideEpgLabels(self):
		self["epgName"].hide()
		self["epgTime"].hide()
		#self["channelName"].hide()
		self["epgProgress"].hide()
		self["epgDescription"].hide()
	
	def hideEpgNextLabels(self):
		self["epgNextName"].hide()
		self["epgNextTime"].hide()	
	
	def showMenu(self):
		lst = []
		if bouquet.current.name != 'favourites':
			lst += [(_("Sort by name"), 1),
				   (_("Sort by default"), 2)]
		c = bouquet.getCurrentSel()
		if c and c.type == Bouquet.TYPE_SERVICE and config.ParentalControl.configured.value:
			cid = c.name
			if parentalControl.getProtectionLevel(fakeReference(cid).toCompareString()) == -1:
				lst += [( _("add to parental protection"), 'add')]
			else:
				lst += [( _("remove from parental protection"), 'rm')]
		if bouquet.current.name == 'favourites':
			if not self.editMode:
				lst += [( _("Enter edit mode"), 'start_edit')]
			else:
				lst += [( _("Exit edit mode"), 'stop_edit')]
		self.session.openWithCallback(self.showMenuCB, ChoiceBox, _("Context menu"), lst )
	
	def showMenuCB(self, entry = None):
		if entry is None: return
		entry = entry[1]
		global favouritesList
		print "[iptvDream] sort type is", entry
		if (entry in [1,2]):			
			n = bouquet.current.name
			print "[iptvDream] sorting", n
			if n != 'favourites':
				if cfg.sortkey.has_key(n):
					cfg.sortkey[n].value = entry
				else:
					cfg.sortkey['in group'].value = entry
				bouquet.current.sortByKey(entry)
	
			self.fillList()
		elif entry == 'add':
			service = fakeReference(bouquet.getCurrentSel().name)
			parentalControl.protectService(service.toCompareString())
		elif entry ==  'rm':
			service = fakeReference(bouquet.getCurrentSel().name)
			self.session.openWithCallback(
			  boundFunction(self.pinEntered, service.toCompareString()), PinInput, pinList =
			  [config.ParentalControl.servicepin[0].value], triesEntry = config.ParentalControl.retries.servicepin, title = _("Enter the service pin"),
			  windowTitle = _("Change pin code"))
		elif entry == 'start_edit':
			self.editMode = True
		elif entry == 'stop_edit':
			self.editMode = False
			self.editMoving = False
			favouritesList = [x.name for x in bouquet.getList()]
			print "[iptvDream] now fav are:", favouritesList
			self.fillList()

	def pinEntered(self, service, result):
		if result:
			parentalControl.unProtectService(service)
			self.exit()
		else:
			self.session.openWithCallback(self.exit, MessageBox, _("The pin code you entered is wrong."), MessageBox.TYPE_ERROR)
	
	def showEpgList(self):
		if self.editMode: return
		c =  bouquet.getCurrentSel()
		if c.type == Bouquet.TYPE_SERVICE:
			self.session.openWithCallback(self.showEpgCB, KartinaEpgList, c.name)
	
	def showEpgCB(self, time=None):
		print "[iptvDream] showEpgCB", time
		if time:
			bouquet.goIn()
			self.close(False, time)
	 
		
class KartinaEpgList(Screen):
		
	def __init__(self, session, current):
		Screen.__init__(self, session)
		
		self["key_red"] = Button(_("Archive"))
		self["key_green"] = Button(_("Fully"))
		self["key_yellow"] = Button("")
		self.list = MenuList([], content = eListboxPythonMultiContent)
		self.list.l.setFont(0, gFont("Regular", 20))
		self.list.l.setFont(1, gFont("Regular", 20))
		self.list.l.setItemHeight(28)
		self["list"] = self.list
		self["epgName"] = Label()
		self["epgDescription"] = Label()
		self["epgTime"] = Label()
		self["epgDuration"] = Label()
		
		self["sepgName"] = Label()
		self["sepgDescription"] = Label()
		self["sepgTime"] = Label()
		self["sepgDuration"] = Label()
		
		self["actions"] = ActionMap(["OkCancelActions", "IPdmEpgListActions", "ColorActions"], 
		{
			"cancel": self.exit,
			"ok": self.archive,
		#	"yellow": self.selectChannel,
			"nextDay" : self.nextDay,
			"prevDay" :self.prevDay,
			"green" : self.showSingle
		}, -1)
		
		self.lastroot = bouquet.current
		self.current = current
		self.day = 0
		self.single = False
		self.epgDownloaded = False
		self.list.onSelectionChanged.append(self.updateEpg)
		self.onLayoutFinish.append(self.fillList)
	
	def kartinaEpgEntry(self, entry):
		res = [
			(entry),
			(eListboxPythonMultiContent.TYPE_TEXT, 18, 2, 30, 22, 0, RT_HALIGN_LEFT, _(entry.tstart.strftime('%a')) ), 
			(eListboxPythonMultiContent.TYPE_TEXT, 50, 2, 90, 22, 0, RT_HALIGN_LEFT, entry.tstart.strftime('%H:%M')),
			(eListboxPythonMultiContent.TYPE_TEXT, 130, 2, 595, 24, 1, RT_HALIGN_LEFT, entry.name)]
		if ktv.channels[self.current].archive and entry.tstart < syncTime():
			res += [(eListboxPythonMultiContent.TYPE_PIXMAP_ALPHATEST, 0, 5, 16, 16, rec_png)]
		return res
		
	def fillList(self):
		self.hideLabels("s%s")
		self.list.show()
		if self.epgDownloaded: return
		d = syncTime()+secTd(bouquet.aTime)+datetime.timedelta(self.day)
		try:
			ktv.getDayEpg(self.current, d)
		except APIException:
			print "[iptvDream] load day epg failed cid = ", self.current
			return
		epglist = ktv.channels[self.current].epgDay(d)
		self.list.setList(map(self.kartinaEpgEntry, epglist))
		self.setTitle("EPG / %s / %s %s" % (ktv.channels[self.current].name, d.strftime("%d"), _(d.strftime("%b")) ))
		x = 0
		for x in xrange(len(epglist)):
			if epglist[x].tstart > d:
				break
		if x > 0: x-=1
		self.list.moveToIndex(x)
		self.epgDownloaded = True
		#self.ok()
	
	def selectChannel(self):
		self.session.openWithCallback(self.currentChanged, KartinaChannelSelection)
	
	def currentChanged(self, changed):
		if changed:
			self.current = bouquet.getCurrent()
			self.day = 0
			self.single = False
			self["key_green"].setText(_("Fully"))
			self.fillList() #FIXME: too many show-hide-show-hide.
	
	def updateEpg(self):
		self.fillEpgLabels()
	
	def fillEpgLabels(self, s = "%s"):
		idx = self.list.getSelectionIndex()
		cid = self.current
		if len(self.list.list):
			entry = self.list.list[idx][0]
			self[s % "epgName"].setText(entry.name)
			self[s % "epgTime"].setText(entry.tstart.strftime("%d.%m %H:%M"))
			self[s % "epgDescription"].setText(entry.progDescr)
			self[s % "epgDescription"].show()
			self[s % "epgName"].show()
			self[s % "epgTime"].show()
			if entry.isValid():
				self[s % "epgDuration"].setText("%s min" % (entry.duration/ 60))
				self[s % "epgDuration"].show()
			else:
				self[s % "epgDuration"].hide()
	
	def hideLabels(self, s = "%s"):
		print "hide", s
		self[s % "epgName"].hide()
		self[s % "epgTime"].hide()
		self[s % "epgDuration"].hide()
		self[s % "epgDescription"].hide()
		
	def showSingle(self):
		if not self.single:
			self["key_green"].setText("")
			self.single = True
			self.hideLabels()
			self.list.hide()
			self.fillEpgLabels("s%s")
	
	def archive(self):
		idx = self.list.getSelectionIndex()
		if len(self.list.list) > idx:
			if ktv.channels[self.current].archive:
				self.close(self.list.list[idx][0].tstart)
	
	def exit(self):
		if self.single: #If single view then go to list. Else close all
			self.single = False
			self["key_green"].setText(_("Fully"))
			self.fillList()
			self.fillEpgLabels()
			return
		bouquet.current = self.lastroot
		self.close()
	
	def nextDay(self):
		if self.single: return
		self.day+=1
		self.epgDownloaded = False
		self.fillList()
	
	def prevDay(self):
		if self.single: return
		self.day-=1
		self.epgDownloaded = False
		self.fillList()

class WeatherIcon(Pixmap): #Pixmap class by Dr.Best. A bit "long" code IMHO:) Has autoresize feature!
	def __init__(self):
		Pixmap.__init__(self)
		self.IconFileName = ""
		self.picload = ePicLoad()
		self.picload.PictureData.get().append(self.paintIconPixmapCB)

	def onShow(self):
		Pixmap.onShow(self)
		sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((self.instance.size().width(), self.instance.size().height(), sc[0], sc[1], 0, 0, '#00000000'))

	def paintIconPixmapCB(self, picInfo=None):
		ptr = self.picload.getData()
		if ptr != None:
			self.instance.setPixmap(ptr.__deref__())

	def updateIcon(self, filename):
		new_IconFileName = filename
		if (self.IconFileName != new_IconFileName):
			self.IconFileName = new_IconFileName
			self.picload.startDecode(self.IconFileName)
		else:
			print "already shown", filename

class KartinaScrollLabel(ScrollLabel):
	def down(self):
		self.pageDown
	def up(self):
		self.pageUp

class multiListHandler():
	def __init__(self, menu_lists):
		self.count = len(menu_lists)
		self.lists = menu_lists
		self.is_selection = False
		self.is_fakepage = False
		self.goto_end = False
		
		self["multiActions"] = ActionMap(["DirectionActions"], 
		{
			"right": self.doNothing,
			"rightRepeated": self.doNothing,
			"rightUp": self.pageDown,
			"left": self.doNothing,
			"leftRepeated": self.doNothing,
			"leftUp": self.pageUp,
			
			"up": self.up,
			"upRepeated": self.up,
			"upUp": self.doNothing,
			"down": self.down,
			"downRepeated": self.down,
			"downUp": self.doNothing,
		}, -2)
		self.selectList(self.lists[0])
	
	def doNothing(self): #moves away annoing messages in log
		return
	
	def selectList(self, curr):
		self.curr = curr
		for i in self.lists:
			if not isinstance(self[i], ScrollLabel): self[i].selectionEnabled(0)
		if not isinstance(self[self.curr], ScrollLabel):
			self[self.curr].selectionEnabled(1)
		self.is_selection = isinstance(self[self.curr], SelectionList)
		self.is_fakepage = hasattr(self[self.curr], 'fake_page')
		print "[iptvDream] select list", self.curr, "selection", self.is_selection, self.is_fakepage
	
	def setFakepage(self, is_fake):
		self.is_fakepage = hasattr(self[self.curr], 'fake_page') and is_fake
	
	def ok(self): #returns if selection action applied
		if self.is_selection:
			self[self.curr].toggleSelection()
			return True
		return False
		
	def down(self):
		if self.is_fakepage:
			oldidx = self[self.curr].getSelectionIndex()
			self[self.curr].down()
			if oldidx == self[self.curr].getSelectionIndex():
				self.pageDown()
		else:
			self[self.curr].down()
	
	def up(self):
		if self.is_fakepage:
			oldidx = self[self.curr].getSelectionIndex()
			self[self.curr].up()
			if oldidx == self[self.curr].getSelectionIndex():
				self.pageUp()
		else:
			self[self.curr].up()
	
	def pageDown(self):
		if self.is_fakepage:
			self.nextPage()
		else:
			self[self.curr].pageDown()	

	def pageUp(self):
		if self.is_fakepage:
			self.prevPage()
		else:
			self[self.curr].pageUp()

class DownloadThread(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.messagePump = ePythonMessagePump()
		self.__cancel = False
		self.__newTask = False
		self.__lock = Lock()
		self._lastposter = ""
		self.cnd = Condition(self.__lock)
		self.clean_list = os_listdir(POSTER_PATH)
		self.downloaded_count = len(self.clean_list)
		
	def nextTask(self, url, filename):
		self.cnd.acquire()
		self.url = url
		self.filename = filename
		self.__newTask = True
		self.cnd.notify()
		self.cnd.release()
	
	def stopTasks(self):
		self.__cancel = True
		self.cnd.acquire()
		self.cnd.notify()
		self.cnd.release()
	
	def getLastposter(self):
		self.cnd.acquire()
		tmp = self._lastposter
		self.cnd.release()
		return tmp
	
	lastposter = property(getLastposter)
	
	def run(self):
		while True:
			self.cnd.acquire()
			while not (self.__newTask or self.__cancel):
				self.cnd.wait()
			self.__newTask = False
			tmpurl = self.url
			tmpfilename = self.filename
			self.cnd.release()
			if self.__cancel:
				break
			urlretrieve(tmpurl, tmpfilename)
			print "downloaded", tmpfilename
			self.cnd.acquire()
			self._lastposter = tmpfilename
			self.cnd.release()
			self.messagePump.send(0)
			
			self.downloaded_count += 1
			self.clean_list += [tmpfilename]
			if self.downloaded_count > CLEAN_POSTER_CACHE and CLEAN_POSTER_CACHE != 0:
				eBackgroundFileEraser.getInstance().erase(self.clean_list.pop(0))
				self.downloaded_count -= 1
		print "[iptvDream]: downloadThread stopped"
			
class KartinaVideoList(Screen, multiListHandler):
	
	MODE_MAIN = 0 
	MODE_GENRES = 1
	MODE2_LIST = 0
	MODE2_INFO = 1
	
	def __init__(self, session):
		Screen.__init__(self, session)
		
		self["key_red"] = Button(_("Last"))
		self["key_green"] = Button(_("Genres"))
		self["key_yellow"] = Button(_("Search"))
		self["key_blue"] = Button(_("Best"))
		self.list = MenuList([], enableWrapAround=False, content = eListboxPythonMultiContent)
		self.list.l.setFont(0, gFont("Regular", 20))
		self.list.l.setItemHeight(28)
		self["list"] = self.list
		
		self.list.fake_page = True
		
		self.glist = SelectionList()
		self.glist.l.setFont(0, gFont("Regular", 20))
		self.glist.l.setItemHeight(28)
		self["glist"] = self.glist
		self["fullinfo"] = KartinaScrollLabel()
		
		multiListHandler.__init__(self, ["list", "glist", "fullinfo"])
		
		self["name"] = Label()
		self["description"] = Label()
		self["year"] = Label()
		
		self["rate1"] = Slider(0, 100)
		self["rate2"] = Slider(0, 100)
		self["rate1_back"] = Pixmap()
		self["rate2_back"] = Pixmap()
		self["rate1_text"] = Label("IMDB")
		self["rate2_text"] = Label("Kinopoisk")
		self["moreinfo"] = Label()
		self["poster"] = WeatherIcon() 
		
		self["pages"] = Label()
		self["genres"] = Label()
		self["genres"].setText(_("Genres: ")+_("all"))
				
		self["actions"] = ActionMap(["OkCancelActions","IPdmVideoListActions"], 
		{
			"cancel": self.exit,
			"ok": self.ok,
			"last" : self.showLast,
			"best" : self.showBest,
			"genres": self.selectGenres,
			"search": self.search,
			"nextPage" : self.nextPage,
			"prevPage" :self.prevPage,
			"showInfo" : self.showVidInfo
		}, -1)
		
		self["actions_info"] = ActionMap(["OkCancelActions"],
		{
			"cancel": self.exitInfo,
			"ok": self.exitInfo
		}, -1)
		
		self.mode = self.MODE_MAIN
		self.mode2 = self.MODE2_LIST
		self.fillingList = True
		
		self.lastroot = bouquet.current
		bouquet.saveDbselectVal()
		
		self.list.onSelectionChanged.append(self.selectionChanged)
		self.editMode = False
		self.editMoving = False
		self.onShown.append(self.start)
		
		self.download = DownloadThread()
		self.download.messagePump.recv_msg.get().append(self.startPosterDecode)
		self.download.start()
		self.onClose.append(self.disconnectPump)
		self.onClose.append(self.download.stopTasks)

	def disconnectPump(self):
		self.download.messagePump.recv_msg.get().remove(self.startPosterDecode)
		
	def start(self):
		if self.start in self.onShown:
			self.onShown.remove(self.start)
			#On first fill...
			self.exitInfo()
			if bouquet.current != bouquet.root:
				if bouquet.current.type == Bouquet.TYPE_SERVICE:
					bouquet.goOut()
				self.fillSingle()
				return
		
		try:
			bouquet.count = ktv.getVideos(bouquet.stype, bouquet.page, bouquet.genres, NUMS_ON_PAGE, bouquet.query)
		except APIException as e:
			print "[iptvDream] load videos failed!!!"
			print e
			self.session.open(MessageBox, _("Get videos failed!"), MessageBox.TYPE_ERROR)
			self.close(False)
			return
		print "[iptvDream] total videos", bouquet.count
		bouquet.current = bouquet.root
		if bouquet.getList():
			bouquet.root.remove()
			print 'clear bouquet'
		bouquet.appendRoot(ktv.buildVideoBouquet())
		bouquet.goIn()
		
		self.fillList()		
		#buildVideoBouqet already return list sorted by server.. #TODO: Think about local sort.
		#bouquet.current.sortByKey(self.sortkey) 
	
	def kartinaVideoEntry(self, entry):
		vid = entry.name
		self.number_number +=1
		res = [
			(vid),
			(eListboxPythonMultiContent.TYPE_TEXT, 0, 2, 50, 24, 0, RT_HALIGN_LEFT, str(self.number_number) ),
			(eListboxPythonMultiContent.TYPE_TEXT, 55, 2, 450, 24, 0, RT_HALIGN_LEFT, ktv.videos[vid].name )
		]
		return res

	def kartinaVideoSEntry(self, entry):
		fid = entry.name
		res = [
			(fid),
			(eListboxPythonMultiContent.TYPE_TEXT, 2, 2, 504, 24, 0, RT_HALIGN_LEFT, ktv.filmFiles[fid]['title'])
		]
		return res
	
	def fillList(self):			
		print "[iptvDream] fill video list"
		self.fillingList = True
		
		self.number_number = (bouquet.page-1)*NUMS_ON_PAGE #number_number.. What for??
		
		self.list.setList(map(self.kartinaVideoEntry, bouquet.getList() ))	
		if self.goto_end:
			bouquet.setIndex(len(bouquet.getList())-1)
		self.list.moveToIndex(bouquet.current.index)
		self.fillingList = False
		
		self.setFakepage(self.mode == self.MODE_MAIN)
		
		self.setTitle(Ktv.iName+" / "+_(bouquet.stype)+" "+bouquet.query)
		pages = (bouquet.count)/NUMS_ON_PAGE
		if bouquet.count % NUMS_ON_PAGE != 0:
			pages += 1
	
		self["pages"].setText("%s %d / %d" % (_("page"), bouquet.page, pages))
		self.hideLabels('s%s')
		self.selectionChanged()
	
	def fillSingle(self):
		self.setFakepage(False)
		
		cid = bouquet.current.name
	
		try: #TODO: do it safe
			ktv.getVideoInfo(cid)
		except APIException:
			print "[iptvDream] load videos failed!!!"
			self.session.open(MessageBox, _("Get videos failed!"), MessageBox.TYPE_ERROR)
			return
		
		#fill list if necessary
		if not len(bouquet.current.content):
			for episode in ktv.buildEpisodesBouquet(cid).getContent():
				bouquet.current.append(episode)
		#print bouquet.getList()
				
		self.fillingList = True
		self.list.setList(map(self.kartinaVideoSEntry, bouquet.getList() ))
		self.list.moveToIndex(bouquet.current.index)	
		self.fillingList = False
		
		self.setTitle(Ktv.iName+" / "+ktv.videos[cid].name)
		self.hideLabels('%s')
		self.selectionChanged()
	
	def nextPage(self):
		if not bouquet.getCurrentSel() or bouquet.getCurrentSel().type == Bouquet.TYPE_SERVICE: return
		bouquet.page += 1
		if  (bouquet.page-1)*NUMS_ON_PAGE > bouquet.count:
			bouquet.page = 1
		self.goto_end = False
		self.start()
	
	def prevPage(self):
		if not bouquet.getCurrentSel() or bouquet.getCurrentSel().type == Bouquet.TYPE_SERVICE: return
		bouquet.page -= 1
		if bouquet.page == 0:
			bouquet.page = bouquet.count / NUMS_ON_PAGE
			if bouquet.count % NUMS_ON_PAGE != 0:
				bouquet.page += 1
		self.goto_end = True
		self.start()
	
	def selectGenres(self):
		#for button click
		if self.mode == self.MODE_GENRES:
			self.endSelectGenres()
			bouquet.page = 1
			self.start()
		elif self.mode == self.MODE_MAIN:
			self.startSelectGenres()
	
	def startSelectGenres(self):
		#main code
		if not len(self.glist.list):
			ktv.getVideoGenres()
			idx = 0
			for g in ktv.video_genres:
				self.glist.addSelection(g['name'], g['id'], idx, False)
				idx += 1
		self["key_green"].setText(_("OK"))
		self["genres"].setText(_("Genres: ")+"...")
		self.selectList("glist")
		self.glist.show()
		self.hideLabels('%s')
		self.mode = self.MODE_GENRES
	
	#separate this code to not duplicate
	def endSelectGenres(self):
		self["key_green"].setText(_("Genres"))
		self.selectList("list")
		self.glist.hide()
		self.mode = self.MODE_MAIN
		self.updateGenres()
	
	def updateGenres(self):
		bouquet.genres = [item[1] for item in self.glist.getSelectionsList()]
		genrestxt = [item[0] for item in self.glist.getSelectionsList()]
		if len(genrestxt):
			self["genres"].setText(_("Genres: ")+', '.join(genrestxt))
		else:
			self["genres"].setText(_("Genres: ")+_("all"))
	
	def selectionChanged(self):
		if self.mode != self.MODE_MAIN: return
		if self.fillingList: return			#simple hack
		
		idx = self.list.getSelectionIndex()
		if self.editMoving and self.lastIndex != idx:
			print "[iptvDream] moving entry", idx
			if self.lastIndex > idx:
				bouquet.current.moveOneUp()
			else:
				bouquet.current.moveOneDown()
			self.lastIndex = idx
			self.fillList() #TODO: optimize!!!  maybe cpp part...
			
		bouquet.setIndex(idx)
		self.updateInfo()
	
	def updateInfo(self):	
		c = bouquet.getCurrentSel()
		if c:
			cid = c.name
			#some specific here
			if c.type == Bouquet.TYPE_MENU:
				s = "%s"
				self["moreinfo"].setText('\n'.join([ktv.videos[cid].country, ktv.videos[cid].genre]))
				pass
			elif c.type == Bouquet.TYPE_SERVICE:
				s = "s%s"
				fid = cid
				cid = bouquet.current.name
				self["moreinfo"].setText('\n'.join([
					"%s format" % ktv.filmFiles[fid]["format"],
					ktv.filmFiles[fid]["length"] and "%d min" % ktv.filmFiles[fid]["length"] or "",
					ktv.videos[cid].director,
					ktv.videos[cid].actors
				] ))
		else:
			s = "%s"
			self["name"].setText("")
			self["year"].setText("")
			self["description"].setText("")
			self["moreinfo"].setText("")
			self["rate1"].setValue(0)
			self["rate2"].setValue(0)
			return
		
		self["rate1"].setValue(ktv.videos[cid].rate_imdb)
		self["rate2"].setValue(ktv.videos[cid].rate_kinopoisk)
		self["name"].setText(ktv.videos[cid].name)
		self["year"].setText(ktv.videos[cid].year)
		self["description"].setText(ktv.videos[cid].descr)
		self["name"].show()
		self["year"].show()
		self["description"].show()
		self["rate1"].show()
		self["rate2"].show()
		self["rate1_back"].show()
		self["rate2_back"].show()
		self["rate1_text"].show()
		self["rate2_text"].show()
		self["moreinfo"].show()
		self["poster"].show()		
		
		self.poster_path = POSTER_PATH + ktv.getPosterPath(cid, local = True)
		print "need", self.poster_path
		if self["poster"].IconFileName != self.poster_path:
			self.download.nextTask(ktv.getPosterPath(cid), self.poster_path)
	
	def showVidInfo(self):
		c = bouquet.getCurrentSel()
		if c:
			cid = c.name
			txtmore = ""
			#some specific here
			if c.type == Bouquet.TYPE_SERVICE:
				fid = cid
				cid = bouquet.current.name
				txtactors = '%s: %s' % (_("Actors"), ktv.videos[cid].actors)
				txtmore += '\n'.join([ktv.videos[cid].country, ktv.videos[cid].genre, _("Director"),
				                ktv.videos[cid].director, txtactors])
		else:
			return
		
		txt = ktv.videos[cid].descr + '\n' + txtmore
		self["fullinfo"].setText(txt)
		self.mode2 = self.MODE2_INFO
		self.selectList("fullinfo")
		self["actions"].setEnabled(False)
		self["actions_info"].setEnabled(True)
		self["list"].hide()
		self["fullinfo"].show()

	
	def startPosterDecode(self, msg):
		if self.download.lastposter == self.poster_path:
			self["poster"].updateIcon(self.poster_path)
	
	def showLast(self):
		bouquet.stype = 'last'
		bouquet.page = 1
		bouquet.query = ''
		self.start() 
		
	def showBest(self):
		bouquet.stype = 'best'
		bouquet.page = 1
		bouquet.query = ''
		self.start()
	
	def search(self):
		self.session.openWithCallback(self.searchCB, VirtualKeyBoard, _("Search films"))
	
	def searchCB(self, text):
		if text:
			bouquet.stype = 'text'
			bouquet.query = text
			print "[iptvDream] searching for", text
			bouquet.page = 1
			self.start()	
		
	def hideLabels(self, s = "%s"):
		#FIXME: non-readable code
		print "hide", s
		self["name"].hide()
		self["year"].hide()
		self["description"].hide()
		self["rate1"].hide()
		self["rate2"].hide()
		self["rate1_back"].hide()
		self["rate2_back"].hide()
		self["rate1_text"].hide()
		self["rate2_text"].hide()
		self["moreinfo"].hide()
		self["poster"].hide()
		
	def showElements(self, element_list, hide=False):
		#TODO: use it!!
		if hide:
			for e in element_list:
				self[e].hide()
		else:	
			for e in element_list:
				self[e].show()
		return		
	
	def ok(self):
		if multiListHandler.ok(self): #This indicate that we are in SelectionList
			if UPDATE_ON_TOGGLE:
				self.updateGenres()
				bouquet.page = 1
				self.start()
			return
		c = bouquet.getCurrentSel()
		if not c:
			return
		print "[iptvDream] ok pressed. type", c.type, 'file', c.name
		if c.type == Bouquet.TYPE_MENU:
			bouquet.goIn()
			self.fillSingle()
		elif c.type == Bouquet.TYPE_SERVICE:
			bouquet.goIn()
			self.list.onSelectionChanged.pop() #Do it before close, else event happed while close.
			self.close(True)
	
	def exitInfo(self):
		self["fullinfo"].hide()
		self["list"].show()
		self["actions_info"].setEnabled(False)
		self["actions"].setEnabled(True)
		self.selectList("list")
		self.mode2 = self.MODE2_LIST
	
	def exit(self):
		c = bouquet.getCurrentSel()
		if c and c.type == Bouquet.TYPE_SERVICE:
			bouquet.goOut()
			self.goto_end = False
			self.fillList()
		else:
			self.list.onSelectionChanged.pop() #Do it before close, else event happed while close.
			bouquet.current = self.lastroot
			bouquet.restoreDbselectVal()
			self.close(False)
	
		
#----------Config Class----------
#TODO: boundFunction are looking bad. Global variables also bad idea.
#So we need to implement some class..

def selectConfig(session, **kwargs):
	l = [(a,a) for a in apis.keys()] #boundFunction is used to tell session variable
	session.openWithCallback(boundFunction(configSelected, session), ChoiceBox, _("Select service to configure"), l)

def configSelected(session, answer):
	if answer == None: return
	aname = answer[1]
	startConifg(session, aname)
	
def startConifg(session, aname):
	print "[iptvDream] open config for", aname
	session.openWithCallback(boundFunction(configEnded, session, aname), KartinaConfig, aname)

def configEnded(session, aname, changed = False):
	print "[iptvDream] config ended for", aname
	
	if KartinaPlayer.instance and (Ktv.iName == aname or Ktv.iProvider == apis[aname].iProvider):
		#We are telling KartinaPlayer to restart if config changed
		#If it fails, we are asking for next try.
		if changed:
			print "[iptvDream] restarting"
			#KartinaPlayer.instance.show() #FIXME: lockShow() or something to indicate restart
			if not KartinaPlayer.instance.go():
				askForRetry(session)		
		#If iptvDream not running (failed last start)
		#then we exit it. If it is allready running do nothing
		elif not KartinaPlayer.instance.is_runnig():
			KartinaPlayer.instance.close()
	else:
		print "[iptvDream] player not running do nothing"

def askForRetry(session):
	print "[iptvDream] start failed. Configure again?"
	exception = KartinaPlayer.instance.last_error
	session.openWithCallback(editConfig, MessageBox, _("Login or initialization failed!\nEdit options?") +'\n'+exception)
	
def editConfig(edit):
	#If we went here, then KartinaPlayer is started for shure.
	if edit:
		startConifg(KartinaPlayer.instance.session, Ktv.iName)
	else:
		configEnded(KartinaPlayer.instance.session, Ktv.iName, changed=False)


class KartinaConfig(ConfigListScreen, Screen):
	skin = """
		<screen name="KartinaConfig" position="center,center" size="550,280" title="IPTV">
			<widget name="config" position="20,10" size="520,220" scrollbarMode="showOnDemand" />
			<ePixmap name="red"	position="0,230" zPosition="4" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />
			<ePixmap name="green" position="140,230" zPosition="4" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />
			<widget name="key_red" position="0,230" zPosition="5" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
			<widget name="key_green" position="140,230" zPosition="5" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""
	
	def __init__(self, session, aname):
		Screen.__init__(self, session)
		
		self["actions"] = NumberActionMap(["SetupActions", "ColorActions"],
		{
			"green": self.keySave,
			"red": self.keyCancel,
			"cancel": self.keyCancel
		}, -2)
		
		self.aname = aname
		self.aprov = apis[aname].iProvider

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))

		cfglist = [
			getConfigListEntry(_("login"), config.iptvdream[self.aprov].login),
			getConfigListEntry(_("password"), config.iptvdream[self.aprov].password),
			getConfigListEntry(_("Show in mainmenu"), config.iptvdream[aname].in_mainmenu), 
			getConfigListEntry(_("Service (player) id"), config.iptvdream[aname].service),
			getConfigListEntry(_("Buffering time, milliseconds"), config.plugins.iptvDream.buftime)
		]
		if apis[aname].MODE == MODE_STREAM:
			cfglist.append(getConfigListEntry(_("Show in bouquets"), config.iptvdream[aname].inbouquet))
		if apis[aname].HAS_PIN == True:
			cfglist.append(getConfigListEntry(_("Auto send parental code"), config.iptvdream[aname].parental_code))
			
		ConfigListScreen.__init__(self, cfglist, session)
		self.setTitle(_("Configuration of ")+aname)
	
	def keySave(self):
		self.saveAll()
		self.close(True)

class RemoteConfig(ConfigListScreen, Screen):
	skin = """
		<screen name="RemoteConfig" position="center,center" size="550,250" title="IPTV">
			<widget name="config" position="20,10" size="520,150" scrollbarMode="showOnDemand" />
			<ePixmap name="red"	position="0,200" zPosition="4" size="140,40" pixmap="skin_default/buttons/red.png" transparent="1" alphatest="on" />
			<ePixmap name="green" position="140,200" zPosition="4" size="140,40" pixmap="skin_default/buttons/green.png" transparent="1" alphatest="on" />
			<widget name="key_red" position="0,200" zPosition="5" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
			<widget name="key_green" position="140,200" zPosition="5" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-1,-1" />
		</screen>"""
	
	def __init__(self, session):
		Screen.__init__(self, session)
		
		self["actions"] = NumberActionMap(["SetupActions", "ColorActions"],
		{
			"green": self.pushSettings,
			"red": self.keyCancel,
			"cancel": self.keyCancel
		}, -2)
		
		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("OK"))
		
		self.cfgs = ktv.getSettings()
		cfglist = []
		for key in self.cfgs:
			x = self.cfgs[key]
			if x.vallist is not None:
				cfglist.append(getConfigListEntry(key, ConfigSelection(x.vallist, x.value) ))
			elif isinstance(x.value, int):
				cfglist.append(getConfigListEntry(key, ConfigInteger(x.value, x.limits) ))
			elif isinstance(x.value, str):
				cfglist.append(getConfigListEntry(key, ConfigText(x.value, False) ))
		
		ConfigListScreen.__init__(self, cfglist, session)
		#sets = ktv.getSettings()
		#for entry in sets:
	
	def pushSettings(self):
		topush = []
		for x in self["config"].list:
			if x[1].isChanged():
				key = x[0]
				print "[iptvDream] setting to push:", self.cfgs[key].name, x[1].value
				topush.append((self.cfgs[key].name, x[1].value))
		try:
			ktv.pushSettings(topush)
		except APIException as e:
				print "[iptvDream] Error: push settings failed!"
				self.session.open(MessageBox, _("Failed to save settings")+"\n"
				+str(e), type = MessageBox.TYPE_ERROR, timeout = 5)
		self.close()

#gettext HACK:
[_("Jan"), _("Feb"), _("Mar"), _("Apr"), _("May"), _("Jun"), _("Jul"), _("Aug"), _("Sep"), _("Oct"), _("Nov") ] 
[_("all"), _("favourites"), _("By group")]
[_("last"), _("best"), _("text")]
