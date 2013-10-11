import sys
#sys.path.append("../") 
try:
	from Plugins.Extensions.iptvDream.utils import *
	import Plugins.Extensions.iptvDream.jtvreader as jtvreader
except ImportError:
	from utils import *
	import jtvreader