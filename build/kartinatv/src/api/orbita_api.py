#  Dreambox Enigma2 IPtvDream player! (by technic)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/

from newrus_api import NewrusAPI, Ktv as NewrusKtv

class OrbitaAPI(NewrusAPI):
	
	iProvider = "Orbita"
	site = "http://iptv.orb-media.com"

class Ktv(NewrusKtv, OrbitaAPI):
	
	iName = "Orbita"
	iTitle = "Orbita"
