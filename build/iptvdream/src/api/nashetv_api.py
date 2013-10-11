#  Dreambox Enigma2 iptvDream plugin! (by technic - git)
#
#  Copyright (c) 2010 Alex Maystrenko <alexeytech@gmail.com>
#  web: http://techhost.dlinkddns.com/
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2, or (at your option) any later
# version.

from mywy_api import MyWyAPI, Ktv as MyWyKtv

class NasheTVAPI(MyWyAPI):
	
	iProvider = "nashetv"
	site = "http://core.nasche.tv/iptv/api/v1/xml"
	
class Ktv(MyWyKtv, NasheTVAPI):
	
	iName = "NasheTV"
	iTitle = "NasheTV"